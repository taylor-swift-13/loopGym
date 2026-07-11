__all__ = ["ExampleSampler", "ExampleSet"]


def __getattr__(name):
    """Lazily expose sampler classes without pre-importing the CLI module."""
    if name in __all__:
        from .example_sampler import ExampleSampler, ExampleSet

        return {"ExampleSampler": ExampleSampler, "ExampleSet": ExampleSet}[name]
    raise AttributeError(name)
