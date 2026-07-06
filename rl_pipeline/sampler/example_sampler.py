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
import re
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
    # The sampler sees ONLY the loop — never the assert/postcondition.  A negative
    # is a loop-ENTRY valuation the loop CANNOT produce (an UNREACHABLE state);
    # reachability is decided purely by execution (the sampled reachable set).
    # The strongest invariant is the tightest characterization of the reachable
    # set: sound on every positive, rejecting as many unreachable states as it can.
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

    def _frontier_negatives(self, prog: Program, positives: List[State],
                            reachable: set) -> List[State]:
        """Hard negatives sit just off the reachable frontier.  Perturb each
        reachable state's MODIFIED variables (loop never-written vars stay fixed, so
        the perturbation is reliably unreachable):
          * single-axis steps leave any reachable manifold (e.g. z==x*y, x+y==n)
            → expose a missing relational law;
          * joint pairwise steps (same-sign preserves differences, opposite-sign
            preserves sums) stay on a LINEAR manifold but leave the reachable
            segment → expose a missing bound (e.g. 0<=x)."""
        movable = self._modified_vars(prog, 0)
        if not movable:   # fallback if the body write couldn't be detected syntactically
            movable = [v for v in prog.pre_vars if v not in set(prog.params)] or list(prog.pre_vars)
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

    def _negatives(self, prog: Program, positives: List[State],
                   overrun: List[State]) -> (List[State], dict):
        reachable = {s.vars_key() for s in positives}
        # frontier: pure-arithmetic perturbations off the reachable set;
        # overrun: real body-dynamics past the exit (relation-preserving, out of bounds)
        proposals = [("frontier", s) for s in self._frontier_negatives(prog, positives, reachable)]
        proposals += [("overrun", s) for s in overrun]
        stats = {"proposals": len(proposals), "frontier": 0, "overrun": 0}
        seen, negatives = set(), []
        for kind, s in proposals:
            k = s.vars_key()
            if k in reachable or k in seen:   # keep only UNREACHABLE, deduped
                continue
            seen.add(k)
            negatives.append(s)
            stats[kind] += 1
        return negatives, stats

    # ── driver ───────────────────────────────────────────────────────────────
    def sample(self) -> ExampleSet:
        prog = parse_program(self.source)
        es = ExampleSet(program=prog)
        for loop_idx in range(len(prog.loops)):
            reach, overrun = cexec.collect_traces(prog, loop_idx=loop_idx,
                                                  n_runs=self.n_runs, seed=self.seed)
            positives = self._dedup(reach)
            es.positives[loop_idx] = positives
            if loop_idx == 0:
                negatives, stats = self._negatives(prog, positives, overrun)
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
