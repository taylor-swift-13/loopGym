"""Single source of truth for every LLM prompt: <repo-root>/prompt/*.txt.

Edit the .txt files — never inline prompt text in code.  Templates use
str.format placeholders ({program}, {feedback}) filled at call sites.

  generate_prompt.txt  — rollout generation (closed-book by default)
  refine_prompt.txt    — m-round refine; STATELESS by design: it sees only
                         program + current pool verdicts (no round number, no
                         history), so "train one round, infer many" stays
                         in-distribution.  Shared VERBATIM by inference and RL
                         training — both must format THIS template.
  system_prompt.txt    — chat system prompt (vLLM / src.llm.Chatbot)
"""
from __future__ import annotations

import os

PROMPT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "prompt")


def load(name: str) -> str:
    with open(os.path.join(PROMPT_DIR, name), encoding="utf-8") as f:
        return f.read()


GENERATE_PROMPT = load("generate_prompt.txt")
REFINE_PROMPT = load("refine_prompt.txt")


def system_prompt() -> str:
    """Chat system prompt, or "" if the file is absent."""
    try:
        return load("system_prompt.txt")
    except OSError:
        return ""
