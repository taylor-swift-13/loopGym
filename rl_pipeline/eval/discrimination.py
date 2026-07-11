"""
Reward-discrimination harness: does the reward rank rollouts by true quality?

For each benchmark program we build rollout families of KNOWN relative quality:

  gold        true, tight invariant set (hand-written)
  loose       true but weaker subset            (must score <= gold)
  trivial     ["1 == 1"]                        (must score ~0)
  guard_copy  [loop guard]                      (violated at exit state -> ~0)
  post_copy   [assert expression]               (usually violated at entry -> ~0)
  unsound     pins a movable var to one sampled value (filtered -> ~0)

Criteria per program:
  * gold must dominate junk by a margin:   reward(gold) >= reward(trivial) + margin
  * gold must actually work:               base(gold) >= min_gold_base
  * quality order:                         reward(gold) >= reward(loose) - eps

Run:  python -m rl_pipeline.eval.discrimination [--programs ...] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..common.program import parse_program
from ..reward.filters import auto_filter, frama_c_available
from ..reward.reward_calculator import RewardCalculator
from ..sampler import ExampleSampler

REPO = Path(__file__).resolve().parents[2]
INPUT = REPO / "src" / "input"

# ── benchmark programs with hand-written ground truth ────────────────────────
# gold = true + tight; loose = true + strictly weaker.
SPECS: Dict[str, Dict[str, object]] = {
    "linear/103.c": {   # x=0; while(x<100) x++;           1-var, worst case for pointwise hacks
        "gold": ["0 <= x", "x <= 100"],
        "loose": ["0 <= x"],
    },
    "linear/2.c": {     # x=1,y=0; while(y<1000){x+=y;y++}  long loop (cap stress)
        "gold": ["0 <= y", "y <= 1000", "2*x == y*y - y + 2"],
        "loose": ["0 <= y", "x >= 1"],
    },
    "linear/1.c": {     # same but y<100000                 extreme length stress
        # x overflows int32 during the run, so the executed-semantics relation is
        # modular; `x >= 1` is NOT a true invariant of the compiled program.
        "gold": ["0 <= y", "y <= 100000", "(2*x - y*y + y - 2) % 4294967296 == 0"],
        "loose": ["0 <= y"],
    },
    "linear/34.c": {    # x=n; while(x>0) x--;              symbolic bound
        "gold": ["x <= n", "n > 0 ==> x >= 0", "n <= 0 ==> x == n"],
        "loose": ["x <= n"],
    },
    "linear/68.c": {    # x=1; while(x<=n){y=n-x;x++}       param-dependent
        "gold": ["x >= 1", "n >= 1 ==> x <= n + 1", "x > 1 ==> y == n - x + 1",
                 "x == 1 ==> y == \\at(y,Pre)"],
        "loose": ["x >= 1"],
    },
    "NLA_lipus/2.c": {  # division by counting: q,r vs x/y  C-division semantics
        "gold": ["0 <= q", "0 <= r", "r < y", "x >= y * q + r", "q <= x / y"],
        "loose": ["0 <= r", "x >= y * q + r"],
    },
    "NLA_lipus/15.c": { # c,y count, x=sum(1..y)            nonlinear relation
        "gold": ["c == y", "2*x == y*y + y", "0 <= c", "c <= k"],
        "loose": ["c == y", "0 <= c"],
    },
    "NLA_lipus/1.c": {  # cubic series                      nonlinear, multi-relation
        "gold": ["z == 6*n + 6", "y == 3*n*n + 3*n + 1", "x == n*n*n", "n >= 0", "n <= a + 1"],
        "loose": ["z == 6*n + 6", "n >= 0"],
    },
    "NLA_lipus/24.c": { # z=x*y; while(x>0){x--;z-=y}       nonlinear product relation
        "gold": ["z == x*y", "x >= 0"],
        "loose": ["x >= 0"],
    },
    "NLA_lipus/5.c": {  # extended GCD (comma declarators)   multi-var bilinear relations
        "gold": ["a == p*x + r*y", "b == q*x + s*y", "p*s - r*q == 1", "a >= 1", "b >= 1"],
        "loose": ["p*s - r*q == 1", "a >= 1"],
        "post_is_invariant": True,
    },
    # Nondeterministic programs are excluded because the conservative sampler
    # emits no finite-sample negatives for oracle-controlled loops.
}

def unsound_pin(examples) -> List[str]:
    """Pin one variable to a single sampled value (violated by other positives)."""
    pos = examples.pos(0)
    if len(pos) < 2:
        return []
    v = next(iter(pos[0].vars))
    vals = sorted({p.vars[v] for p in pos})
    if len(vals) < 2:
        return []
    return [f"{v} == {vals[len(vals) // 2]}"]


# ── harness ──────────────────────────────────────────────────────────────────

@dataclass
class ProgramReport:
    program: str
    n_pos: int
    n_neg: int
    rewards: Dict[str, float]
    bases: Dict[str, float]
    survivors: Dict[str, int]
    violations: List[str]


def evaluate_program(rel_path: str, spec: Dict[str, object],
                     margin: float = 0.15, eps: float = 0.02,
                     min_gold_base: float = 0.80,
                     sampler_kwargs: Optional[dict] = None) -> ProgramReport:
    source = (INPUT / rel_path).read_text()
    prog = parse_program(source)
    gold: List[str] = list(spec["gold"])
    loose: List[str] = list(spec["loose"])
    sampler_kwargs = dict(sampler_kwargs or {})
    base_seed = int(sampler_kwargs.pop("seed", 0)) if "seed" in sampler_kwargs else 0
    # adversary generators see the EXACT sample being scored
    examples = ExampleSampler(source, seed=base_seed, **sampler_kwargs).sample()

    families: Dict[str, List[str]] = {
        "gold": gold,
        "loose": loose,
        "trivial": ["1 == 1"],
        "guard_copy": [prog.loop.guard] if prog.loop else [],
        "post_copy": [prog.post] if prog.post else [],
        "unsound": unsound_pin(examples),
    }
    families = {k: v for k, v in families.items() if v}

    calc = RewardCalculator(invariant_filter=auto_filter(), sampler_kwargs=sampler_kwargs)
    names = list(families)
    # scored with the DEPLOYED filter cascade (real Houdini when frama-c is on PATH)
    batch = calc.compute(source, [{"invariants": families[n]} for n in names],
                         examples=examples)
    rewards = {n: batch.rollouts[i].reward for i, n in enumerate(names)}
    bases = {n: batch.rollouts[i].base for i, n in enumerate(names)}
    survivors = {n: len(batch.rollouts[i].survivors) for i, n in enumerate(names)}

    v: List[str] = []
    g = rewards["gold"]
    if bases["gold"] < min_gold_base:
        v.append(f"gold base too low: {bases['gold']:.2f} < {min_gold_base}")
    if len(survivors) and survivors["gold"] < len(gold):
        v.append(f"gold invariants filtered: {survivors['gold']}/{len(gold)} survive "
                 f"(a TRUE invariant failed the positive check -> sampler mislabels)")
    if rewards.get("loose", 0.0) > g + eps:
        v.append(f"loose beats gold: {rewards['loose']:.3f} > {g:.3f}")
    # post_copy is junk when the assert is NOT a loop invariant (violated at
    # entry / vacuous); on programs where it IS one (post_is_invariant), copying
    # it deserves reward — then it is a quality family that just must not BEAT gold
    junk_families = ["trivial", "guard_copy", "unsound"]
    if spec.get("post_is_invariant"):
        if rewards.get("post_copy", 0.0) > g + eps:
            v.append(f"post_copy beats gold: {rewards['post_copy']:.3f} > {g:.3f}")
    else:
        junk_families.append("post_copy")
    for junk in junk_families:
        if junk in rewards and rewards[junk] > g - margin:
            v.append(f"junk {junk} too close to gold: {rewards[junk]:.3f} vs {g:.3f}")
    return ProgramReport(
        program=rel_path,
        n_pos=batch.n_positives, n_neg=batch.n_negatives,
        rewards=rewards, bases=bases, survivors=survivors, violations=v,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--programs", nargs="*", default=list(SPECS))
    ap.add_argument("--runs", type=int, default=None, help="override sampler n_runs")
    ap.add_argument("--json", default=None, help="write full report JSON here")
    args = ap.parse_args()

    sampler_kwargs = {"n_runs": args.runs} if args.runs else {}
    if not frama_c_available():
        print("!! WARNING: frama-c not on PATH — running the LITE filter path.")
        print("!!          Production runs the Houdini cascade; lite certificates do not transfer.")
    reports = []
    total_violations = 0
    for rel in args.programs:
        rep = evaluate_program(rel, SPECS[rel], sampler_kwargs=sampler_kwargs)
        reports.append(rep)
        total_violations += len(rep.violations)
        print(f"\n=== {rep.program}   pos={rep.n_pos} neg={rep.n_neg}")
        order = sorted(rep.rewards, key=lambda n: -rep.rewards[n])
        for n in order:
            print(f"  {n:<12} reward={rep.rewards[n]:.3f}  base={rep.bases[n]:.3f}  "
                  f"survivors={rep.survivors[n]}")
        for v in rep.violations:
            print(f"  !! {v}")

    print(f"\n{'=' * 60}\nprograms={len(reports)}  violations={total_violations}")
    if args.json:
        Path(args.json).write_text(json.dumps(
            [rep.__dict__ for rep in reports], indent=2, default=str))
    return 1 if total_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
