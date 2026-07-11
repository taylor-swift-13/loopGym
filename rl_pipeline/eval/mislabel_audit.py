"""
Mislabel audit: a negative candidate that is observed REACHABLE corrupts the
tightness denominator and is a hard label error. For every benchmark program,
sample candidates at the canonical config and check them against positives of a
LARGER sample (same seed, more runs — the input prefix is identical, so
pair-level overlap is a genuine mislabel; extra runs only widen coverage).

Reports, per program:
  pair_mislabels : negatives whose (vars, pre) pair shows up as a positive  — hard error
  vars_overlap   : vars-only collisions (upper bound; pre may differ)       — soft signal

Run:  python -m rl_pipeline.eval.mislabel_audit [--audit-runs 24] [--jobs 8]
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INPUT = REPO / "src" / "input"


def discover_programs(suite: str = "core") -> list[str]:
    roots = {
        "core": ("linear", "NLA_lipus"),
        "loopy": ("Loopy",),
        "all": ("linear", "NLA_lipus", "Loopy"),
    }[suite]
    return sorted(
        str(path.relative_to(INPUT))
        for directory in roots
        for path in (INPUT / directory).glob("*.c")
    )


def audit_one(rel: str, base_runs: int, audit_runs: int) -> dict:
    from ..sampler import ExampleSampler

    try:
        source = (INPUT / rel).read_text()
        es = ExampleSampler(source, n_runs=base_runs).sample()
        negatives = es.neg(0)
        if not negatives:
            return {"program": rel, "n_neg": 0, "pair_mislabels": 0, "vars_overlap": 0}
        big = ExampleSampler(source, n_runs=audit_runs).sample()
        # a second seed adds branch/srand coverage (exact extra power for
        # no-param programs, whose pre is empty)
        big2 = ExampleSampler(source, n_runs=audit_runs, seed=9).sample()
        big_pos = big.pos(0) + big2.pos(0)
        pos_pairs = {(p.vars_key(), tuple(sorted(p.pre.items()))) for p in big_pos}
        pos_vars = {p.vars_key() for p in big_pos}
        pair = sum(1 for n in negatives
                   if (n.vars_key(), tuple(sorted(n.pre.items()))) in pos_pairs)
        vo = sum(1 for n in negatives if n.vars_key() in pos_vars)
        return {"program": rel, "n_neg": len(negatives),
                "pair_mislabels": pair, "vars_overlap": vo}
    except Exception as e:  # noqa: BLE001 - audit must survive odd programs
        return {"program": rel, "error": str(e)[:200]}


def _worker(args):
    return audit_one(*args)


def main() -> int:
    from ..sampler.example_sampler import DEFAULT_N_RUNS

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-runs", type=int, default=DEFAULT_N_RUNS)
    ap.add_argument("--audit-runs", type=int, default=DEFAULT_N_RUNS * 2)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--json", default=None)
    ap.add_argument(
        "--suite",
        choices=("core", "loopy", "all"),
        default="core",
        help="benchmark set to audit (default: the measured 366-program core)",
    )
    args = ap.parse_args()
    if args.base_runs < 1 or args.audit_runs < args.base_runs:
        ap.error("require 1 <= base-runs <= audit-runs")
    if args.jobs < 1:
        ap.error("jobs must be at least 1")

    programs = discover_programs(args.suite)
    tasks = [(rel, args.base_runs, args.audit_runs) for rel in programs]
    with mp.Pool(args.jobs) as pool:
        results = pool.map(_worker, tasks)

    bad = [r for r in results if r.get("pair_mislabels")]
    soft = [r for r in results if r.get("vars_overlap") and not r.get("pair_mislabels")]
    errs = [r for r in results if r.get("error")]
    total_neg = sum(r.get("n_neg", 0) for r in results)
    print(f"programs={len(results)}  total_negatives={total_neg}")
    print(f"pair mislabels (hard): {len(bad)} programs, "
          f"{sum(r['pair_mislabels'] for r in bad)} states")
    for r in sorted(bad, key=lambda r: -r["pair_mislabels"])[:20]:
        print(f"  HARD {r['program']}: {r['pair_mislabels']}/{r['n_neg']}")
    print(f"vars-only overlap (soft): {len(soft)} programs, "
          f"{sum(r['vars_overlap'] for r in soft)} states")
    for r in sorted(soft, key=lambda r: -r["vars_overlap"])[:20]:
        print(f"  soft {r['program']}: {r['vars_overlap']}/{r['n_neg']}")
    if errs:
        print(f"errors: {len(errs)}")
        for r in errs[:10]:
            print(f"  ERR {r['program']}: {r['error']}")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
    return 1 if bad or errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
