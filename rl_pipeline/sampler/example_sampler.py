"""
ExampleSampler — Component 1.

The sampler sees ONLY the loop (it executes it) — never the assert/postcondition.

A *trace* is the group of loop-HEAD variable valuations one execution passes
through.  Running the loop from many inputs yields many traces; their union is
the REACHABLE set.  Per loop we produce:
  * positives : reachable loop-head valuations (the states of real traces)
  * negatives : loop-head valuations NO trace can produce (UNREACHABLE states)

    accept(s) := s is not reachable          (decided purely by execution)

The strongest invariant is the tightest characterization of the reachable set:
sound on every positive, rejecting as many unreachable states as possible.  Hard
negatives sit just off the reachable frontier — obtained by perturbing reachable
states (parameters fixed) and keeping the perturbations that are not reachable:
  - single-axis steps leave any reachable manifold (linear OR nonlinear, e.g.
    z==x*y) → expose a missing relational law;
  - joint pairwise steps stay on a linear manifold but leave the reachable
    segment → expose a missing bound (e.g. 0<=x).
No assert, no guard, no postcondition, no program mutation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..common.program import Program, parse_program
from ..common.state import State
from . import cexec

# Canonical sampler defaults — the SINGLE source of truth shared by BOTH the
# reward service (training) and the inference framework, so training and
# inference sample identically.  n_runs = how many executions define the reachable
# set (more runs = tighter reachability approximation).  Override only for experiments.
DEFAULT_N_RUNS = 8
DEFAULT_SEED = 0


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
        n_runs: int = DEFAULT_N_RUNS,
        seed: int = DEFAULT_SEED,
        logger: Optional[logging.Logger] = None,
    ):
        self.source = source
        self.n_runs = n_runs
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
    # The sampler sees ONLY the loop — never the assert/postcondition.  A negative
    # is a loop-ENTRY valuation the loop CANNOT produce (an UNREACHABLE state);
    # reachability is decided purely by execution (the sampled reachable set).
    # The strongest invariant is the tightest characterization of the reachable
    # set: sound on every positive, rejecting as many unreachable states as it can.
    def _frontier_negatives(self, prog: Program, positives: List[State],
                            reachable: set) -> List[State]:
        """Hard negatives sit just off the reachable frontier.  Perturb each
        reachable state's MODIFIED variables (parameters kept fixed, so the
        perturbation stays at a sampled parameter setting and is reliably
        unreachable):
          * single-axis steps leave any reachable manifold (e.g. z==x*y, x+y==n)
            → expose a missing relational law;
          * joint pairwise steps (same-sign preserves differences, opposite-sign
            preserves sums) stay on a LINEAR manifold but leave the reachable
            segment → expose a missing bound (e.g. 0<=x)."""
        params = set(prog.params)
        movable = [v for v in prog.pre_vars if v not in params]
        if not movable:
            return []
        deltas = (1, -1, 2, -2, 3, -3, 5, -5, 7, -7)
        out: List[State] = []
        for r in positives[:80]:
            base = r.vars
            for v in movable:
                for d in deltas:
                    nv = dict(base); nv[v] = nv[v] + d
                    out.append(State(vars=nv, pre=dict(r.pre)))
            for i in range(len(movable)):
                for j in range(i + 1, len(movable)):
                    u, w = movable[i], movable[j]
                    for d in (1, -1, 2, -2, 3, -3):
                        for su, sw in ((d, d), (d, -d)):
                            nv = dict(base); nv[u] += su; nv[w] += sw
                            out.append(State(vars=nv, pre=dict(r.pre)))
        return out

    def _negatives(self, prog: Program, loop_idx: int, positives: List[State]) -> (List[State], dict):
        reachable = {s.vars_key() for s in positives}
        proposals = self._frontier_negatives(prog, positives, reachable)
        stats = {"proposals": len(proposals), "frontier": 0}
        seen, negatives = set(), []
        for s in proposals:
            k = s.vars_key()
            if k in reachable or k in seen:   # keep only UNREACHABLE, deduped
                continue
            seen.add(k)
            negatives.append(s)
            stats["frontier"] += 1
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
              f"(frontier proposals={st.get('proposals','-')})")
        print("  positives:")
        for s in es.pos(li)[:args.show]:
            print("    +", s.render())
        print("  negatives:")
        for s in es.neg(li)[:args.show]:
            print("    -", s.render())


if __name__ == "__main__":
    _cli()
