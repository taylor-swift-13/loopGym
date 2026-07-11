__all__ = ["RewardCalculator", "BatchReward", "RolloutScore"]


def __getattr__(name):
    """Keep the public API without importing the sampler on package import.

    Inference reuses only ``reward.annotate`` and ``reward.filters``.  Eagerly
    importing ``reward_calculator`` made that independent path load the entire
    sampling stack as an accidental side effect.
    """
    if name in __all__:
        from .reward_calculator import BatchReward, RewardCalculator, RolloutScore

        return {
            "RewardCalculator": RewardCalculator,
            "BatchReward": BatchReward,
            "RolloutScore": RolloutScore,
        }[name]
    raise AttributeError(name)
