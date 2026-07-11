"""Closed-book generation, optional refinement, Houdini pruning, and verification.

Inference is independent of reward sampling and scoring.  Rollouts come from a
swappable provider:
  * LLMRolloutProvider  — queries an LLM (src/llm.Chatbot) for ACSL invariants.
  * MockRolloutProvider — fixed invariant sets (for tests / offline runs).
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ..common import prompts
from ..common.program import Program, parse_program, strip_postcondition
from ..common.state import extract_invariants, dedup_normalized
from ..reward import annotate
from ..reward import filters


# ── rollout providers ────────────────────────────────────────────────────────

class MockRolloutProvider:
    """Returns pre-baked invariant sets; cycles if asked for more than provided.
    `refinements` (optional) are consumed one per refine() call, for tests."""

    def __init__(self, rollouts: List[List[str]], refinements: Optional[List[List[str]]] = None):
        self.rollouts = rollouts
        self.refinements = list(refinements or [])
        self._refine_calls = 0

    def __call__(self, prog: Program, n: int) -> List[List[str]]:
        if not self.rollouts:
            return [[] for _ in range(n)]
        return [list(self.rollouts[i % len(self.rollouts)]) for i in range(n)]

    def refine(self, prog: Program, feedback: str, n: int = 1) -> List[List[str]]:
        if self._refine_calls >= len(self.refinements):
            return [[] for _ in range(n)]
        out = [list(self.refinements[self._refine_calls]) for _ in range(n)]
        self._refine_calls += 1
        return out


class LLMRolloutProvider:
    """Queries an LLM for invariants. `chat_fn` maps a prompt string -> response string.

    Two modes via `hide_assert`:
      * True  (default) — the program shown to the model has its postcondition
        stripped, so it synthesises invariants from loop semantics ("closed-book").
      * False — the full program (assert visible) is shown ("open-book"): the
        model may use the goal to guide invariant discovery."""

    def __init__(self, chat_fn: Optional[Callable[[str], str]] = None, logger=None,
                 hide_assert: bool = True):
        self.log = logger or logging.getLogger("rl_pipeline.inference.llm")
        self.chat_fn = chat_fn or self._default_chat_fn()
        self.hide_assert = hide_assert

    @staticmethod
    def _default_chat_fn() -> Callable[[str], str]:
        from src.config import LLMConfig
        from src.llm import Chatbot

        cfg = LLMConfig()
        bot = Chatbot(cfg)
        return bot.chat

    def __call__(self, prog: Program, n: int) -> List[List[str]]:
        # closed-book: hide the assert (goal) so the model can't restate it
        source = strip_postcondition(prog.source) if self.hide_assert else prog.source
        return self._chat_n(prompts.GENERATE_PROMPT.format(program=source), n)

    def refine(self, prog: Program, feedback: str, n: int = 1) -> List[List[str]]:
        source = strip_postcondition(prog.source) if self.hide_assert else prog.source
        return self._chat_n(
            prompts.REFINE_PROMPT.format(program=source, feedback=feedback), n
        )

    def _chat_n(self, prompt: str, n: int) -> List[List[str]]:
        out: List[List[str]] = []
        for _ in range(n):
            try:
                resp = self.chat_fn(prompt)
            except Exception as e:
                self.log.warning("LLM call failed: %s", e)
                resp = ""
            out.append(extract_invariants(resp))
        return out


class VLLMRolloutProvider:
    """Batched rollout generation with an IN-PROCESS vLLM engine — all n samples
    for a program are produced in ONE call (high-throughput RL path, no HTTP).
    Honors `hide_assert` like LLMRolloutProvider.

    Requires the optional `vllm` package (+ a GPU).  To use a vLLM OpenAI *server*
    instead (e.g. verl's), point `src.llm.Chatbot` at it via
    `LLMConfig(base_url="http://host:8000/v1", api_model=...)` and pass its
    `.chat` to `LLMRolloutProvider(chat_fn=...)` — no code change needed."""

    def __init__(self, model: Optional[str] = None, llm=None, hide_assert: bool = True,
                 temperature: float = 1.0, top_p: float = 1.0, max_tokens: int = 2048,
                 logger=None, **llm_kwargs):
        self.log = logger or logging.getLogger("rl_pipeline.inference.vllm")
        self.hide_assert = hide_assert
        from vllm import LLM, SamplingParams  # optional dependency
        self._SamplingParams = SamplingParams
        self.llm = llm if llm is not None else LLM(model=model, **llm_kwargs)
        self.system_prompt = prompts.system_prompt()
        self.temperature, self.top_p, self.max_tokens = temperature, top_p, max_tokens

    def __call__(self, prog: Program, n: int) -> List[List[str]]:
        source = strip_postcondition(prog.source) if self.hide_assert else prog.source
        return self._chat_n(prompts.GENERATE_PROMPT.format(program=source), n)

    def refine(self, prog: Program, feedback: str, n: int = 1) -> List[List[str]]:
        source = strip_postcondition(prog.source) if self.hide_assert else prog.source
        return self._chat_n(
            prompts.REFINE_PROMPT.format(program=source, feedback=feedback), n
        )

    def _chat_n(self, prompt: str, n: int) -> List[List[str]]:
        messages = [{"role": "user", "content": prompt}]
        if self.system_prompt:
            messages.insert(0, {"role": "system", "content": self.system_prompt})
        sp = self._SamplingParams(n=n, temperature=self.temperature,
                                  top_p=self.top_p, max_tokens=self.max_tokens)
        try:
            outs = self.llm.chat(messages, sp, use_tqdm=False)
        except Exception as e:
            self.log.warning("vLLM generate failed: %s", e)
            return [[] for _ in range(n)]
        return [extract_invariants(o.text) for o in outs[0].outputs]


# ── result ───────────────────────────────────────────────────────────────────

@dataclass
class InferenceResult:
    program: str
    final_invariants: List[str]
    annotated_code: str
    verified: Optional[bool]
    reroll_count: int
    n_rollouts: int
    rollouts: List[List[str]] = field(default_factory=list)
    refine_rounds: int = 0        # LLM refine rounds actually run (<= m_refine)


# ── framework ─────────────────────────────────────────────────────────────────

class InferenceFramework:
    """loop -> invariants.  Generate rollouts, union them, optionally run m LLM
    refine rounds on the merged pool (cheap WP precheck -> feedback -> refined
    candidates JOIN the pool, originals kept), then prune with real Houdini
    (Frama-C/WP) and verify with Frama-C.  m_refine=0 reproduces the plain
    pipeline exactly.  INDEPENDENT of the reward component — it does NOT sample
    positives/negatives (that is only the reward's job)."""

    def __init__(
        self,
        source: str,
        rollout_provider=None,
        invariant_filter=None,
        n_rollouts: int = 4,
        max_rerolls: int = 1,
        hide_assert: bool = True,
        m_refine: int = 0,
        refine_samples: int = 1,
        logger: Optional[logging.Logger] = None,
    ):
        self.prog = parse_program(source)
        # hide_assert applies to the DEFAULT provider; a passed-in provider keeps
        # its own setting (set hide_assert on it directly).
        self.provider = rollout_provider or LLMRolloutProvider(logger=logger, hide_assert=hide_assert)
        self.filter = invariant_filter or filters.auto_filter(logger)
        self.n_rollouts = n_rollouts
        self.max_rerolls = max_rerolls
        self.m_refine = m_refine
        self.refine_samples = refine_samples
        self.log = logger or logging.getLogger("rl_pipeline.inference")
        if self.n_rollouts < 1:
            raise ValueError("n_rollouts must be at least 1")
        if self.max_rerolls < 0 or self.m_refine < 0:
            raise ValueError("max_rerolls and m_refine must be non-negative")
        if self.refine_samples < 1:
            raise ValueError("refine_samples must be at least 1")

    def _verify(self, annotated_code: str) -> Optional[bool]:
        """Frama-C verify the final annotated code (None if frama-c unavailable)."""
        if not filters.frama_c_available():
            return None
        try:
            from src.output_verify import OutputVerifier
        except Exception:
            return None
        tmpdir = tempfile.mkdtemp(prefix="rlinfer_")
        cpath = os.path.join(tmpdir, "prog.c")
        try:
            with open(cpath, "w") as f:
                f.write(annotated_code)
            v = OutputVerifier(logger=self.log)
            v.run(cpath)
            syntax = getattr(v, "syntax_correct", False) or getattr(v, "syntax_error", "") == "syntax Correct"
            valid = bool(v.validate_result) and all(v.validate_result)
            has_target = bool(self.prog.post)
            satisfy = bool(v.verify_result) and all(v.verify_result) if has_target else True
            return bool(syntax and valid and satisfy)
        except Exception as e:
            self.log.warning("verify failed: %s", e)
            return None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _refine_loop(self, pool: List[str], loop_idx: int) -> tuple:
        """m rounds of: WP precheck (syntax + at most two WP passes) -> feedback ->
        LLM refine -> refined candidates join the pool (originals kept: a later
        companion can rescue an iron reject; the final full Houdini adjudicates).
        Stops early when nothing is rejected or the pool reaches a fixpoint."""
        stage = filters.precheck_stage(self.filter)
        if stage is None:
            self.log.warning("m_refine=%d but filter has no WP precheck stage "
                             "(frama-c unavailable?); skipping refine", self.m_refine)
            return pool, 0
        refine_fn = getattr(self.provider, "refine", None)
        if refine_fn is None:
            self.log.warning("m_refine=%d but provider has no refine(); skipping",
                             self.m_refine)
            return pool, 0
        rounds = 0
        for _ in range(self.m_refine):
            if not pool:
                break
            verdicts = stage.precheck(self.prog, loop_idx, pool)
            if not any(not v.kept for v in verdicts):
                break                                  # nothing to refine
            feedback = filters.build_feedback(verdicts)
            refined = refine_fn(self.prog, feedback, self.refine_samples)
            rounds += 1
            new_pool = dedup_normalized(list(pool) + [c for r in refined for c in r])
            if len(new_pool) == len(pool):
                break                                  # fixpoint: no new candidates
            self.log.info("refine round %d: pool %d -> %d", rounds, len(pool), len(new_pool))
            pool = new_pool
        return pool, rounds

    def _attempt(self):
        loop_idx = 0
        rollouts = self.provider(self.prog, self.n_rollouts)
        # combine (union) across all rollouts, then prune with real Houdini
        # (Frama-C/WP).  No positives -> no lite pre-filter; Houdini is the judge.
        union = dedup_normalized(c for r in rollouts for c in r)
        refine_rounds = 0
        if self.m_refine > 0:
            union, refine_rounds = self._refine_loop(union, loop_idx)
        survivors = self.filter.filter(self.prog, loop_idx, union, positives=None)
        annotated = annotate.build_annotated(self.prog, survivors, loop_idx)
        verified = self._verify(annotated)
        return InferenceResult(
            program=self.prog.func_name,
            final_invariants=survivors,
            annotated_code=annotated,
            verified=verified,
            reroll_count=0,
            n_rollouts=self.n_rollouts,
            rollouts=rollouts,
            refine_rounds=refine_rounds,
        )

    def run(self) -> InferenceResult:
        best: Optional[InferenceResult] = None
        rerolls = 0
        for attempt in range(self.max_rerolls + 1):
            res = self._attempt()
            rerolls = attempt
            if best is None or _better(res, best):
                best = res
            if res.verified is True:
                break
            if attempt < self.max_rerolls:
                self.log.info("re-rolling (attempt %d, verified=%s)", attempt + 1, res.verified)
        assert best is not None
        best.reroll_count = rerolls
        return best


def _better(a: InferenceResult, b: InferenceResult) -> bool:
    ra = (1 if a.verified else 0, len(a.final_invariants))
    rb = (1 if b.verified else 0, len(b.final_invariants))
    return ra > rb
