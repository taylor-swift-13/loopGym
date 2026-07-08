"""
Gold-free hackability sweep over the FULL benchmark suite.

The discrimination harness proves hack-resistance on the programs with
hand-written gold; this sweep proves the ANTI-MEMORIZATION property everywhere
else, with absolute (gold-free) criteria:

  trivial / mega_conj             must score ~0 (filter floor)
  state_mem / chunked_conj        whole-state memorizers must collapse
                                  (rollout atom budget + holdout seed)
  diseq_farm64                    pointwise farms bounded by their crude-true
                                  share (reported; tail inspected)
  const_bound                     reported only — the sampled box is a TRUE
                                  invariant on fixed-input programs

Adversaries see the union of every CANONICAL seed's sample; scoring
min-combines canonical + a holdout seed they never saw (as deployed).
Scored with w_marg=0 (no ablation): reward ~= base - junk penalty.

Run:  python -m rl_pipeline.eval.hack_sweep [--jobs 8] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INPUT = REPO / "src" / "input"

# Absolute gates (reward = base - junk with w_base=1, w_marg=0), derived from
# what the rollout ATOM BUDGET (32) provably allows a memorizer to cover:
#   state/chunk memorizers  <= 32 witness traces
#   diseq farms             <= 32 clauses x _SLICE_CAP(6) diversified traces
# plus slack for holdout-transferable crude-true facts.  Pools smaller than
# LOW_SIGNAL_NEG are reported separately, not gated: there everything short is
# both memorizable AND true (reward granularity is the real limit).
LOW_SIGNAL_NEG = 24
MEM_COVER = 32
SLACK = 0.15


def gates_for(n_neg: int, diseq_bound: float, ival_bound: float):
    # diseq/ival are gated by CONSISTENCY: a 32-atom farm can provably kill at
    # most the top-32 farm-targetable slices (diseq_bound) / the top-16
    # positive-free interval runs (ival_bound) of the pool; exceeding that
    # means a slice-cap / placement-spread leak in the sampler.  On small
    # finite state spaces these bounds are legitimately ~1 (complement
    # enumeration is crude TRUTH there, and the production Houdini drops
    # non-inductive clauses).
    return {
        "trivial": 0.01,
        "mega_conj": 0.01,
        "state_mem": min(0.65, MEM_COVER / n_neg + SLACK),
        "chunked_conj": min(0.65, MEM_COVER / n_neg + SLACK),
        "diseq_farm64": min(1.0, diseq_bound + SLACK),
        "ival_farm": min(1.0, ival_bound + SLACK),
    }


def top16_interval_coverage(example_sets, budget: int = 16, max_width: int = 200) -> float:
    """Provable ceiling for a `budget`-clause INTERVAL farm (2 atoms each under
    the 32-atom budget): per seed, negatives' farm-targetable values form
    maximal positive-free runs (an interval clause cannot span across a
    positive value without being dropped by the exact soundness check); the
    best farm covers at most the union of the top-`budget` runs.  Min over
    seeds bounds any FIXED farm's min-combined score."""
    per_seed = []
    for es in example_sets:
        pos_vals = {}
        for p in es.pos(0):
            for v, val in p.vars.items():
                pos_vals.setdefault(v, set()).add(val)
        negs = es.neg(0)
        groups = es.groups(0)
        if not groups:
            per_seed.append(0.0)
            continue
        val_groups: dict = {}
        for gi, idxs in enumerate(groups):
            for i in idxs:
                for v, val in negs[i].vars.items():
                    if val not in pos_vals.get(v, ()):
                        val_groups.setdefault(v, {}).setdefault(val, set()).add(gi)
        run_weights = []
        for v, vg in val_groups.items():
            vals = sorted(vg)
            pv = pos_vals.get(v, set())
            i = 0
            while i < len(vals):
                j = i
                covered = set(vg[vals[i]])
                while (j + 1 < len(vals) and vals[j + 1] - vals[i] <= max_width
                       and not any(p in pv for p in range(vals[j] + 1, vals[j + 1] + 1))):
                    j += 1
                    covered |= vg[vals[j]]
                run_weights.append(len(covered))
                i = j + 1
        top = sorted(run_weights, reverse=True)[:budget]
        per_seed.append(min(sum(top), len(groups)) / len(groups))
    return min(per_seed) if per_seed else 0.0


def top32_slice_coverage(example_sets) -> float:
    """Fraction of (all seeds') negative TRACES the 32 fattest farm-targetable
    slices cover — the provable ceiling for a 32-atom diseq farm (min-combined
    scoring can never exceed the per-seed max)."""
    fracs = []
    for es in example_sets:
        pos_vals = {}
        for p in es.pos(0):
            for v, val in p.vars.items():
                pos_vals.setdefault(v, set()).add(val)
        negs = es.neg(0)
        groups = es.groups(0)
        slice_groups: dict = {}
        for gi, idxs in enumerate(groups):
            for i in idxs:
                for v, val in negs[i].vars.items():
                    if val not in pos_vals.get(v, ()):
                        slice_groups.setdefault((v, val), set()).add(gi)
        top = sorted((len(g) for g in slice_groups.values()), reverse=True)[:32]
        covered = min(sum(top), len(groups))       # union bound
        fracs.append(covered / len(groups) if groups else 0.0)
    return max(fracs)


REPORT_ONLY = ("const_bound",)


def sweep_one(rel: str, n_runs: int) -> dict:
    from ..reward.filters import PositiveFilter
    from ..reward.reward_calculator import RewardCalculator
    from ..sampler import ExampleSampler
    from .discrimination import (HOLDOUT_SEED, _MergedExamples, chunked_conjunction,
                                 const_bounds, diseq_farm, interval_farm,
                                 mega_conjunction, state_memorizer)

    try:
        source = (INPUT / rel).read_text()
        canon = [ExampleSampler(source, n_runs=n_runs, seed=k).sample() for k in (0, 1)]
        holdout = ExampleSampler(source, n_runs=n_runs, seed=HOLDOUT_SEED).sample()
        if not canon[0].groups(0):
            return {"program": rel, "n_neg": 0}
        merged = _MergedExamples(canon)          # adversary knowledge
        families = {
            "trivial": ["1 == 1"],
            "mega_conj": mega_conjunction(merged),
            "state_mem": state_memorizer(merged),
            "chunked_conj": chunked_conjunction(merged),
            "diseq_farm64": diseq_farm(merged, budget=64),
            "ival_farm": interval_farm(merged),
            "const_bound": const_bounds(merged),
        }
        families = {k: v for k, v in families.items() if v}
        calc = RewardCalculator(invariant_filter=PositiveFilter(),
                                w_base=1.0, w_marg=0.0)
        names = list(families)
        batch = calc.compute(source, [{"invariants": families[n]} for n in names],
                             examples=canon + [holdout])
        rewards = {n: round(batch.rollouts[i].reward, 4) for i, n in enumerate(names)}
        n_neg = batch.n_negatives
        low_signal = n_neg < LOW_SIGNAL_NEG
        diseq_bound = top32_slice_coverage(canon + [holdout])
        ival_bound = top16_interval_coverage(canon + [holdout])
        gates = {} if low_signal else gates_for(n_neg, diseq_bound, ival_bound)
        violations = [f"{n}={rewards[n]:.3f}>{gates[n]:.3f}" for n in rewards
                      if n in gates and rewards[n] > gates[n]]
        return {"program": rel, "n_neg": n_neg, "low_signal": low_signal,
                "diseq_bound": round(diseq_bound, 3), "ival_bound": round(ival_bound, 3),
                "rewards": rewards, "violations": violations}
    except Exception as e:  # noqa: BLE001 - sweep must survive odd programs
        return {"program": rel, "error": str(e)[:200]}


def _worker(args):
    return sweep_one(*args)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-runs", type=int, default=12)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    programs = sorted(
        str(p.relative_to(INPUT))
        for d in ("linear", "NLA_lipus")
        for p in (INPUT / d).glob("*.c")
    )
    with mp.Pool(args.jobs) as pool:
        results = pool.map(_worker, [(rel, args.n_runs) for rel in programs])

    errs = [r for r in results if r.get("error")]
    zero = [r for r in results if r.get("n_neg") == 0 and not r.get("error")]
    low = [r for r in results if r.get("low_signal")]
    bad = [r for r in results if r.get("violations")]
    print(f"programs={len(results)}  zero-negative={len(zero)}  "
          f"low-signal(neg<{LOW_SIGNAL_NEG})={len(low)}  errors={len(errs)}")
    print(f"gate violations: {len(bad)} programs")
    for r in sorted(bad, key=lambda r: -max(r['rewards'].values()))[:25]:
        print(f"  !! {r['program']} (neg={r['n_neg']}): {', '.join(r['violations'])}")
    if low:
        print("  low-signal:", " ".join(f"{r['program']}:{r['n_neg']}" for r in low))
    for fam in ("trivial", "mega_conj", "state_mem", "chunked_conj",
                "diseq_farm64", "ival_farm") + REPORT_ONLY:
        vals = sorted(r["rewards"][fam] for r in results if r.get("rewards", {}).get(fam) is not None)
        if vals:
            mid = vals[len(vals) // 2]
            p95 = vals[int(len(vals) * 0.95)]
            print(f"  {fam:<13} n={len(vals):>3}  median={mid:.3f}  p95={p95:.3f}  max={vals[-1]:.3f}")
    if errs:
        for r in errs[:10]:
            print(f"  ERR {r['program']}: {r['error']}")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
