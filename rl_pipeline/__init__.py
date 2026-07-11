"""
LoopGym invariant-generation and reward pipeline.

Three independently usable entry points share common parsing and state code;
reward and inference additionally share the Frama-C adapter:

  * sampler   — produces positive (reachable) and negative (must-exclude)
                loop-entry valuations for a program.
  * reward    — given a group of rollouts + example sets, computes per-rollout
                reward, base score, marginal gain, and a batch score.
                Exposed as a FastAPI HTTP service.
  * inference — generate rollouts -> optional refine -> combine -> Houdini ->
                verify. It does not sample reward examples.

See the root README and docs/training_integration.md for the current contracts.
"""

__all__ = ["common", "sampler", "reward", "inference"]
