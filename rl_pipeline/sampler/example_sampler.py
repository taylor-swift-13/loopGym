"""
ExampleSampler — Component 1.

Produces, per loop, a set of loop-ENTRY valuations:
  * positives : reachable states (from executing the correct program)
  * negatives : "must-exclude" states — a correct invariant, together with the
                negated guard, must imply the postcondition, so any state with
                (¬guard ∧ ¬post) MUST be excluded by the invariant.

Negatives are generated from three proposal distributions and then filtered by
one uniform, spec-derived acceptance test:

    accept(s) := (s not reachable) ∧ ¬guard(s) ∧ ¬post(s)

Proposals:
  - random       : broad domain sweep over the loop-entry variables
  - mutation-loop: run realistically-mutated programs, take their loop-entry states
  - mutation-trace: perturb reachable states (near-miss)

Because the acceptance test is spec-derived (not "trust whatever a wrong program
printed"), the negatives are representative by construction — mutation only steers
the proposals toward realistic near-misses.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..common.program import Program, parse_program
from ..common.state import State, eval_predicate
from . import cexec, mutators


@dataclass
class ExampleSet:
    program: Program
    positives: Dict[int, List[State]] = field(default_factory=dict)
    negatives: Dict[int, List[State]] = field(default_factory=dict)
    stats: Dict[int, dict] = field(default_factory=dict)

    def pos(self, loop_idx: int = 0) -> List[State]:
        return self.positives.get(loop_idx, [])

    def neg(self, loop_idx: int = 0) -> List[State]:
        return self.negatives.get(loop_idx, [])


class ExampleSampler:
    def __init__(
        self,
        source: str,
        n_runs: int = 16,
        n_random: int = 3000,
        max_loop_mutants: int = 20,
        mutant_runs: int = 3,
        seed: int = 0,
        logger: Optional[logging.Logger] = None,
    ):
        self.source = source
        self.n_runs = n_runs
        self.n_random = n_random
        self.max_loop_mutants = max_loop_mutants
        self.mutant_runs = mutant_runs
        self.seed = seed
        self.log = logger or logging.getLogger("rl_pipeline.sampler")

    # ── positives ────────────────────────────────────────────────────────────
    def _positives(self, prog: Program, loop_idx: int) -> List[State]:
        states = cexec.collect_reachable(prog, loop_idx=loop_idx, n_runs=self.n_runs, seed=self.seed)
        # dedup by vars
        seen, out = set(), []
        for s in states:
            k = s.vars_key()
            if k not in seen:
                seen.add(k)
                out.append(s)
        return out

    # ── negatives ────────────────────────────────────────────────────────────
    def _is_hard_negative(self, s: State, guard: str, post: str) -> bool:
        g = eval_predicate(guard, s)
        p = eval_predicate(post, s)
        # need ¬guard ∧ ¬post, both must be decidable
        return (g is False) and (p is False)

    def _random_candidates(self, prog: Program, loop_idx: int) -> List[State]:
        cons = cexec.param_constraints(prog.requires, prog.pre_vars)
        # widen locals (not just params) to broad range
        for v in prog.pre_vars:
            cons.setdefault(v, {"min": -64, "max": 64})
        cands: List[State] = []
        rows = cexec.sample_inputs(prog.pre_vars, cons, self.n_random, seed=self.seed + 1)
        for row in rows:
            pre = {p: row[p] for p in prog.params if p in row}
            cands.append(State(vars=dict(row), pre=pre))
        return cands

    @staticmethod
    def _guard_post_constants(prog: Program) -> List[int]:
        consts = {0, 1, -1}
        for txt in (prog.loops[0].guard, prog.post):
            for m in re.finditer(r"-?\d+", txt or ""):
                try:
                    consts.add(int(m.group()))
                except ValueError:
                    pass
        return sorted(consts)

    def _boundary_candidates(self, prog: Program, loop_idx: int) -> List[State]:
        """Sample valuations focused around/beyond the guard & post constants, so the
        ¬guard∧¬post region is reached even when its bounds lie far outside the
        generic domain (e.g. `y < 100000`, `x == 100`).  Params stay within their
        `requires` domain; locals/modified vars range freely over the boundary pool."""
        consts = self._guard_post_constants(prog)
        pool = sorted({c + d for c in consts for d in (-2, -1, 0, 1, 2)} | set(cexec._TIERS))
        cons = cexec.param_constraints(prog.requires, prog.params)
        params = set(prog.params)
        cands: List[State] = []
        n = min(self.n_random, 1500)
        for r in range(n):
            row: Dict[str, int] = {}
            for j, v in enumerate(prog.pre_vars):
                val = pool[(r * 7 + j * 13 + self.seed) % len(pool)]
                if v in params:
                    lo = cons.get(v, {}).get("min", -64)
                    hi = cons.get(v, {}).get("max", 64)
                    val = max(lo, min(hi, val))
                row[v] = int(val)
            pre = {p: row[p] for p in prog.params if p in row}
            cands.append(State(vars=dict(row), pre=pre))
        return cands

    def _exit_boundary_negatives(self, prog: Program, loop_idx: int, positives: List[State]) -> List[State]:
        """Guaranteed WITNESS negatives adjacent to every reachable exit state.

        For a correct proof we need `I ∧ ¬guard ⟹ post`.  The hardest witnesses of
        an insufficient (too-weak) invariant are the states right next to a true
        exit state `e` (which satisfies `¬guard ∧ post`) that flip post to false.
        We perturb the post-variables of each exit positive while keeping the loop
        guard false, so any invariant that is sound but not tight at the exit
        boundary is robustly caught — giving `reject-all-negatives` a real margin."""
        guard, post = prog.loops[loop_idx].guard, prog.post
        if not post:
            return []
        post_vars = [v for v in prog.pre_vars if re.search(r"\b" + re.escape(v) + r"\b", post)]
        if not post_vars:
            return []
        exit_states = [s for s in positives if eval_predicate(guard, s) is False]
        deltas = (1, -1, 2, -2, 3, -3, 5, -5, 7, -7)
        out: List[State] = []
        for e in exit_states:
            for v in post_vars:
                for d in deltas:
                    nv = dict(e.vars)
                    nv[v] = nv[v] + d
                    out.append(State(vars=nv, pre=dict(e.pre)))
            for d in (1, -1, 2, -2):  # joint perturbation of all post-vars
                nv = dict(e.vars)
                for v in post_vars:
                    nv[v] = nv[v] + d
                out.append(State(vars=nv, pre=dict(e.pre)))
        return out

    def _mutation_loop_candidates(self, prog: Program, loop_idx: int) -> List[State]:
        cands: List[State] = []
        for msrc in mutators.mutate_loop(prog, loop_idx, self.max_loop_mutants):
            try:
                mprog = parse_program(msrc)
            except ValueError:
                continue
            if mprog.pre_vars != prog.pre_vars:
                continue
            try:
                states = cexec.collect_reachable(
                    mprog, loop_idx=loop_idx, n_runs=self.mutant_runs, seed=self.seed + 2
                )
            except Exception:
                states = []
            cands.extend(states)
        return cands

    def _negatives(self, prog: Program, loop_idx: int, positives: List[State]) -> (List[State], dict):
        guard, post = prog.loops[loop_idx].guard, prog.post
        pos_keys = {s.vars_key() for s in positives}
        stats = {"proposals": 0, "random": 0, "boundary": 0, "mut_loop": 0, "mut_trace": 0}

        if not post:
            self.log.warning("no postcondition; cannot derive spec negatives for loop %d", loop_idx)

        proposals: List[State] = []
        rand = self._random_candidates(prog, loop_idx)
        proposals += [("random", s) for s in rand]
        proposals += [("random", s) for s in self._boundary_candidates(prog, loop_idx)]
        proposals += [("boundary", s) for s in self._exit_boundary_negatives(prog, loop_idx, positives)]
        mloop = self._mutation_loop_candidates(prog, loop_idx)
        proposals += [("mut_loop", s) for s in mloop]
        mtrace = mutators.mutate_traces(positives)
        proposals += [("mut_trace", s) for s in mtrace]
        stats["proposals"] = len(proposals)

        seen, negatives = set(), []
        for kind, s in proposals:
            k = s.vars_key()
            if k in pos_keys or k in seen:
                continue
            if post and self._is_hard_negative(s, guard, post):
                seen.add(k)
                negatives.append(s)
                stats[kind] += 1
        return negatives, stats

    # ── driver ───────────────────────────────────────────────────────────────
    def sample(self) -> ExampleSet:
        prog = parse_program(self.source)
        es = ExampleSet(program=prog)
        for loop_idx in range(len(prog.loops)):
            positives = self._positives(prog, loop_idx)
            es.positives[loop_idx] = positives
            if loop_idx == 0:  # negatives derived from program post (final assertion)
                negatives, stats = self._negatives(prog, loop_idx, positives)
                es.negatives[loop_idx] = negatives
                es.stats[loop_idx] = {"n_pos": len(positives), "n_neg": len(negatives), **stats}
            else:
                es.negatives[loop_idx] = []
                es.stats[loop_idx] = {"n_pos": len(positives), "n_neg": 0}
        return es


def _cli():
    import argparse

    ap = argparse.ArgumentParser(description="Sample positive/negative loop-entry valuations")
    ap.add_argument("program", help="path to a C program")
    ap.add_argument("--runs", type=int, default=16)
    ap.add_argument("--random", type=int, default=3000)
    ap.add_argument("--mutants", type=int, default=20)
    ap.add_argument("--show", type=int, default=6, help="print N example states each")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    src = open(args.program).read()
    es = ExampleSampler(src, n_runs=args.runs, n_random=args.random, max_loop_mutants=args.mutants).sample()
    print(f"program: {es.program.func_name}  guard: {es.program.loop.guard!r}  post: {es.program.post!r}")
    for li in sorted(es.positives):
        st = es.stats[li]
        print(f"\nloop {li}: positives={st['n_pos']} negatives={st['n_neg']} "
              f"(proposals={st.get('proposals','-')}, "
              f"random={st.get('random','-')}, mut_loop={st.get('mut_loop','-')}, mut_trace={st.get('mut_trace','-')})")
        print("  positives:")
        for s in es.pos(li)[:args.show]:
            print("    +", s.render())
        print("  negatives:")
        for s in es.neg(li)[:args.show]:
            print("    -", s.render())


if __name__ == "__main__":
    _cli()
