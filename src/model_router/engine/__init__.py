"""model_router.engine package."""

__all__ = ["InferenceCore"]


def __getattr__(name: str):
    if name == "InferenceCore":
        from model_router.engine.core import InferenceCore
        return InferenceCore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
