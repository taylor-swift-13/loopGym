import os
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """LLM backend config used by src/llm.py (inference rollout provider).

    Single, deterministic prompt path — no CoT variants."""

    # True  → local inference (Transformers backend)
    # False → cloud API provider (yunwu.ai / OpenAI compatible)
    use_local: bool = False

    # ── cloud API ─────────────────────────────────────────────────────────────
    api_model: str = "gpt-5-nano"
    api_key: str = os.getenv("OPENAI_API_KEY", "")   # never hardcode secrets
    base_url: str = "https://yunwu.ai/v1"

    # ── local inference (use_local=True) ──────────────────────────────────────
    local_model_path: str = ""

    # ── generation params ─────────────────────────────────────────────────────
    api_temperature: float = 1.0
    api_top_p: float = 1.0
    api_max_tokens: int = 16384

# ==============================================================================
# Houdini configuration (used by src/houdini_pruner.py)
# ==============================================================================
HOUDINI_CONFIG = {
    "max_iterations": 500,
}
