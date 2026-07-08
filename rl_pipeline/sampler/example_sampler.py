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
from ..common.state import State, eval_predicate
from . import cexec

# Canonical sampler defaults — the SINGLE source of truth shared by BOTH the
# reward service (training) and the inference framework, so training and
# inference sample identically.  n_runs = how many executions define the reachable
# set (more runs = tighter reachability approximation).  Override only for experiments.
DEFAULT_N_RUNS = 12
DEFAULT_SEED = 0

# relation dimension: small steps, verifiable against the dense trace window.
# Deliberately SHORT (±1, ±2): d=1 tests the exact boundary of a law, d=2 the
# first approximation; anything larger adds no discrimination but fattens the
# near cluster that window-exclusion farms feed on (the relation pool is capped,
# so near mass directly displaces the anti-window far mass)
_SMALL_DELTAS = (1, -1, 2, -2)
# bound dimension: large ladder steps, kept only when they escape the sampled
# range.  Deliberately SHORT (10 deltas ≤ 34): every ladder escapee lands within
# ±34 of the range edge — inside any 2-atom window — so the ladder must not
# outweigh the decade-spread far escapes in _escape_negatives (near:far ≈ 1:1)
_LADDER_DELTAS = (5, -5, 8, -8, 13, -13, 21, -21, 34, -34)
_BASE_CAP = 96           # perturbation bases, stratified across all positives
# Forward trace states required for a "dense" base.  Must be max(|small delta|)+1:
# the entry state (it=0) and the first head (it=1) carry the SAME valuation (the
# head prints BEFORE the body runs), so a value-jump of 2 along a unit-step
# manifold is only witnessed by the state at it+3 — a shorter window lets
# frontier perturbations from short runs land on the unsampled next-in-trace
# state (a mislabel).
_DENSE_WINDOW = 3


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

    # ── seed-hashed placement (the SINGLE source for every negative family) ──
    #
    # Negative VALUES must be unpredictable to a policy trained on the fixed
    # canonical seeds, on two scales:
    #   * exact position (defeats pointwise `v != k` farms): hash per seed;
    #   * cluster window (defeats interval farms `!(a <= v && v <= b)`, which
    #     survive position hashing as long as all offsets stay small): spread
    #     offsets over decades up to ~1e6 (cube-safe) — no clause budget of
    #     bounded windows covers every decade on every seed, while a true law
    #     (`v >= bound`, `x - y == c`) rejects at any distance.
    # FAR offsets must carry weight comparable to near ones in every family:
    # near offsets inevitably cluster inside a two-atom window of the boundary
    # in EVERY derived expression space (v, v+w, v−w, …), so a near-majority
    # pool hands most of its mass to a narrow window exclusion.

    _FAR_DECADES = (100, 300, 1000, 10000, 100000, 300000)

    def _hashed(self, salt: int, k: int, lo: int, span: int) -> int:
        return lo + (self.seed * 31337 + salt * 7919 + k * 104729) % span

    def _far_deltas(self, n: int = 6, salt: int = 0) -> List[int]:
        """`n` far offsets, one per decade (cycling), position hashed per seed."""
        return [self._hashed(salt, i, d, 2 * d)
                for i, d in ((i, self._FAR_DECADES[i % len(self._FAR_DECADES)])
                             for i in range(n))]

    def _axis_spread(self, bases: List[State], axes_of: Callable[[State], List[str]],
                     values_of: Callable[[State, str, int], Tuple[int, ...]],
                     per_base: int = 1) -> List[State]:
        """The one emitter behind every FAR negative family: for each base and
        each of `per_base` seed-hashed far offsets, replace one axis's value
        with `values_of(base, axis, offset)`.  Families differ only in their
        axis list and value rule (relative to base / range edge)."""
        far = self._far_deltas()
        out: List[State] = []
        for i, r in enumerate(bases):
            for j in range(per_base):
                f = far[(i * per_base + j) % len(far)] + i * per_base + j
                for v in axes_of(r):
                    for val in values_of(r, v, f):
                        nv = dict(r.vars); nv[v] = val
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
                    for d in _SMALL_DELTAS:
                        for su, sw in ((d, d), (d, -d)):
                            if not (novel(u, base[u] + su) or novel(w, base[w] + sw)):
                                continue
                            nv = dict(base); nv[u] += su; nv[w] += sw
                            out.append(State(vars=nv, pre=dict(r.pre)))
        return out

    @staticmethod
    def _complete_runs(raw_reach: List[State]) -> Set[int]:
        """Runs whose observed states are the COMPLETE reachable set for their
        input (only meaningful for deterministic programs): the run either
        exited within the dense print prefix (every state printed), or a state
        REPEATED inside the prefix — the orbit is closed, so the observed
        prefix is the whole reachable set even on capped non-terminating runs."""
        per_run: Dict[int, List[State]] = {}
        for s in raw_reach:
            if s.run >= 0:
                per_run.setdefault(s.run, []).append(s)
        ok: Set[int] = set()
        for run, states in per_run.items():
            if max(s.it for s in states) < cexec._PRINT_DENSE:
                ok.add(run)                             # exited, fully printed
                continue
            seen_keys: set = set()
            for s in sorted(states, key=lambda t: t.it):
                if s.it >= cexec._PRINT_DENSE:
                    break
                k = s.vars_key()
                if k in seen_keys:
                    ok.add(run)                         # closed orbit
                    break
                seen_keys.add(k)
        return ok

    def _far_relation_negatives(self, movable: List[str], bases: List[State]) -> List[State]:
        """FAR single-axis perturbations, only for bases of COMPLETE runs (see
        _complete_runs): there the observed states are the whole reachable set
        for that input, so an unobserved valuation is unreachable at ANY
        distance — no density window needed.  Spreads the relation dimension,
        whose small deltas cluster within ±3 of the manifold in every
        conserved-expression space (x−y, x+y, …)."""
        # at least 2 offsets per base (more on small pools), so the far band
        # carries weight against the near cluster in every expression space
        per_base = max(2, 64 // max(1, len(bases)))
        return self._axis_spread(bases, lambda r: movable,
                                 lambda r, v, f: (r.vars[v] + f, r.vars[v] - f),
                                 per_base=per_base)

    def _escape_negatives(self, movable: List[str], bases: List[State],
                          positives: List[State],
                          run_ranges: Optional[Dict[int, Dict[str, Tuple[int, int]]]] = None
                          ) -> List[State]:
        """Ladder + far steps kept only when they leave the variable's sampled
        range.  Since full traces are collected up to the genuine exit, the
        sampled range equals the true reachable range, so escapees are truly
        unreachable — at ANY distance.  The near ladder gives many distinct
        escaped values (defeats pointwise `v != k` farms); the far offsets
        spread escapees over decades (defeats bounded-window interval farms).

        Escapes anchor at the base's own RUN range when that run is complete
        (`run_ranges`), else at the global range, and far escapes for complete
        runs land INSIDE the gap between the run's range and the global range.
        The gap placement wins on both fronts at once:
          * it starves input-envelope boxes — an escape at x = run_hi(n=5)+f
            sits inside the global envelope, so `x <= global_max` cannot
            reject it while the true input-relative bound `x <= n` can;
          * it is farm-immune for free — gap values are positive-observed
            under OTHER inputs, so any single-var window/diseq covering them
            is unsound on the sample and dies in the exact filter.
        Runs sitting at the global edge (no gap) fall back to beyond-global
        decade offsets."""
        lo = {v: min(p.vars[v] for p in positives) for v in movable}
        hi = {v: max(p.vars[v] for p in positives) for v in movable}
        run_ranges = run_ranges or {}

        def bounds(r: State, v: str) -> Tuple[int, int]:
            rr = run_ranges.get(r.run, {}).get(v)
            return rr if rr is not None else (lo[v], hi[v])

        out: List[State] = []
        for r in bases:
            base = r.vars
            for v in movable:
                b_lo, b_hi = bounds(r, v)
                for d in _LADDER_DELTAS:
                    nv_val = base[v] + d
                    if b_lo <= nv_val <= b_hi:
                        continue
                    nv = dict(base); nv[v] = nv_val
                    out.append(State(vars=nv, pre=dict(r.pre)))

        def far_vals(r: State, v: str, f: int) -> Tuple[int, int]:
            r_lo, r_hi = bounds(r, v)
            up = r_hi + 1 + (f % (hi[v] - r_hi)) if r_hi < hi[v] else hi[v] + f
            dn = r_lo - 1 - (f % (r_lo - lo[v])) if r_lo > lo[v] else lo[v] - f
            return (up, dn)

        return out + self._axis_spread(bases, lambda r: movable, far_vals, per_base=2)

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
        bases = self._bases(positives)                     # escape / far-relation
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
                # per-run ranges for COMPLETE runs of deterministic programs:
                # escapes anchored at the run's OWN range are still provably
                # unreachable for that run's inputs, but only an INPUT-RELATIVE
                # bound (x <= n) rejects them — an input-envelope box
                # (x <= global_max) does not, so boxes starve (see
                # _escape_negatives)
                run_ranges: Dict[int, Dict[str, Tuple[int, int]]] = {}
                if not re.search(r"\bunknown\w*\s*\(", prog.source):
                    complete = self._complete_runs(raw_reach)
                    for p in positives:
                        if p.run in complete:
                            rr = run_ranges.setdefault(p.run, {})
                            for v in movable:
                                if v in p.vars:
                                    lo_hi = rr.get(v)
                                    val = p.vars[v]
                                    rr[v] = ((val, val) if lo_hi is None else
                                             (min(lo_hi[0], val), max(lo_hi[1], val)))
                escapes = self._slice_diverse(
                    keep(self._escape_negatives(movable, bases, positives, run_ranges)),
                    positives, counts=slice_counts)
                for s in escapes:
                    bound_groups.append([len(bound)])
                    bound.append(s)
                    n_escape += 1

        relation_candidates = self._relation_negatives(movable, dense_bases, dense_index, novel_only)
        if not re.search(r"\bunknown\w*\s*\(", prog.source):
            far_bases = [b for b in bases if b.run in self._complete_runs(raw_reach)]
            relation_candidates = relation_candidates + self._far_relation_negatives(
                movable, far_bases)
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
