"""Δbase reward for refine-training groups.

A refine GRPO group shares one prompt: (program + merged rollout pool + verdict
table).  Each sampled refine response is rewarded by how much it raises the
pool's base score (negative-discrimination after real Houdini):

    delta_base[i] = base(Houdini(pool ∪ refined_i)) − base(Houdini(pool))

This IS the refined invariants' marginal contribution to the merged pool.
Under GRPO group normalization the shared base_before is absorbed, so the delta
equals the absolute score gradient-wise — the delta form is kept for monitoring
("how much discrimination the refine recovered").  Δ ≥ 0 always (the pool only
grows, Houdini survivors are monotone), so an all-zero group simply yields no
gradient — expected early in training.

Trivial/copied/weakened refinements get Δ ≈ 0 for free: they must both survive
Houdini AND reject new negatives to score.

The refine prompt and feedback renderer are shared through
``rl_pipeline.common.prompts`` and ``reward.filters`` so training and inference
format the same stateless input.
"""
from __future__ import annotations

from typing import List, Optional

from ..common.state import dedup_normalized
from ..sampler import ExampleSampler, ExampleSet
from .reward_calculator import RewardCalculator


def refine_group_delta_base(
    source: str,
    pool: List[str],
    refinements: List[List[str]],
    examples: Optional[ExampleSet] = None,
    calculator: Optional[RewardCalculator] = None,
    loop_idx: int = 0,
) -> dict:
    """Score one refine group: n refine responses against a shared merged pool.

    Returns {"delta_base": [n floats], "base_before": float, "base_after": [n],
    "pool_size": int}.  base_before is computed ONCE and shared across the group
    (n+1 Houdini cascades total; the calculator's survive cache dedups overlap).
    """
    calc = calculator or RewardCalculator(w_marg=0.0)
    if examples is None:
        examples = ExampleSampler(source, **calc.sampler_kwargs).sample()
    pool = dedup_normalized(pool)
    merged = [dedup_normalized(list(pool) + list(r)) for r in refinements]
    # rollout 0 = the un-refined pool; rollouts 1..n = pool ∪ refined_i
    res = calc.compute(source, [pool] + merged, examples=examples, loop_idx=loop_idx)
    base_before = res.rollouts[0].base
    base_after = [r.base for r in res.rollouts[1:]]
    return {
        # Guard the public delta >= 0 contract against floating-point residue.
        "delta_base": [max(0.0, after - base_before) for after in base_after],
        "base_before": base_before,
        "base_after": base_after,
        "pool_size": len(pool),
    }
