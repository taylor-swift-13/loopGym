"""
Reward service — Component 2 exposed over HTTP (FastAPI).

  POST /reward   {program, rollouts, ...}  -> per-rollout reward + batch score
  POST /sample   {program, ...}            -> example-set stats (debug/collaboration)
  GET  /health

The example set (positives/negatives) is expensive to sample, so it is cached
per (program, sampler-config).  Any RL trainer can POST batches here.

Run:  python -m rl_pipeline.reward.service --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import hashlib
import logging
import random
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..sampler import ExampleSampler, ExampleSet
from ..sampler.example_sampler import DEFAULT_N_RUNS, DEFAULT_SEED
from . import filters
from .reward_calculator import RewardCalculator

log = logging.getLogger("rl_pipeline.reward.service")

# lazily-built shared invariant filter (Houdini if frama-c present, else positive)
_SHARED_FILTER = None
_EXAMPLE_CACHE: Dict[str, ExampleSet] = {}


def _get_filter():
    global _SHARED_FILTER
    if _SHARED_FILTER is None:
        _SHARED_FILTER = filters.auto_filter(log)
    return _SHARED_FILTER


class SamplerCfg(BaseModel):
    # Defaults from the SINGLE canonical source in sampler.example_sampler, so the
    # reward service (training) and the inference framework sample identically.
    # The sampler sees ONLY the loop: negatives are UNREACHABLE loop-head
    # valuations (states no execution trace produces), never derived from assert.
    n_runs: int = DEFAULT_N_RUNS
    seed: int = DEFAULT_SEED
    # score against this many consecutive seeds and take the per-rollout MINIMUM
    # (kills memorization of any one deterministic sample); 1 = legacy behavior
    n_seeds: int = 2
    # additionally score against this many HOLDOUT example sets with a fresh
    # random seed per request (pin with holdout_seed for reproducibility): a
    # policy that adapted to the fixed canonical seeds gains nothing — overfit
    # boxes/farms collapse on the unseen sample while true invariants don't care
    n_holdout: int = 1
    holdout_seed: Optional[int] = None


class RewardRequest(BaseModel):
    program: str = Field(..., description="C program source with requires/loop/assert")
    rollouts: List[Any] = Field(..., description="each: {'invariants':[...]} or {'code': '...'}")
    w_base: float = 0.5
    w_marg: float = 0.5
    w_junk: float = 0.05
    reroll_threshold: float = 0.6
    sampler: SamplerCfg = SamplerCfg()


class SampleRequest(BaseModel):
    program: str
    sampler: SamplerCfg = SamplerCfg()
    show: int = 8


def _cache_key(program: str, n_runs: int, seed: int) -> str:
    return hashlib.sha1(f"{program}|runs={n_runs}|seed={seed}".encode()).hexdigest()


def _get_examples(program: str, cfg: SamplerCfg):
    # one ExampleSet per scored seed, each cached independently
    sets = []
    for k in range(max(1, cfg.n_seeds)):
        key = _cache_key(program, cfg.n_runs, cfg.seed + k)
        es = _EXAMPLE_CACHE.get(key)
        if es is None:
            es = ExampleSampler(program, n_runs=cfg.n_runs, seed=cfg.seed + k).sample()
            _EXAMPLE_CACHE[key] = es
        sets.append(es)
    for j in range(max(0, cfg.n_holdout)):
        if cfg.holdout_seed is not None:      # pinned holdout: deterministic + cacheable
            hs = cfg.holdout_seed + j
            key = _cache_key(program, cfg.n_runs, hs)
            es = _EXAMPLE_CACHE.get(key)
            if es is None:
                es = ExampleSampler(program, n_runs=cfg.n_runs, seed=hs).sample()
                _EXAMPLE_CACHE[key] = es
        else:                                 # fresh seed per request: never cached
            es = ExampleSampler(program, n_runs=cfg.n_runs,
                                seed=random.randrange(1 << 30)).sample()
        sets.append(es)
    return sets if len(sets) > 1 else sets[0]


def build_app():
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="SAM2INV Reward Service", version="1.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "filter_mode": getattr(_get_filter(), "name", "unknown"),
                "cached_programs": len(_EXAMPLE_CACHE)}

    @app.post("/reward")
    def reward(req: RewardRequest):
        try:
            examples = _get_examples(req.program, req.sampler)
            rc = RewardCalculator(
                invariant_filter=_get_filter(),
                w_base=req.w_base, w_marg=req.w_marg, w_junk=req.w_junk,
                reroll_threshold=req.reroll_threshold, logger=log,
            )
            br = rc.compute(req.program, req.rollouts, examples=examples)
            return br.to_dict()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/sample")
    def sample(req: SampleRequest):
        try:
            es = _get_examples(req.program, req.sampler)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if isinstance(es, list):        # multi-seed config: show the first seed's set
            es = es[0]
        out = {"program": es.program.func_name, "guard": es.program.loop.guard,
               "post": es.program.post, "loops": {}}
        for li in sorted(es.positives):
            out["loops"][li] = {
                "stats": es.stats.get(li, {}),
                "positives": [s.render() for s in es.pos(li)[:req.show]],
                "negatives": [s.render() for s in es.neg(li)[:req.show]],
            }
        return out

    return app


# module-level app for `uvicorn rl_pipeline.reward.service:app`
try:  # pragma: no cover
    app = build_app()
except Exception:  # fastapi missing at import time
    app = None


def _main():
    import argparse
    import uvicorn

    ap = argparse.ArgumentParser(description="Run the reward HTTP service")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    uvicorn.run(build_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    _main()
