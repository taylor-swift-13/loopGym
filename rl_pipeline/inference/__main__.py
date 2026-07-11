"""Deploy a trained model to vLLM and run certified inference.

    python -m rl_pipeline.inference --model <hf-or-local> \
        --inputs 'src/input/NLA_lipus/*.c' --n-rollouts 8 --output results.jsonl

Inference does not sample reward examples.  It generates with vLLM, optionally
refines the merged pool, then runs Houdini and Frama-C/WP verification.
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import os

from . import InferenceFramework, VLLMRolloutProvider


def _expand(patterns):
    out = []
    seen = set()
    for p in patterns:
        if os.path.isdir(p):
            matches = sorted(glob.glob(os.path.join(p, "**", "*.c"), recursive=True))
        elif any(c in p for c in "*?["):
            matches = sorted(glob.glob(p, recursive=True))
        else:
            matches = [p]
        for match in matches:
            key = os.path.abspath(match)
            if key not in seen:
                seen.add(key)
                out.append(match)
    return out


def main():
    ap = argparse.ArgumentParser(description="Run inference with a vLLM-served model")
    ap.add_argument("--model", required=True, help="HF id or local dir of the trained model")
    ap.add_argument("--inputs", nargs="+", required=True, help="dirs / globs / files of .c programs")
    ap.add_argument("--n-rollouts", type=int, default=8)
    ap.add_argument("--max-rerolls", type=int, default=1)
    ap.add_argument("--m-refine", type=int, default=0,
                    help="maximum verifier-feedback refinement rounds")
    ap.add_argument("--refine-samples", type=int, default=1,
                    help="model samples requested in each refinement round")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top-p", type=float, default=1.0)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--output", default=None, help="write per-program results as JSONL")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    files = _expand(args.inputs)
    if not files:
        raise SystemExit("no input .c files matched")

    provider = VLLMRolloutProvider(
        model=args.model,
        temperature=args.temperature, top_p=args.top_p, max_tokens=args.max_tokens,
    )
    rows, verified = [], 0
    for i, path in enumerate(files):
        src = open(path).read()
        fw = InferenceFramework(src, rollout_provider=provider,
                                n_rollouts=args.n_rollouts, max_rerolls=args.max_rerolls,
                                m_refine=args.m_refine, refine_samples=args.refine_samples)
        res = fw.run()
        verified += int(res.verified is True)
        rows.append({
            "input": path,
            "program": os.path.basename(path),
            "verified": res.verified,
            "invariants": res.final_invariants,
            "reroll_count": res.reroll_count,
            "refine_rounds": res.refine_rounds,
        })
        logging.info("[%d/%d] %s  verified=%s  refinements=%d",
                     i + 1, len(files), os.path.basename(path),
                     res.verified, res.refine_rounds)

    print(f"\nverified {verified}/{len(files)} (Frama-C/WP)")
    if args.output:
        with open(args.output, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
