"""
ExampleSampler — Component 1 (minimal).

The sampler sees ONLY the loop (it executes it) — never the assert/postcondition.

Running the loop from many inputs yields traces of loop-head valuations; their
union is the REACHABLE set.  Per loop we produce:
  * positives : reachable loop-head valuations;
  * negatives : impossible TRACES (histories the loop cannot produce), stored
    as WITNESS states grouped in `neg_groups`: a perturbation is a singleton
    ("real prefix + this state"); an over-run continuation is one group.
    A rollout rejects a history iff some invariant is false at ANY witness.

Three negative families, each with a construction-time unreachability argument:
  * relation : small perturbations (±1, ±2) off DENSE bases — every in-window
    reachable neighbor is known, so a surviving perturbation is off-manifold;
  * over-run : the body executed past a GENUINE exit — real dynamics, out of
    the reachable range;
  * escape   : ladder steps kept only when they leave the variable's sampled
    range.

Truthfulness filters (label correctness — a mislabeled negative punishes
exactly the true invariants):
  * states observed reachable are never negatives;
  * states that could be a fresh loop ENTRY under their input are dropped;
  * nondet-tainted variables are never perturbed; a nondet guard disables the
    bound families (the loop can always run longer); capped runs disable
    escapes (the sampled range is then an under-approximation).

Soundness of scoring is delegated to the reward's filter cascade, which ends
in real Houdini (Frama-C/WP).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
import re
from typing import Callable, Dict, List, Optional, Set, Tuple

from ..common.program import Program, parse_program
from ..common.state import State, eval_predicate
from . import cexec

# Canonical sampler defaults — the SINGLE source of truth shared by BOTH the
# reward service (training) and the inference framework.
DEFAULT_N_RUNS = 12
DEFAULT_SEED = 0

_SMALL_DELTAS = (1, -1, 2, -2)
_LADDER_DELTAS = (5, -5, 8, -8, 13, -13, 21, -21, 34, -34)
_BASE_CAP = 96           # perturbation bases, stratified across all positives
# Forward trace states required for a "dense" base: the entry state (it=0) and
# the first head (it=1) carry the SAME valuation, so a value-jump of 2 along a
# unit-step manifold is only witnessed by the state at it+3.
_DENSE_WINDOW = 3


@dataclass
class ExampleSet:
    program: Program
    positives: Dict[int, List[State]] = field(default_factory=dict)
    negatives: Dict[int, List[State]] = field(default_factory=dict)
    # witness-state indices per impossible trace (see module docstring)
    neg_groups: Dict[int, List[List[int]]] = field(default_factory=dict)
    stats: Dict[int, dict] = field(default_factory=dict)

    def pos(self, loop_idx: int = 0) -> List[State]:
        return self.positives.get(loop_idx, [])

    def neg(self, loop_idx: int = 0) -> List[State]:
        return self.negatives.get(loop_idx, [])

    def groups(self, loop_idx: int = 0) -> List[List[int]]:
        g = self.neg_groups.get(loop_idx)
        if g is None:
            g = [[i] for i in range(len(self.neg(loop_idx)))]
        return g


class ExampleSampler:
    def __init__(
        self,
        source: str,
        n_runs: int = DEFAULT_N_RUNS,
        seed: int = DEFAULT_SEED,
        logger: Optional[logging.Logger] = None,
    ):
        self.source = source
        self.n_runs = n_runs
        self.seed = seed
        self.log = logger or logging.getLogger("rl_pipeline.sampler")

    # ── positives ────────────────────────────────────────────────────────────
    @staticmethod
    def _dedup(states: List[State]) -> List[State]:
        seen, out = set(), []
        for s in states:
            k = s.vars_key()
            if k not in seen:
                seen.add(k)
                out.append(s)
        return out

    # ── negatives ────────────────────────────────────────────────────────────
    @staticmethod
    def _modified_vars(prog: Program, loop_idx: int = 0) -> List[str]:
        """Loop-head variables the loop BODY assigns to — the ones that move
        along a trace, so perturbing them leaves the reachable set."""
        loop = prog.loops[loop_idx]
        body = prog.source[loop.body_open + 1: loop.body_close]
        mod = []
        for v in prog.pre_vars:
            e = re.escape(v)
            if (re.search(rf"\b{e}\s*(=[^=]|[-+*/%|&^]=)", body)
                    or re.search(rf"\b{e}\s*(\+\+|--)", body)
                    or re.search(rf"(\+\+|--)\s*\b{e}\b", body)):
                mod.append(v)
        return mod

    @staticmethod
    def _guard_nondeterministic(prog: Program, loop_idx: int = 0) -> bool:
        loop = prog.loops[loop_idx]
        return bool(re.search(r"\bunknown\w*\s*\(", loop.guard or ""))

    _ASSIGN_RE = re.compile(
        r"\b(\w+)\s*(?:=[^=]|[-+*/%|&^]=)|(?:\+\+|--)\s*(\w+)\b|\b(\w+)\s*(?:\+\+|--)")

    @classmethod
    def _assigned_names(cls, text: str) -> Set[str]:
        names: Set[str] = set()
        for m in cls._ASSIGN_RE.finditer(text):
            name = next((g for g in m.groups() if g), None)
            if name:
                names.add(name)
        return names

    @classmethod
    def _nondet_tainted(cls, prog: Program, loop_idx: int = 0) -> Set[str]:
        """Variables whose loop-head value depends on WHICH unknown() branches
        ran — their reachable values form an envelope a finite sample cannot
        enumerate, so they must never be perturbed.  Taint = assigned from
        unknown() (incl. pre-loop entry values), assigned under a
        nondeterministic condition, then propagated through straight-line data
        flow to a fixpoint."""
        loop = prog.loops[loop_idx]
        body = prog.source[loop.body_open + 1: loop.body_close]
        tainted: Set[str] = set()
        for name, expr in prog.local_inits:
            if expr and re.search(r"\bunknown\w*\s*\(", expr):
                tainted.add(name)
        changed = True
        while changed:
            changed = False
            for name, expr in prog.local_inits:
                if name not in tainted and expr and any(
                        re.search(rf"\b{re.escape(t)}\b", expr) for t in tainted):
                    tainted.add(name)
                    changed = True
        for m in re.finditer(r"\b(\w+)\s*=[^=][^;]*\bunknown\w*\s*\(", body):
            tainted.add(m.group(1))
        scopes = cls._branch_scopes(body)
        stmts = re.findall(r"\b(\w+)\s*=\s*([^=;][^;]*);", body)

        def refs_tainted(expr: str) -> bool:
            return any(re.search(rf"\b{re.escape(t)}\b", expr) for t in tainted)

        changed = True
        while changed:
            changed = False
            for cond, block in scopes:
                if re.search(r"\bunknown\w*\s*\(", cond) or refs_tainted(cond):
                    new = cls._assigned_names(block) - tainted
                    if new:
                        tainted |= new
                        changed = True
            for v, expr in stmts:
                if v not in tainted and refs_tainted(expr):
                    tainted.add(v)
                    changed = True
        return tainted

    @staticmethod
    def _branch_scope_ranges(body: str):
        """[(condition, [(start, end), ...])] for every `if (cond) {...}
        [else {...}]` in the body."""
        scopes = []
        for m in re.finditer(r"\bif\s*\(", body):
            depth, i = 1, m.end()
            while i < len(body) and depth:
                if body[i] == "(":
                    depth += 1
                elif body[i] == ")":
                    depth -= 1
                i += 1
            cond = body[m.end():i - 1]
            pos = body.find("{", i)
            if pos < 0 or body[i:pos].strip() not in ("", ")"):
                continue
            depth, j = 1, pos + 1
            while j < len(body) and depth:
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    depth -= 1
                j += 1
            ranges = [(pos + 1, j - 1)]
            m_else = re.match(r"\s*else\s*\{", body[j:])
            if m_else:
                epos = j + m_else.end() - 1
                depth, k = 1, epos + 1
                while k < len(body) and depth:
                    if body[k] == "{":
                        depth += 1
                    elif body[k] == "}":
                        depth -= 1
                    k += 1
                ranges.append((epos + 1, k - 1))
            scopes.append((cond, ranges))
        return scopes

    @classmethod
    def _branch_scopes(cls, body: str):
        """[(condition, joined block text)], PLUS braceless `if (cond) stmt;
        [else stmt2;]` arms."""
        scopes = [(cond, "\n".join(body[s:e] for s, e in ranges))
                  for cond, ranges in cls._branch_scope_ranges(body)]
        for m in re.finditer(r"\bif\s*\(", body):
            depth, i = 1, m.end()
            while i < len(body) and depth:
                if body[i] == "(":
                    depth += 1
                elif body[i] == ")":
                    depth -= 1
                i += 1
            cond = body[m.end():i - 1]
            rest = body[i:]
            if re.match(r"\s*\{", rest):
                continue
            stmt_end = body.find(";", i)
            if stmt_end < 0:
                continue
            arm = body[i:stmt_end + 1]
            m_else = re.match(r"\s*else\b(?!\s*if)", body[stmt_end + 1:])
            if m_else:
                epos = stmt_end + 1 + m_else.end()
                m_brace = re.match(r"\s*\{", body[epos:])
                if m_brace:
                    bpos = epos + m_brace.end() - 1
                    depth, k = 1, bpos + 1
                    while k < len(body) and depth:
                        if body[k] == "{":
                            depth += 1
                        elif body[k] == "}":
                            depth -= 1
                        k += 1
                    arm += "\n" + body[bpos + 1:k - 1]
                else:
                    e_end = body.find(";", epos)
                    if e_end > 0:
                        arm += "\n" + body[epos:e_end + 1]
            scopes.append((cond, arm))
        return scopes

    @staticmethod
    def _body_nondeterministic(prog: Program, loop_idx: int = 0) -> bool:
        loop = prog.loops[loop_idx]
        body = prog.source[loop.body_open + 1: loop.body_close]
        return bool(re.search(r"\bunknown\w*\s*\(", body))

    @staticmethod
    def _bases(positives: List[State]) -> List[State]:
        """Stratified subsample across ALL positives."""
        if len(positives) <= _BASE_CAP:
            return positives
        step = len(positives) // _BASE_CAP
        return positives[::step][:_BASE_CAP]

    def _entry_feasible_fn(self, prog: Program) -> Callable[[State], bool]:
        """A perturbed state that could be a FRESH LOOP ENTRY under its input is
        reachable and must never be labeled negative."""
        checks = [(n, e) for n, e in prog.local_inits
                  if e and e.strip() and not re.search(r"\bunknown\w*\s*\(", e)]
        req = (prog.requires or "").strip()
        params = list(prog.params)

        def feasible(s: State) -> bool:
            for p in params:
                if p in s.pre and s.vars.get(p) != s.pre.get(p):
                    return False
            for name, expr in checks:
                ok = eval_predicate(f"({name}) == ({expr})", s)
                if ok is not True:
                    return False
            if req and eval_predicate(req, s) is False:
                return False
            return True

        return feasible

    def _relation_negatives(self, movable: List[str], bases: List[State],
                            dense_index: Set[Tuple[int, int]],
                            novel_only: Optional[Dict[str, Set[int]]] = None) -> List[State]:
        """Small single-axis + pairwise steps from DENSE bases (next
        `_DENSE_WINDOW` trace states sampled, so a surviving perturbation is
        genuinely off-manifold).  `novel_only` applies for nondeterministic
        bodies: keep only perturbations giving some variable a never-observed
        value."""
        out: List[State] = []

        def novel(v: str, val: int) -> bool:
            return novel_only is None or val not in novel_only.get(v, set())

        for r in bases:
            if r.run >= 0 and not all(
                (r.run, r.it + k) in dense_index for k in range(1, _DENSE_WINDOW + 1)
            ):
                continue
            base = r.vars
            for v in movable:
                for d in _SMALL_DELTAS:
                    if not novel(v, base[v] + d):
                        continue
                    nv = dict(base); nv[v] = nv[v] + d
                    out.append(State(vars=nv, pre=dict(r.pre)))
            for i in range(len(movable)):
                for j in range(i + 1, len(movable)):
                    u, w = movable[i], movable[j]
                    for d in _SMALL_DELTAS:
                        for su, sw in ((d, d), (d, -d)):
                            if not (novel(u, base[u] + su) or novel(w, base[w] + sw)):
                                continue
                            nv = dict(base); nv[u] += su; nv[w] += sw
                            out.append(State(vars=nv, pre=dict(r.pre)))
        return out

    def _escape_negatives(self, movable: List[str], bases: List[State],
                          positives: List[State]) -> List[State]:
        """Ladder steps kept only when they leave the variable's sampled range
        (full traces run to the genuine exit, so escapees are unreachable)."""
        lo = {v: min(p.vars[v] for p in positives) for v in movable}
        hi = {v: max(p.vars[v] for p in positives) for v in movable}
        out: List[State] = []
        for r in bases:
            base = r.vars
            for v in movable:
                for d in _LADDER_DELTAS:
                    nv_val = base[v] + d
                    if lo[v] <= nv_val <= hi[v]:
                        continue
                    nv = dict(base); nv[v] = nv_val
                    out.append(State(vars=nv, pre=dict(r.pre)))
        return out

    def _negatives(self, prog: Program, positives: List[State], overrun: List[State],
                   raw_reach: List[State], capped: bool) -> Tuple[List[State], List[List[int]], dict]:
        movable = self._modified_vars(prog, 0)
        if not movable:
            movable = [v for v in prog.pre_vars if v not in set(prog.params)] or list(prog.pre_vars)

        reachable = {s.vars_key() for s in positives}
        entry_feasible = self._entry_feasible_fn(prog)
        seen: set = set()

        def keep(states: List[State]) -> List[State]:
            out = []
            for s in states:
                k = s.vars_key()
                if k in reachable or k in seen:
                    continue
                if entry_feasible(s):
                    continue
                seen.add(k)
                out.append(s)
            return out

        nondet_body = self._body_nondeterministic(prog, 0)
        tainted = self._nondet_tainted(prog, 0)
        guard = prog.loops[0].guard or ""
        nondet = (self._guard_nondeterministic(prog, 0)
                  or any(re.search(rf"\b{re.escape(t)}\b", guard) for t in tainted))
        dense_index = {(s.run, s.it) for s in raw_reach if s.run >= 0}
        bases = self._bases(positives)
        movable = [v for v in movable if v not in tainted]
        novel_only = None
        if nondet_body:
            novel_only = {v: {p.vars[v] for p in positives} for v in movable}

        # bound families: over-run (one group per continuation) + ladder escapes
        bound: List[State] = []
        bound_groups: List[List[int]] = []
        n_over_traces = n_escape = 0
        if not nondet:
            by_run: Dict[int, List[State]] = {}
            for s in keep(overrun):
                by_run.setdefault(s.run, []).append(s)
            for run in sorted(by_run):
                idxs = []
                for s in by_run[run]:
                    idxs.append(len(bound))
                    bound.append(s)
                bound_groups.append(idxs)
            n_over_traces = len(by_run)
            if not capped and positives:
                for s in keep(self._escape_negatives(movable, bases, positives)):
                    bound_groups.append([len(bound)])
                    bound.append(s)
                    n_escape += 1

        relation = keep(self._relation_negatives(movable, bases, dense_index, novel_only))

        negatives = bound + relation
        groups = bound_groups + [[len(bound) + i] for i in range(len(relation))]
        stats = {
            "n_traces": len(groups),
            "n_witness_states": len(negatives),
            "relation": len(relation),
            "bound_overrun": n_over_traces,
            "bound_escape": n_escape,
            "capped": capped,
            "nondet_guard": nondet,
        }
        return negatives, groups, stats

    # ── driver ───────────────────────────────────────────────────────────────
    def sample(self) -> ExampleSet:
        prog = parse_program(self.source)
        es = ExampleSet(program=prog)
        for loop_idx in range(len(prog.loops)):
            runs = self.n_runs * 2 if self._body_nondeterministic(prog, loop_idx) else self.n_runs
            reach, overrun, capped = cexec.collect_traces(
                prog, loop_idx=loop_idx, n_runs=runs, seed=self.seed)
            positives = self._dedup(reach)
            es.positives[loop_idx] = positives
            if loop_idx == 0:
                negatives, groups, stats = self._negatives(prog, positives, overrun, reach, capped)
                es.negatives[loop_idx] = negatives
                es.neg_groups[loop_idx] = groups
                es.stats[loop_idx] = {"n_pos": len(positives), "n_neg": len(groups), **stats}
            else:
                es.negatives[loop_idx] = []
                es.neg_groups[loop_idx] = []
                es.stats[loop_idx] = {"n_pos": len(positives), "n_neg": 0}
        return es


def _cli():
    import argparse

    ap = argparse.ArgumentParser(description="Sample positive/negative loop-entry valuations")
    ap.add_argument("program", help="path to a C program")
    ap.add_argument("--runs", type=int, default=DEFAULT_N_RUNS)
    ap.add_argument("--show", type=int, default=6, help="print N example states each")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    src = open(args.program).read()
    es = ExampleSampler(src, n_runs=args.runs).sample()
    print(f"program: {es.program.func_name}  guard: {es.program.loop.guard!r} (loop only; assert not used)")
    for li in sorted(es.positives):
        st = es.stats[li]
        print(f"\nloop {li}: positives={st['n_pos']} negative-traces={st['n_neg']} "
              f"(relation={st.get('relation','-')} overrun={st.get('bound_overrun','-')} "
              f"escape={st.get('bound_escape','-')} capped={st.get('capped','-')})")
        print("  positives:")
        for s in es.pos(li)[:args.show]:
            print("    +", s.render())
        print("  negatives:")
        for s in es.neg(li)[:args.show]:
            print("    -", s.render())


if __name__ == "__main__":
    _cli()
