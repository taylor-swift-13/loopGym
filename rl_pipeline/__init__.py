"""
rl_pipeline — reward-oriented invariant-generation pipeline.

Three independent-but-collaborating components:

  * sampler   — produces positive (reachable) and negative (must-exclude)
                loop-entry valuations for a program.
  * reward    — given a group of rollouts + example sets, computes per-rollout
                reward, base score, marginal gain, and a batch score.
                Exposed as a FastAPI HTTP service.
  * inference — the generation loop: sample rollouts -> positive-filter ->
                combine -> Houdini -> verify.

See docs/reward_pipeline_plan.md for the design.
"""

__all__ = ["common", "sampler", "reward", "inference"]
