"""Testing entrypoint: deploy a trained model to vLLM and run inference.

    python -m rl_pipeline.inference --model <hf-or-local> \
        --inputs 'src/input/NLA_lipus/*.c' --n-rollouts 8 --output results.jsonl

Shares the SAME sampler as the reward service (via InferenceFramework →
ExampleSampler).  Frama-C (bundled in the inference image) makes `verified` real:
each program is sample → generate (vLLM) → positive-filter → combine → Houdini →
Frama-C/WP verify.
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
    for p in patterns:
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, "*.c")))
        elif any(c in p for c in "*?["):
            out += sorted(glob.glob(p))
        else:
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(description="Run inference with a vLLM-served model")
    ap.add_argument("--model", required=True, help="HF id or local dir of the trained model")
    ap.add_argument("--inputs", nargs="+", required=True, help="dirs / globs / files of .c programs")
    ap.add_argument("--n-rollouts", type=int, default=8)
    ap.add_argument("--max-rerolls", type=int, default=1)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top-p", type=float, default=1.0)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--show-assert", action="store_true",
                    help="open-book: let the model see the assert (default: hidden)")
    ap.add_argument("--output", default=None, help="write per-program results as JSONL")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    files = _expand(args.inputs)
    if not files:
        raise SystemExit("no input .c files matched")

    provider = VLLMRolloutProvider(
        model=args.model, hide_assert=not args.show_assert,
        temperature=args.temperature, top_p=args.top_p, max_tokens=args.max_tokens,
    )
    rows, verified = [], 0
    for i, path in enumerate(files):
        src = open(path).read()
        fw = InferenceFramework(src, rollout_provider=provider,
                                n_rollouts=args.n_rollouts, max_rerolls=args.max_rerolls)
        res = fw.run()
        verified += int(res.verified is True)
        rows.append({"program": os.path.basename(path), "verified": res.verified,
                     "batch_score": res.batch_score, "invariants": res.final_invariants})
        logging.info("[%d/%d] %s  verified=%s  score=%s",
                     i + 1, len(files), os.path.basename(path), res.verified, res.batch_score)

    print(f"\nverified {verified}/{len(files)} (Frama-C/WP)")
    if args.output:
        with open(args.output, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
