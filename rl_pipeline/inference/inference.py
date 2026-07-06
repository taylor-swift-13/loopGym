"""
InferenceFramework — Component 3.

The generation loop:  sample rollouts -> positive-filter -> combine -> Houdini -> verify.

It collaborates with the other two components:
  * ExampleSampler (Component 1) supplies the positive states for the fast filter
    (and, reused, the negatives for scoring).
  * RewardCalculator (Component 2) scores the batch and drives the re-roll decision.

Rollouts come from a swappable provider:
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

from ..common.program import Program, parse_program, strip_postcondition
from ..common.state import extract_invariants, dedup_normalized
from ..reward import annotate
from ..reward import filters
from ..sampler import ExampleSampler, ExampleSet


# ── rollout providers ────────────────────────────────────────────────────────

class MockRolloutProvider:
    """Returns pre-baked invariant sets; cycles if asked for more than provided."""

    def __init__(self, rollouts: List[List[str]]):
        self.rollouts = rollouts

    def __call__(self, prog: Program, n: int) -> List[List[str]]:
        if not self.rollouts:
            return [[] for _ in range(n)]
        return [list(self.rollouts[i % len(self.rollouts)]) for i in range(n)]


_PROMPT = """You are given a C function. Produce the strongest inductive ACSL loop
invariants that capture the loop's behavior (conservation/relational laws + tight
progress bounds). Output ONLY invariant lines, each formatted exactly as:
loop invariant <expr>;

Program:
{program}
"""


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
        from ..common import paths
        paths.ensure_src_on_path()
        from llm import Chatbot  # type: ignore
        try:
            from config import LLMConfig  # type: ignore
            cfg = LLMConfig()
        except Exception:
            from llm import LLMConfig  # type: ignore
            cfg = LLMConfig()
        bot = Chatbot(cfg)
        return bot.chat

    def __call__(self, prog: Program, n: int) -> List[List[str]]:
        out: List[List[str]] = []
        # closed-book: hide the assert (goal) so the model can't restate it
        source = strip_postcondition(prog.source) if self.hide_assert else prog.source
        prompt = _PROMPT.format(program=source)
        for _ in range(n):
            try:
                resp = self.chat_fn(prompt)
            except Exception as e:
                self.log.warning("LLM call failed: %s", e)
                resp = ""
            out.append(extract_invariants(resp))
        return out


# ── result ───────────────────────────────────────────────────────────────────

@dataclass
class InferenceResult:
    program: str
    final_invariants: List[str]
    annotated_code: str
    verified: Optional[bool]
    batch_score: Optional[float]
    reroll_count: int
    n_rollouts: int
    rollouts: List[List[str]] = field(default_factory=list)
    filtered_rollouts: List[List[str]] = field(default_factory=list)


# ── framework ─────────────────────────────────────────────────────────────────

class InferenceFramework:
    def __init__(
        self,
        source: str,
        rollout_provider=None,
        examples: Optional[ExampleSet] = None,
        invariant_filter=None,
        reward_calculator=None,
        n_rollouts: int = 4,
        max_rerolls: int = 1,
        reroll_threshold: float = 0.6,
        sampler_kwargs: Optional[dict] = None,
        hide_assert: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        self.source = source
        self.prog = parse_program(source)
        # hide_assert applies to the DEFAULT provider; a passed-in provider keeps
        # its own setting (set hide_assert on it directly).
        self.provider = rollout_provider or LLMRolloutProvider(logger=logger, hide_assert=hide_assert)
        self.examples = examples
        self.filter = invariant_filter or filters.auto_filter(logger)
        self.positive = filters.PositiveFilter()
        self.reward_calc = reward_calculator
        self.n_rollouts = n_rollouts
        self.max_rerolls = max_rerolls
        self.reroll_threshold = reroll_threshold
        self.sampler_kwargs = sampler_kwargs or {}
        self.log = logger or logging.getLogger("rl_pipeline.inference")

    def _get_examples(self) -> ExampleSet:
        if self.examples is None:
            self.examples = ExampleSampler(self.source, **self.sampler_kwargs).sample()
        return self.examples

    def _verify(self, annotated_code: str) -> Optional[bool]:
        """Frama-C verify the final annotated code (None if frama-c unavailable)."""
        if not filters.frama_c_available():
            return None
        from ..common import paths
        paths.ensure_src_on_path()
        try:
            from output_verify import OutputVerifier  # type: ignore
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
            has_assert = "assert" in annotated_code
            satisfy = (all(v.verify_result) if v.verify_result else False) or not has_assert
            return bool(syntax and valid and satisfy)
        except Exception as e:
            self.log.warning("verify failed: %s", e)
            return None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _attempt(self, examples: ExampleSet):
        loop_idx = 0
        positives = examples.pos(loop_idx)
        rollouts = self.provider(self.prog, self.n_rollouts)

        # positive-filter each rollout (fast, cheap soundness pre-filter)
        filtered = [self.positive.filter(self.prog, loop_idx, r, positives) for r in rollouts]

        # combine (union) across surviving rollouts
        union = dedup_normalized(c for fr in filtered for c in fr)

        # Houdini prune + build final annotated code
        survivors = self.filter.filter(self.prog, loop_idx, union, positives)
        annotated = annotate.build_annotated(self.prog, survivors, loop_idx)
        verified = self._verify(annotated)

        batch_score = None
        if self.reward_calc is not None:
            br = self.reward_calc.compute(self.source, rollouts, examples=examples)
            batch_score = br.batch_score

        return InferenceResult(
            program=self.prog.func_name,
            final_invariants=survivors,
            annotated_code=annotated,
            verified=verified,
            batch_score=batch_score,
            reroll_count=0,
            n_rollouts=self.n_rollouts,
            rollouts=rollouts,
            filtered_rollouts=filtered,
        )

    def run(self) -> InferenceResult:
        examples = self._get_examples()
        best: Optional[InferenceResult] = None
        for attempt in range(self.max_rerolls + 1):
            res = self._attempt(examples)
            res.reroll_count = attempt
            if best is None or _better(res, best):
                best = res
            done = res.verified is True or (
                res.batch_score is not None and res.batch_score >= self.reroll_threshold)
            if done:
                break
            if attempt < self.max_rerolls:
                self.log.info("re-rolling (attempt %d, batch_score=%s)", attempt + 1, res.batch_score)
        return best


def _better(a: InferenceResult, b: InferenceResult) -> bool:
    ra = (1 if a.verified else 0, a.batch_score if a.batch_score is not None else -1, len(a.final_invariants))
    rb = (1 if b.verified else 0, b.batch_score if b.batch_score is not None else -1, len(b.final_invariants))
    return ra > rb
