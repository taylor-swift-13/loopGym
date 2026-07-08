"""
ExampleSampler — Component 1.

The sampler sees ONLY the loop (it executes it) — never the assert/postcondition.

A *trace* is the group of loop-HEAD variable valuations one execution passes
through.  Running the loop from many inputs yields many traces; their union is
the REACHABLE set.  Per loop we produce:
  * positives : reachable loop-head valuations (the states of real traces)
  * negatives : impossible TRACES — histories the loop cannot produce.  Each
    negative is stored as its WITNESS states (where the fake history departs
    from anything real) grouped in `neg_groups`: a one-shot perturbation is a
    singleton ("real prefix + this state"); an over-run continuation is one
    group holding the whole past-the-exit segment.  A rollout rejects the
    history iff some invariant is false at ANY witness.

The strongest invariant is the tightest characterization of the reachable set:
sound on every positive, ruling out as many impossible histories as possible.

Negatives come in two balanced dimensions, both TRUTHFUL by construction (a
mislabeled negative — an actually-reachable state — poisons the reward, since
it punishes exactly the true invariants):

  RELATION dimension (small perturbations, off any reachable manifold):
    single-axis / joint pairwise ±{1,2,3} steps from bases whose local trace
    window is densely sampled — every in-window reachable neighbor is known, so
    a surviving perturbation is genuinely off-manifold, exposing a missing
    relational law (x+y==n, z==x*y, …).

  BOUND dimension (relation holds, range violated):
    * over-run states: the loop body executed past a GENUINE exit — real
      dynamics, out of range;
    * box-escape states: large ladder steps ±{5,…,89} kept only when they leave
      the variable's sampled range — many distinct values per axis, so a
      pointwise "v != k" farm cannot cover them with a realistic clause budget.

Anti-hack guards baked in:
  * perturbations of states that could be a fresh loop ENTRY (params free,
    literal locals at their init, requires satisfiable) are dropped — those are
    reachable by choosing different inputs, and rewarding their rejection would
    favor sample-overfit predicates over true invariants;
  * runs that hit the divergence cap disable the bound dimension's box-escape
    (sampled ranges are then under-approximations);
  * `while(unknown())`-style nondeterministic guards disable the bound
    dimension entirely (the loop can always run longer, so no range is sound);
  * the two dimensions are balanced so neither dominates the reward.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
import re
from typing import Callable, Dict, List, Optional, Set, Tuple

from ..common.program import Program, parse_program
from ..common.state import State, eval_int, eval_predicate
from . import cexec

# Canonical sampler defaults — the SINGLE source of truth shared by BOTH the
# reward service (training) and the inference framework, so training and
# inference sample identically.  n_runs = how many executions define the reachable
# set (more runs = tighter reachability approximation).  Override only for experiments.
DEFAULT_N_RUNS = 12
DEFAULT_SEED = 0

# relation dimension: small steps, verifiable against the dense trace window
_SMALL_DELTAS = (1, -1, 2, -2, 3, -3)
# bound dimension: large ladder steps, kept only when they escape the sampled range
_LADDER_DELTAS = (5, -5, 8, -8, 13, -13, 21, -21, 34, -34, 55, -55, 89, -89)
_BASE_CAP = 96           # perturbation bases, stratified across all positives
# Forward trace states required for a "dense" base.  Must be max(|small delta|)+1:
# the entry state (it=0) and the first head (it=1) carry the SAME valuation (the
# head prints BEFORE the body runs), so a value-jump of 3 along a unit-step
# manifold is only witnessed by the state at it+4 — a window of 3 lets frontier
# perturbations from short runs land on the unsampled next-in-trace state.
_DENSE_WINDOW = 4


@dataclass
class ExampleSet:
    program: Program
    positives: Dict[int, List[State]] = field(default_factory=dict)
    negatives: Dict[int, List[State]] = field(default_factory=dict)
    # A NEGATIVE is a TRACE the loop cannot produce (an impossible history),
    # not an isolated valuation.  `negatives` stores the WITNESS states —
    # the points where the impossible history departs from anything real —
    # and `neg_groups` maps each history to its witness indices: a rollout
    # rejects the history iff it rejects ANY witness.  A one-shot perturbation
    # is a singleton group ("real prefix + this state"); an over-run
    # continuation is ONE group holding its whole past-the-exit segment.
    neg_groups: Dict[int, List[List[int]]] = field(default_factory=dict)
    stats: Dict[int, dict] = field(default_factory=dict)

    def pos(self, loop_idx: int = 0) -> List[State]:
        return self.positives.get(loop_idx, [])

    def neg(self, loop_idx: int = 0) -> List[State]:
        return self.negatives.get(loop_idx, [])

    def groups(self, loop_idx: int = 0) -> List[List[int]]:
        """Witness-index groups, one per impossible trace (singletons when
        no explicit grouping was recorded)."""
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
        """Loop-head variables that the loop BODY assigns to — these are the ones
        that move along a trace, so perturbing them leaves the reachable set.  A
        variable that the loop never writes is a fixed input and is kept constant
        (this is data-flow, not a param/local distinction: a *parameter* modified in
        the loop, e.g. `while(unknown()){x=2;}`, is correctly treated as movable)."""
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
        """Variables whose loop-head value depends on WHICH unknown() branches ran.

        Such a variable's reachable values form an envelope (one value per branch
        sequence) that a finite sample cannot enumerate — a small perturbation of
        an observed value can land on an unobserved-but-reachable combination, so
        these variables must not be perturbed at all.

        Taint = assigned from an unknown() call, or assigned inside an
        `if (unknown()) {...} [else {...}]` scope, then propagated through
        straight-line data flow (`v = ...t...`) to a fixpoint."""
        loop = prog.loops[loop_idx]
        body = prog.source[loop.body_open + 1: loop.body_close]
        tainted: Set[str] = set()
        # PRE-LOOP nondeterminism: a local entering the loop with an unknown()
        # value (`x = unknown(); while(...)`) has an entry ENVELOPE exactly like
        # a branch-dependent variable — a perturbed neighbor may be reachable
        # under a different draw, so it must be tainted too (plus straight-line
        # propagation through the other entry expressions)
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
        # direct data taint: v = ... unknown() ...
        for m in re.finditer(r"\b(\w+)\s*=[^=][^;]*\bunknown\w*\s*\(", body):
            tainted.add(m.group(1))
        scopes = cls._branch_scopes(body)
        stmts = re.findall(r"\b(\w+)\s*=\s*([^=;][^;]*);", body)

        def refs_tainted(expr: str) -> bool:
            return any(re.search(rf"\b{re.escape(t)}\b", expr) for t in tainted)

        changed = True
        while changed:
            changed = False
            # control dependence: a branch whose condition is nondeterministic
            # (unknown(), or referencing a tainted var) taints everything it assigns
            for cond, block in scopes:
                if re.search(r"\bunknown\w*\s*\(", cond) or refs_tainted(cond):
                    new = cls._assigned_names(block) - tainted
                    if new:
                        tainted |= new
                        changed = True
            # data flow: v = expr(tainted) taints v
            for v, expr in stmts:
                if v not in tainted and refs_tainted(expr):
                    tainted.add(v)
                    changed = True
        return tainted

    @staticmethod
    def _branch_scope_ranges(body: str):
        """[(condition, [(start, end), ...])] for every `if (cond) {...}
        [else {...}]` in the body (else-blocks belong to their if's condition)."""
        scopes = []
        for m in re.finditer(r"\bif\s*\(", body):
            # match the condition's parentheses
            depth, i = 1, m.end()
            while i < len(body) and depth:
                if body[i] == "(":
                    depth += 1
                elif body[i] == ")":
                    depth -= 1
                i += 1
            cond = body[m.end():i - 1]
            pos = body.find("{", i)
            # only treat a brace DIRECTLY after the condition as the branch body
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
        """[(condition, joined block text)] view over _branch_scope_ranges,
        PLUS braceless `if (cond) stmt; [else stmt2;]` arms — a braceless
        unknown()-branch taints exactly like a braced one."""
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
                continue                      # braced: already covered
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

    # ── one assignment scan shared by every conservation rescue ─────────────
    @classmethod
    def _frozen_consts(cls, prog: Program, body: str) -> Dict[str, int]:
        """Variables constant through the loop with a KNOWN literal value:
        never assigned in the body, literal entry value (`d1 = 1;` pre-loop).
        Lets `x -= d1` count as a constant self-step."""
        assigned = cls._assigned_names(body)
        out: Dict[str, int] = {}
        for name, expr in prog.local_inits:
            if name not in assigned and expr and cls._LIT_RE.fullmatch(expr.strip()):
                out[name] = int(expr.strip())
        return out

    @classmethod
    def _var_assignments(cls, body: str,
                         consts: Optional[Dict[str, int]] = None
                         ) -> Dict[str, List[Tuple[int, str, Optional[int]]]]:
        """Every assignment in the body, per variable: (pos, kind, value) with
        kind 'step' (constant self-step: `v = v ± c`, `v += c`, `v++`, or
        `v ± f` for a frozen literal-valued f from `consts`), 'lit' (integer
        literal `v = L`), or 'other' (anything else)."""
        consts = consts or {}

        def step_of(v: str, sign: str, amount: str) -> Optional[int]:
            if amount.isdigit():
                mag = int(amount)
            elif amount in consts:
                mag = consts[amount]
            else:
                return None
            return mag if sign == "+" else -mag

        out: Dict[str, List[Tuple[int, str, Optional[int]]]] = {}
        for m in re.finditer(r"\b(\w+)\s*=\s*([^=;][^;]*);", body):
            v, rhs = m.group(1), m.group(2).strip()
            sm = re.fullmatch(rf"{re.escape(v)}\s*([+-])\s*(\w+)", rhs)
            step = step_of(v, sm.group(1), sm.group(2)) if sm else None
            if step is not None:
                out.setdefault(v, []).append((m.start(), "step", step))
            elif cls._LIT_RE.fullmatch(rhs):
                out.setdefault(v, []).append((m.start(), "lit", int(rhs)))
            else:
                out.setdefault(v, []).append((m.start(), "other", None))
        for m in re.finditer(r"\b(\w+)\s*([+-])=\s*([^;]+);", body):
            step = step_of(m.group(1), m.group(2), m.group(3).strip())
            out.setdefault(m.group(1), []).append(
                (m.start(), "step", step) if step is not None
                else (m.start(), "other", None))
        for m in re.finditer(r"\b(\w+)\s*(\+\+|--)|(\+\+|--)\s*(\w+)\b", body):
            v = m.group(1) or m.group(4)
            out.setdefault(v, []).append(
                (m.start(), "step", 1 if (m.group(2) or m.group(3)) == "++" else -1))
        for m in re.finditer(r"\b(\w+)\s*([*/%|&^]|<<|>>)=", body):
            out.setdefault(m.group(1), []).append((m.start(), "other", None))
        return out

    @classmethod
    def _const_step_sites(cls, prog: Program, loop_idx: int, tainted: Set[str]):
        """Per TAINTED variable, its {assignment site: net constant step} map —
        or excluded entirely if ANY of its assignments is not a constant
        self-step (`v = v ± c`, `v += c`, `v++`).  Sites carry the branch-arm
        chain (if/else arms are mutually exclusive) plus braceless-if sub-sites,
        so co-location means "always executed together"."""
        loop = prog.loops[loop_idx]
        body = prog.source[loop.body_open + 1: loop.body_close]
        scopes = cls._branch_scope_ranges(body)

        def scope_chain(pos: int):
            # if/else ARMS are mutually exclusive: site identity must carry the
            # arm index, or an if-arm assignment and an else-arm assignment
            # would look co-located (they never execute together)
            return tuple((idx, arm)
                         for idx, (_c, ranges) in enumerate(scopes)
                         for arm, (s, e) in enumerate(ranges)
                         if s <= pos < e)

        # braceless `if (cond) stmt; [else {...}]` guards: the guarded statement
        # belongs to a sub-site UNLESS cond is a textual conjunct of an enclosing
        # scope condition (then it is redundant and transparent).  The ELSE of a
        # transparent braceless if is ¬cond — dead under the enclosing condition
        # but still a distinct site, never transparent.
        braceless = []
        for m in re.finditer(r"\bif\s*\(([^()]*)\)\s*(?!\s*\{)", body):
            stmt_end = body.find(";", m.end())
            if stmt_end < 0:
                continue
            cond = re.sub(r"\s+", " ", m.group(1)).strip()
            conjuncts = set()
            for idx, _arm in scope_chain(m.start()):
                for part in scopes[idx][0].split("&&"):
                    conjuncts.add(re.sub(r"\s+", " ", part).strip("() "))
            if cond not in conjuncts:
                braceless.append((m.end(), stmt_end, ("bl", m.start())))
            m_else = re.match(r"\s*else\s*\{", body[stmt_end + 1:])
            if m_else:
                epos = stmt_end + 1 + m_else.end() - 1
                depth, k = 1, epos + 1
                while k < len(body) and depth:
                    if body[k] == "{":
                        depth += 1
                    elif body[k] == "}":
                        depth -= 1
                    k += 1
                braceless.append((epos + 1, k - 1, ("bl-else", m.start())))

        def site_of(pos: int):
            sub = tuple(tag for s, e, tag in braceless if s <= pos < e)
            return scope_chain(pos) + sub

        # per var, {site: net step} — excluded if any assignment is not a step
        out: Dict[str, Dict[tuple, int]] = {}
        for v, recs in cls._var_assignments(body, cls._frozen_consts(prog, body)).items():
            if v not in tainted or v not in prog.pre_vars:
                continue
            if any(kind != "step" for _pos, kind, _val in recs):
                continue
            per: Dict[tuple, int] = {}
            for pos, _kind, val in recs:
                site = site_of(pos)
                per[site] = per.get(site, 0) + val
            if per:
                out[v] = per
        return out

    @classmethod
    def _rigid_pairs(cls, prog: Program, loop_idx: int, tainted: Set[str]):
        """Conserved-difference pairs among TAINTED variables: v, w updated only
        by constant self-steps at exactly the same sites with proportional step
        vectors conserve `cw·v − cv·w` along EVERY branch sequence.
        Returns [(v, w, cv, cw)]."""
        rescuable = cls._const_step_sites(prog, loop_idx, tainted)
        pairs = []
        names = sorted(rescuable)
        for a in range(len(names)):
            for b in range(a + 1, len(names)):
                v, w = names[a], names[b]
                pv, pw = rescuable[v], rescuable[w]
                if set(pv) != set(pw):
                    continue
                sites = sorted(pv)
                cv, cw = pv[sites[0]], pw[sites[0]]
                if all(pv[s] * cw == pw[s] * cv for s in sites):
                    pairs.append((v, w, cv, cw))
        return pairs

    @classmethod
    def _lattice_rescues(cls, prog: Program, loop_idx: int, tainted: Set[str]):
        """gcd-lattice conservation for a single TAINTED variable: if every
        update of v is a constant self-step and g = gcd(|steps|) > 1, then
        v ≡ v_entry (mod g) along EVERY branch sequence (e.g.
        `if(unknown()) i+=6; else i+=3;` conserves i mod 3).  Perturbations off
        the lattice are unreachable regardless of branching.
        Returns [(v, g)]."""
        from math import gcd
        rescuable = cls._const_step_sites(prog, loop_idx, tainted)
        out = []
        for v, per in sorted(rescuable.items()):
            g = 0
            for step in per.values():
                g = gcd(g, abs(step))
            if g > 1:
                out.append((v, g))
        return out

    _LIT_RE = re.compile(r"^-?\d+$")

    @classmethod
    def _monotone_rescues(cls, prog: Program, loop_idx: int, tainted: Set[str]):
        """Directional conservation for TAINTED variables: if EVERY assignment
        to v in the body is a constant self-step or an integer literal, then

          all steps >= 0  ->  v >= min(v_entry, literals)   (floor)
          all steps <= 0  ->  v <= max(v_entry, literals)   (ceiling)

        along EVERY branch sequence — a value beyond that bound is unreachable
        no matter which unknown() branches run.  Literal-only variables (state
        tags like `turn = 0/1/2`) get BOTH directions.  Rescues the whole
        "counter with reset" family (`if(unknown()) c++; else if(c==n) c=1;`)
        that taint analysis otherwise leaves signal-free.
        Returns [(v, direction, literals)] with direction in {+1 floor, -1 ceiling}."""
        loop = prog.loops[loop_idx]
        body = prog.source[loop.body_open + 1: loop.body_close]
        out = []
        for v, recs in sorted(cls._var_assignments(body, cls._frozen_consts(prog, body)).items()):
            if v not in tainted or v not in prog.pre_vars:
                continue
            if any(kind == "other" for _pos, kind, _val in recs):
                continue
            steps = [val for _pos, kind, val in recs if kind == "step"]
            literals = [val for _pos, kind, val in recs if kind == "lit"]
            if all(s >= 0 for s in steps):
                out.append((v, +1, literals))
            if all(s <= 0 for s in steps):
                out.append((v, -1, literals))
        return out

    def _entry_value_fn(self, prog: Program) -> Callable[[State, str], Optional[int]]:
        """Numeric loop-entry value of a variable for a given state's inputs:
        params come from `pre`; locals only when their init is an int literal
        or a direct param copy (anything else -> None, skip the rescue there)."""
        params = set(prog.params)
        inits = dict(prog.local_inits)

        def entry_value(s: State, v: str) -> Optional[int]:
            if v in params:
                return s.pre.get(v)
            expr = (inits.get(v) or "").strip()
            if self._LIT_RE.fullmatch(expr):
                return int(expr)
            if expr in params:
                return s.pre.get(expr)
            return None

        return entry_value

    def _seed_deltas(self) -> List[int]:
        """Deltas for bound-law negatives, HASHED FROM THE SEED: these negatives
        cluster at few values (bound±d), so fixed deltas would let a pointwise
        `v != k` farm memorize them; with per-seed deltas the holdout's values
        differ and the farm's min-score collapses while `v >= bound` keeps
        rejecting everything.  Always includes 1 (the boundary itself)."""
        ds: List[int] = [1]
        k = 0
        while len(ds) < 8 and k < 64:
            d = 2 + (self.seed * 7919 + k * 104729) % 62
            if d not in ds:
                ds.append(d)
            k += 1
        return ds

    def _bound_negatives(self, laws, bases: List[State]) -> List[State]:
        """States on the wrong side of a conserved bound — sound by construction.
        `laws` = [(v, direction, bound_of)] with direction +1 (v >= bound) or
        -1 (v <= bound); `bound_of(state)` returns the bound value under that
        state's inputs, or None when its side conditions fail there."""
        ds = self._seed_deltas()
        out: List[State] = []
        for v, direction, bound_of in laws:
            for r in bases:
                if v not in r.vars:
                    continue
                bound = bound_of(r)
                if bound is None:
                    continue
                for d in ds:
                    nv = dict(r.vars)
                    nv[v] = bound - d * direction
                    out.append(State(vars=nv, pre=dict(r.pre)))
        return out

    def _bound_laws(self, prog: Program, tainted: Set[str]) -> Tuple[List, int, int]:
        """Compile monotone + guard-derived rescues into uniform bound laws.
        Returns (laws, n_monotone, n_guarded)."""
        entry_value = self._entry_value_fn(prog)
        laws: List = []
        monotone = self._monotone_rescues(prog, 0, tainted)
        for v, direction, literals in monotone:
            def mono_bound(r: State, _v=v, _dir=direction, _lits=literals):
                ev = entry_value(r, _v)
                if ev is None:
                    return None
                return min([ev] + _lits) if _dir > 0 else max([ev] + _lits)
            laws.append((v, direction, mono_bound))
        guarded = self._guarded_bound_rescues(prog, 0, tainted)
        for v, direction, x_expr, literals in guarded:
            # ceiling law (direction +1 in rescue terms) means v <= X, i.e.
            # bound-law direction -1; entry and reset literals must sit on the
            # sound side of X under this state's inputs
            def guard_bound(r: State, _v=v, _dir=direction, _x=x_expr, _lits=literals):
                bound = eval_int(_x, r)
                ev = entry_value(r, _v)
                if bound is None or ev is None:
                    return None
                if _dir > 0 and (ev > bound or any(lit > bound for lit in _lits)):
                    return None
                if _dir < 0 and (ev < bound or any(lit < bound for lit in _lits)):
                    return None
                return bound
            laws.append((v, -direction, guard_bound))
        return laws, len(monotone), len(guarded)

    @classmethod
    def _guarded_bound_rescues(cls, prog: Program, loop_idx: int, tainted: Set[str]):
        """Guard-derived bound for a TAINTED variable: if every UP-step of v is
        exactly +1 and sits under a guard conjunct `v != X` / `v < X` (or the
        else-arm of `v == X` / `v >= X`), every literal assignment is <= X, and
        the entry value is <= X, then `v <= X` holds inductively — unit steps
        cannot skip over the blocked value.  X must be constant through the
        loop (no modified/tainted identifiers).  Dual for the floor direction.
        Rescues `if (c != n) c = c + 1;` counters whose ceiling the bound
        dimension (disabled under nondet guards) could never witness.
        Returns [(v, direction, bound_expr, literals)]."""
        loop = prog.loops[loop_idx]
        body = prog.source[loop.body_open + 1: loop.body_close]
        scopes = cls._branch_scope_ranges(body)
        braceless = []
        for m in re.finditer(r"\bif\s*\(([^()]*)\)\s*(?!\s*\{)", body):
            stmt_end = body.find(";", m.end())
            if stmt_end >= 0:
                braceless.append((m.group(1), m.end(), stmt_end))

        def norm(t: str) -> str:
            return re.sub(r"\s+", " ", t).strip("() ")

        def conjuncts_at(pos: int) -> List[Tuple[str, bool, Tuple[int, int]]]:
            """(conjunct, negated, guarded-range) facts that dominate `pos`."""
            out: List[Tuple[str, bool, Tuple[int, int]]] = []
            for cond, ranges in scopes:
                for arm, (s, e) in enumerate(ranges):
                    if s <= pos < e:
                        if arm == 0:
                            for part in cond.split("&&"):
                                out.append((norm(part), False, (s, e)))
                        elif "&&" not in cond and "||" not in cond:
                            out.append((norm(cond), True, (s, e)))  # else-arm of a single atom
            for cond, s, e in braceless:
                if s <= pos < e:
                    for part in cond.split("&&"):
                        out.append((norm(part), False, (s, e)))
            return out

        def bound_from(facts, v: str, up: bool) -> List[Tuple[str, Tuple[int, int]]]:
            """(bound expression X, guarded-range) pairs justified by the facts."""
            e = re.escape(v)
            pats_direct = ([rf"{e} != (.+)", rf"{e} < (.+)", rf"(.+) > {e}"] if up
                           else [rf"{e} != (.+)", rf"{e} > (.+)", rf"(.+) < {e}"])
            pats_neg = ([rf"{e} == (.+)", rf"{e} >= (.+)", rf"(.+) <= {e}"] if up
                        else [rf"{e} == (.+)", rf"{e} <= (.+)", rf"(.+) >= {e}"])
            found: List[Tuple[str, Tuple[int, int]]] = []
            for fact, negated, rng in facts:
                for pat in (pats_neg if negated else pats_direct):
                    m = re.fullmatch(pat, fact)
                    if m:
                        found.append((norm(m.group(1)), rng))
            return found

        frozen = [v for v in prog.pre_vars
                  if v not in tainted and v not in cls._assigned_names(body)]
        out = []
        for v, recs in sorted(cls._var_assignments(body, cls._frozen_consts(prog, body)).items()):
            if v not in tainted or v not in prog.pre_vars:
                continue
            if any(kind == "other" for _pos, kind, _val in recs):
                continue
            sites = [(pos, val) for pos, kind, val in recs if kind == "step"]
            literals = [val for _pos, kind, val in recs if kind == "lit"]
            if not sites:
                continue
            all_v_positions = [pos for pos, _k, _v2 in recs]
            for direction in (+1, -1):
                moving = [(p, s) for p, s in sites if s * direction > 0]
                if len(moving) != 1 or abs(moving[0][1]) != 1:
                    # several moving sites can fire in one pass (the guard fact
                    # goes stale between them), and non-unit steps skip the block
                    continue
                pos = moving[0][0]
                for x, (s, _e2) in bound_from(conjuncts_at(pos), v, direction > 0):
                    # the guard fact must still hold when the step runs: no other
                    # assignment to v between the guard's scope start and the step
                    if any(s <= q < pos for q in all_v_positions if q != pos):
                        continue
                    # X must be frozen during the loop: identifiers all unmodified
                    ids = set(re.findall(r"[A-Za-z_]\w*", x))
                    if ids and ids <= set(frozen):
                        out.append((v, direction, x, literals))
                        break
        return out

    def _rigid_pair_negatives(self, pairs, bases: List[State]) -> List[State]:
        """Perturbations off a conserved line `cw·v − cv·w == const` — sound by
        construction, no density/novelty requirement needed."""
        out: List[State] = []
        for v, w, cv, cw in pairs:
            for r in bases:
                base = r.vars
                if v not in base or w not in base:
                    continue
                for d in _SMALL_DELTAS:
                    for dv, dw in ((d, 0), (0, d), (d, -d), (d, d)):
                        if cw * dv - cv * dw == 0:
                            continue          # on the conserved line
                        nv = dict(base); nv[v] += dv; nv[w] += dw
                        out.append(State(vars=nv, pre=dict(r.pre)))
        return out

    def _lattice_negatives(self, rescues, bases: List[State]) -> List[State]:
        """Perturbations off a conserved lattice `v ≡ v_entry (mod g)` — sound by
        construction (the base is reachable, so it sits on the lattice; any
        off-lattice step is unreachable under every branch sequence)."""
        out: List[State] = []
        for v, g in rescues:
            deltas = [d for d in (1, -1, 2, -2, 4, -4, 5, -5, 7, -7) if d % g != 0][:8]
            for r in bases:
                if v not in r.vars:
                    continue
                for d in deltas:
                    nv = dict(r.vars); nv[v] += d
                    out.append(State(vars=nv, pre=dict(r.pre)))
        return out

    @staticmethod
    def _body_nondeterministic(prog: Program, loop_idx: int = 0) -> bool:
        """`unknown()` INSIDE the body means the state graph branches: the same
        prefix can reach states no single observed trace shows, so perturbations
        that merely RECOMBINE observed coordinate values may hit an unobserved
        branch (reachable!) and must not be labeled negative."""
        loop = prog.loops[loop_idx]
        body = prog.source[loop.body_open + 1: loop.body_close]
        return bool(re.search(r"\bunknown\w*\s*\(", body))

    @staticmethod
    def _bases(positives: List[State],
               dense_index: Optional[Set[Tuple[int, int]]] = None) -> List[State]:
        """Stratified subsample across ALL positives (not just the first trace).

        When `dense_index` is given, only DENSE bases (full forward trace window
        sampled) are eligible: on long throttled traces most positives have no
        sampled window, so blind stratification wastes nearly the whole base
        budget on states that produce zero relation negatives — leaving a
        negative pool small enough for a pointwise farm to memorize."""
        if dense_index is not None:
            eligible = [s for s in positives
                        if s.run >= 0 and all((s.run, s.it + k) in dense_index
                                              for k in range(1, _DENSE_WINDOW + 1))]
            if eligible:
                positives = eligible
        if len(positives) <= _BASE_CAP:
            return positives
        step = len(positives) // _BASE_CAP
        return positives[::step][:_BASE_CAP]

    def _entry_feasible_fn(self, prog: Program) -> Callable[[State], bool]:
        """A perturbed state that could be a FRESH LOOP ENTRY is reachable (just
        pick those inputs), so it must never be labeled negative.  Entry shape:
        every param equals its own pre value, every literal-init local equals its
        init (evaluated over the state), and the requires holds."""
        # locals with a nondeterministic entry value are FREE at entry (any
        # value could be the draw) — no equality check, like params
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
                if ok is not True:      # mismatch, or undecidable -> not entry-shaped
                    return False
            if req and eval_predicate(req, s) is False:
                return False
            return True

        return feasible

    def _relation_negatives(self, movable: List[str], bases: List[State],
                            dense_index: Set[Tuple[int, int]],
                            novel_only: Optional[Dict[str, Set[int]]] = None) -> List[State]:
        """Small single-axis + pairwise steps from DENSE bases.  Density (the next
        `_DENSE_WINDOW` trace states are sampled) guarantees that a perturbation
        surviving the reachable-set exclusion is genuinely off-manifold rather
        than an unsampled trace neighbor.

        `novel_only` (per-var observed value sets) is passed for programs with a
        NONDETERMINISTIC body: there the state graph branches, and a perturbation
        that merely recombines observed coordinate values may sit on an
        unobserved branch (reachable).  Such candidates are kept only when some
        perturbed coordinate takes a value never observed for that variable."""
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
                    for d in (1, -1, 2, -2, 3, -3):
                        for su, sw in ((d, d), (d, -d)):
                            if not (novel(u, base[u] + su) or novel(w, base[w] + sw)):
                                continue
                            nv = dict(base); nv[u] += su; nv[w] += sw
                            out.append(State(vars=nv, pre=dict(r.pre)))
        return out

    def _escape_negatives(self, movable: List[str], bases: List[State],
                          positives: List[State]) -> List[State]:
        """Large ladder steps kept only when they leave the variable's sampled
        range.  Since full traces are collected up to the genuine exit, the
        sampled range equals the true reachable range, so escapees are truly
        unreachable.  The many distinct escaped values (one ladder per base)
        make pointwise `v != k` farms uneconomical."""
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

    # Hundreds of negatives sharing one off-manifold coordinate value are
    # redundant evidence AND a fat target: one `v != k` clause kills the whole
    # slice.  Capping farm-TARGETABLE slices (values a diseq can use — those
    # never observed positive; positive-valued coordinates are farm-immune
    # since the clause would be unsound) bounds any 32-atom farm to
    # 32 * _SLICE_CAP diversified traces without losing distinct evidence.
    _SLICE_CAP = 6

    def _slice_diverse(self, states: List[State], positives: List[State],
                       counts: Optional[Dict[Tuple[str, int], int]] = None) -> List[State]:
        pos_vals: Dict[str, Set[int]] = {}
        for p in positives:
            for v, val in p.vars.items():
                pos_vals.setdefault(v, set()).add(val)
        if counts is None:
            counts = {}
        out: List[State] = []
        for s in states:
            targetable = [(v, val) for v, val in s.vars.items()
                          if val not in pos_vals.get(v, ())]
            if any(counts.get(kv, 0) >= self._SLICE_CAP for kv in targetable):
                continue
            for kv in targetable:
                counts[kv] = counts.get(kv, 0) + 1
            out.append(s)
        return out

    # A negative rejected by an invariant falls in one of two dimensions:
    #  * relation-breaking (off any reachable manifold)  — ABUNDANT;
    #  * bound-breaking (relation holds, range violated) — SCARCER.
    # The reward = fraction rejected, so if one dimension dominates the count the
    # reward misrepresents quality (a relation-only invariant would score ~99%
    # while missing every bound).  We BALANCE the two: keep every bound negative
    # (over-run + box-escape) and cap the relation ones to `_RELATION_PER_BOUND×`
    # them, so bounds carry a meaningful, program-independent share of the reward.
    _RELATION_PER_BOUND = 2

    def _negatives(self, prog: Program, positives: List[State], overrun: List[State],
                   raw_reach: List[State], capped: bool) -> Tuple[List[State], List[List[int]], dict]:
        movable = self._modified_vars(prog, 0)
        if not movable:   # fallback if the body write couldn't be detected syntactically
            movable = [v for v in prog.pre_vars if v not in set(prog.params)] or list(prog.pre_vars)

        reachable = {s.vars_key() for s in positives}
        entry_feasible = self._entry_feasible_fn(prog)
        seen: set = set()

        def keep(states: List[State]) -> List[State]:
            out = []
            for s in states:
                k = s.vars_key()
                if k in reachable or k in seen:   # keep only UNREACHABLE, deduped
                    continue
                if entry_feasible(s):             # reachable as a fresh entry -> not a negative
                    continue
                seen.add(k)
                out.append(s)
            return out

        nondet_body = self._body_nondeterministic(prog, 0)
        tainted = self._nondet_tainted(prog, 0)
        # a guard referencing a branch-dependent var makes the iteration count
        # itself nondeterministic — no sampled range is sound then
        guard = prog.loops[0].guard or ""
        nondet = (self._guard_nondeterministic(prog, 0)
                  or any(re.search(rf"\b{re.escape(t)}\b", guard) for t in tainted))
        dense_index = {(s.run, s.it) for s in raw_reach if s.run >= 0}
        bases = self._bases(positives)                     # escape / rigid / lattice
        dense_bases = self._bases(positives, dense_index)  # relation (needs the window)
        # branch-dependent (nondet-tainted) variables have envelope-valued
        # reachable sets a finite sample cannot cover — never perturb them
        movable = [v for v in movable if v not in tainted]
        novel_only = None
        if nondet_body:
            novel_only = {v: {p.vars[v] for p in positives} for v in movable}

        # bound dimension first (scarce, kept whole).  Each over-run RUN is ONE
        # impossible trace — the whole past-the-exit continuation is a single
        # history, so its states form one witness group instead of inflating
        # the count with per-state credit; each escape is its own history.
        bound: List[State] = []
        bound_groups: List[List[int]] = []
        slice_counts: Dict[Tuple[str, int], int] = {}   # shared across dimensions
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
                escapes = self._slice_diverse(
                    keep(self._escape_negatives(movable, bases, positives)), positives,
                    counts=slice_counts)
                for s in escapes:
                    bound_groups.append([len(bound)])
                    bound.append(s)
                    n_escape += 1

        relation_candidates = self._relation_negatives(movable, dense_bases, dense_index, novel_only)
        rigid = self._rigid_pairs(prog, 0, tainted) if tainted else []
        if rigid:
            relation_candidates = relation_candidates + self._rigid_pair_negatives(rigid, bases)
        lattice = self._lattice_rescues(prog, 0, tainted) if tainted else []
        if lattice:
            relation_candidates = relation_candidates + self._lattice_negatives(lattice, bases)
        bound_laws, n_monotone, n_guarded = (self._bound_laws(prog, tainted)
                                             if tainted else ([], 0, 0))
        if bound_laws:
            relation_candidates = relation_candidates + self._bound_negatives(bound_laws, bases)
        relation = self._slice_diverse(keep(relation_candidates), positives,
                                       counts=slice_counts)
        # balance in TRACE units: each relation state is one impossible history
        cap = self._RELATION_PER_BOUND * len(bound_groups)
        if bound_groups and len(relation) > cap:
            step = len(relation) // cap                         # deterministic stride subsample
            relation = relation[::step][:cap]

        negatives = bound + relation
        groups = bound_groups + [[len(bound) + i] for i in range(len(relation))]
        stats = {
            "proposals": len(groups),
            "n_traces": len(groups),
            "n_witness_states": len(negatives),
            "relation": len(relation),
            "bound_overrun": n_over_traces,
            "bound_escape": n_escape,
            "capped": capped,
            "nondet_guard": nondet,
            "rigid_pairs": len(rigid),
            "lattice_rescues": len(lattice),
            "monotone_rescues": n_monotone,
            "guarded_rescues": n_guarded,
            # legacy keys (older dashboards):
            "frontier": len(relation),
            "overrun": n_over_traces,
        }
        return negatives, groups, stats

    # ── driver ───────────────────────────────────────────────────────────────
    def sample(self) -> ExampleSet:
        prog = parse_program(self.source)
        es = ExampleSet(program=prog)
        for loop_idx in range(len(prog.loops)):
            # nondeterministic bodies branch: double the runs for branch coverage
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
        print(f"\nloop {li}: positives(reachable)={st['n_pos']} negatives(unreachable)={st['n_neg']} "
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
