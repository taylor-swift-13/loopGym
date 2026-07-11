"""
Reward service — Component 2 exposed over HTTP (FastAPI).

  POST /reward           {program, rollouts, ...}       -> per-rollout reward + batch score
  POST /refine_feedback  {program, pool, ...}           -> verdicts + assembled refine prompt
  POST /refine_reward    {program, pool, refinements}   -> delta_base[] per refinement
  POST /sample           {program, ...}                 -> example-set stats (debug)
  GET  /health

The example set (positives/negative candidates) is expensive to sample, so it is cached
per (program, sampler-config).  Any RL trainer can POST batches here — the two
refine endpoints make refine-group training turnkey: the trainer never needs a
local frama-c or an rl_pipeline import.

Run:  python -m rl_pipeline.reward.service --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import dataclasses
import hashlib
import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from ..common import prompts
from ..common.program import parse_program, strip_postcondition
from ..common.state import dedup_normalized
from ..sampler import ExampleSampler, ExampleSet
from ..sampler.example_sampler import DEFAULT_N_RUNS, DEFAULT_SEED
from . import filters
from .refine import refine_group_delta_base
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
    # Defaults come from the canonical sampler source and are shared by the
    # reward service and offline scorer. Inference performs no reward sampling.
    # Synthetic negatives derive only from loop traces, never from the assert.
    n_runs: int = Field(DEFAULT_N_RUNS, ge=1)
    seed: int = DEFAULT_SEED


class RewardRequest(BaseModel):
    program: str = Field(..., description="C program source with requires/loop/assert")
    rollouts: List[Any] = Field(..., description="each: {'invariants':[...]} or {'code': '...'}")
    w_base: float = Field(0.5, ge=0.0)
    w_marg: float = Field(0.5, ge=0.0)
    reroll_threshold: float = Field(0.6, ge=0.0, le=1.0)
    sampler: SamplerCfg = Field(default_factory=SamplerCfg)


class RefineFeedbackRequest(BaseModel):
    program: str = Field(..., description="C program source (full, with assert)")
    pool: List[str] = Field(..., description="merged invariant pool: the union of the group's rollouts")
    loop_idx: int = Field(0, ge=0)
    hide_assert: bool = True   # closed-book: the assembled prompt strips the assert


class RefineRewardRequest(BaseModel):
    program: str
    pool: List[str] = Field(..., description="the SAME pool the refine prompt showed")
    refinements: List[List[str]] = Field(..., description="one invariant list per sampled refine response")
    loop_idx: int = Field(0, ge=0)
    sampler: SamplerCfg = Field(default_factory=SamplerCfg)


class SampleRequest(BaseModel):
    program: str
    sampler: SamplerCfg = Field(default_factory=SamplerCfg)
    show: int = Field(8, ge=0)


def _cache_key(program: str, n_runs: int, seed: int) -> str:
    return hashlib.sha1(f"{program}|runs={n_runs}|seed={seed}".encode()).hexdigest()


def _get_examples(program: str, cfg: SamplerCfg):
    key = _cache_key(program, cfg.n_runs, cfg.seed)
    es = _EXAMPLE_CACHE.get(key)
    if es is None:
        es = ExampleSampler(program, n_runs=cfg.n_runs, seed=cfg.seed).sample()
        _EXAMPLE_CACHE[key] = es
    return es


def build_app():
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="LoopGym Reward Service", version="1.0")

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
                w_base=req.w_base, w_marg=req.w_marg,
                reroll_threshold=req.reroll_threshold, logger=log,
            )
            br = rc.compute(req.program, req.rollouts, examples=examples)
            return br.to_dict()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/refine_feedback")
    def refine_feedback(req: RefineFeedbackRequest):
        """Build a refine group's prompt: syntax scrub + at most two WP rounds
        over the pool -> verdict table -> prompt/refine_prompt.txt assembled.
        `n_rejected == 0` means there is nothing to refine (skip the group)."""
        stage = filters.precheck_stage(_get_filter())
        if stage is None:
            raise HTTPException(status_code=503,
                                detail="no WP precheck stage (frama-c unavailable)")
        try:
            prog = parse_program(req.program)
            if req.loop_idx >= len(prog.loops):
                raise ValueError(
                    f"loop_idx {req.loop_idx} is out of range for {len(prog.loops)} loops"
                )
            pool = dedup_normalized(req.pool)
            verdicts = stage.precheck(prog, req.loop_idx, pool)
            feedback = filters.build_feedback(verdicts)
            source = strip_postcondition(req.program) if req.hide_assert else req.program
            return {
                "pool": pool,
                "verdicts": [dataclasses.asdict(v) for v in verdicts],
                "feedback": feedback,
                "prompt": prompts.REFINE_PROMPT.format(program=source, feedback=feedback),
                "n_rejected": sum(1 for v in verdicts if not v.kept),
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/refine_reward")
    def refine_reward(req: RefineRewardRequest):
        """Score one refine group: delta_base[i] = base(Houdini(pool ∪ refined_i))
        − base(Houdini(pool)); base_before computed once and shared."""
        try:
            examples = _get_examples(req.program, req.sampler)
            calc = RewardCalculator(invariant_filter=_get_filter(),
                                    w_base=1.0, w_marg=0.0, logger=log)
            return refine_group_delta_base(
                req.program, req.pool, req.refinements,
                examples=examples, calculator=calc, loop_idx=req.loop_idx)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/sample")
    def sample(req: SampleRequest):
        try:
            es = _get_examples(req.program, req.sampler)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        out = {"program": es.program.func_name, "guard": es.program.loop.guard,
               "loops": {}}
        for li in sorted(es.positives):
            out["loops"][li] = {
                "stats": es.stats.get(li, {}),
                "positives": [s.render() for s in es.pos(li)[:req.show]],
                "negatives": [s.render() for s in es.neg(li)[:req.show]],
            }
        return out

    return app


# Module-level app for `uvicorn rl_pipeline.reward.service:app`.
app = build_app()


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
