"""
Invariant filters — reduce a candidate invariant set to the ones that "survive".

  * HoudiniFilter  : real inductive filtering via src/houdini_pruner.HoudiniPruner
                     + src/output_verify.OutputVerifier (needs frama-c on PATH).
                     This is the authoritative "hudini 后的分数" filter.
  * PositiveFilter : drop invariants that are unsound on the sampled positive
                     (reachable) states.  A cheap proxy used (a) as the fast
                     pre-filter in the inference framework, and (b) as a fallback
                     when frama-c is unavailable.

Both expose the same interface:  filter(prog, loop_idx, invariants, positives) -> List[str]
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from typing import List, Optional

from ..common.program import Program
from ..common.state import State, eval_predicate, normalize_invariant, extract_invariants
from . import annotate

# ACSL / boolean tokens that are not program variables
_ACSL_STOPWORDS = {"at", "Pre", "Post", "old", "result", "true", "false",
                   "True", "False", "None", "and", "or", "not"}


def frama_c_available() -> bool:
    return shutil.which("frama-c") is not None


def out_of_scope_ids(inv: str, allowed) -> List[str]:
    """Identifiers referenced by `inv` that are neither program vars nor ACSL tokens."""
    stripped = re.sub(r"\\[A-Za-z_]+", " ", inv)      # drop \at, \old, \forall ...
    ids = re.findall(r"[A-Za-z_]\w*", stripped)
    allow = set(allowed) | _ACSL_STOPWORDS
    return [i for i in ids if i not in allow]


class PositiveFilter:
    """Keep invariants that are (a) in scope and (b) not violated by any positive state."""

    name = "positive"

    def filter(self, prog: Program, loop_idx: int, invariants: List[str],
               positives: Optional[List[State]] = None) -> List[str]:
        positives = positives or []
        kept: List[str] = []
        for inv in invariants:
            cond = normalize_invariant(inv)
            if not cond:
                continue
            # scope gate: reject invariants naming out-of-scope identifiers
            # (Frama-C would reject them, and an undeclared name can break parsing
            #  of the whole file).
            if out_of_scope_ids(cond, prog.pre_vars):
                continue
            unsound = any(eval_predicate(cond, s) is False for s in positives)
            if not unsound:
                kept.append(cond)
        return kept


class HoudiniFilter:
    """Inductive filtering with Frama-C/WP (reuses src/ HoudiniPruner + OutputVerifier)."""

    name = "houdini"

    def __init__(self, logger: Optional[logging.Logger] = None, prefilter_positives: bool = True):
        from ..common import paths
        paths.ensure_src_on_path()
        from houdini_pruner import HoudiniPruner  # type: ignore
        from output_verify import OutputVerifier  # type: ignore

        self._HoudiniPruner = HoudiniPruner
        self._OutputVerifier = OutputVerifier
        self.log = logger or logging.getLogger("rl_pipeline.reward.houdini")
        self._positive = PositiveFilter()
        self.prefilter_positives = prefilter_positives

    def filter(self, prog: Program, loop_idx: int, invariants: List[str],
               positives: Optional[List[State]] = None) -> List[str]:
        invs = [normalize_invariant(i) for i in invariants if normalize_invariant(i)]
        # cheap positive pre-filter first (mirrors the inference pipeline)
        if self.prefilter_positives and positives:
            invs = self._positive.filter(prog, loop_idx, invs, positives)
        if not invs:
            return []
        code = annotate.build_annotated(prog, invs, loop_idx)
        tmpdir = tempfile.mkdtemp(prefix="rlreward_")
        cpath = os.path.join(tmpdir, "prog.c")
        try:
            with open(cpath, "w") as f:
                f.write(code)
            verifier = self._OutputVerifier(logger=self.log)
            pruner = self._HoudiniPruner(logger=self.log)
            pruned_code, _valid = pruner.hudini(code, verifier, cpath)
            if not pruned_code:
                return []
            return extract_invariants(pruned_code)
        except Exception as e:  # frama-c hiccup -> conservative empty
            self.log.warning("Houdini filter failed: %s", e)
            return []
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class CascadeFilter:
    """Run cheap→expensive filters in sequence: Houdini-lite (positive) first, then
    real Houdini on the survivors.  The lite stage drops out-of-scope / unsound
    invariants for free, so Frama-C sees a smaller set (fewer WP goals, fewer
    Houdini iterations) — "先用 hudini-lite 再用真 hudini，加快速度"."""

    def __init__(self, stages):
        self.stages = stages
        self.name = "cascade(" + "->".join(getattr(s, "name", "?") for s in stages) + ")"

    def filter(self, prog: Program, loop_idx: int, invariants: List[str],
               positives: Optional[List[State]] = None) -> List[str]:
        invs = invariants
        for st in self.stages:
            if not invs:
                break
            invs = st.filter(prog, loop_idx, invs, positives)
        return invs


def auto_filter(logger: Optional[logging.Logger] = None):
    """Cascade (Houdini-lite → real Houdini) if frama-c is available, else lite only."""
    if frama_c_available():
        try:
            # lite stage already applied here, so disable HoudiniFilter's own prefilter
            return CascadeFilter([PositiveFilter(), HoudiniFilter(logger=logger, prefilter_positives=False)])
        except Exception:
            pass
    (logger or logging.getLogger("rl_pipeline.reward")).warning(
        "frama-c not available; using PositiveFilter (Houdini-lite) only")
    return PositiveFilter()
