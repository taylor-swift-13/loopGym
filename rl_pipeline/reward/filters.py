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

# Complexity gate: a real loop invariant is a short law (the longest honest ones
# in the benchmark suite are ~80 chars / a handful of atoms).  Without a cap, a
# policy can memorize the sampled negative set into ONE mega-predicate
# (`!(x==1 && y==2) && !(x==3 && ...)`) that rejects every negative while being
# semantically empty — the ultimate reward hack.  Oversized candidates are
# dropped, not truncated.
_MAX_INV_CHARS = 160
_MAX_INV_ATOMS = 12
_ATOM_RE = re.compile(r"==|!=|<=|>=|<|>")


def too_complex(inv: str) -> bool:
    return len(inv) > _MAX_INV_CHARS or len(_ATOM_RE.findall(inv)) > _MAX_INV_ATOMS


def frama_c_available() -> bool:
    return shutil.which("frama-c") is not None


def out_of_scope_ids(inv: str, allowed) -> List[str]:
    """Identifiers referenced by `inv` that are neither program vars nor ACSL tokens."""
    stripped = re.sub(r"\\[A-Za-z_]+", " ", inv)      # drop \at, \old, \forall ...
    ids = re.findall(r"[A-Za-z_]\w*", stripped)
    allow = set(allowed) | _ACSL_STOPWORDS
    return [i for i in ids if i not in allow]


# Soundness checks evaluate every candidate on every positive; nondeterministic
# programs can yield hundreds of thousands of positives, making that quadratic
# blow-up the dominant cost.  A stratified subsample bounds it — but the
# per-variable EXTREME states must always stay in: they are exactly the
# witnesses that filter overfit sample-boxes (`v <= max_observed`).
_MAX_FILTER_POSITIVES = 4096


def representative_positives(positives: List[State]) -> List[State]:
    if len(positives) <= _MAX_FILTER_POSITIVES:
        return positives
    idxs = set()
    lo: dict = {}
    hi: dict = {}
    for i, s in enumerate(positives):
        for v, val in s.vars.items():
            if v not in lo or val < lo[v][0]:
                lo[v] = (val, i)
            if v not in hi or val > hi[v][0]:
                hi[v] = (val, i)
    idxs.update(i for _val, i in lo.values())
    idxs.update(i for _val, i in hi.values())
    step = max(1, len(positives) // (_MAX_FILTER_POSITIVES - len(idxs)))
    idxs.update(range(0, len(positives), step))
    return [positives[i] for i in sorted(idxs)]


# Single-variable predicates are checked against the FULL per-variable value
# sets, not the state subsample: `v != c` (and any interval / modular variant)
# is violated by exactly the positives whose v-value falsifies it, and an
# adversary who knows the (deterministic) subsample stride can pick constants
# from the skipped states — sound-looking on the subsample, unsound in truth,
# and still rejecting negatives that share those values.
_DISEQ_RE = re.compile(r"^\s*(?:!\s*\(\s*(\w+)\s*==\s*(-?\d+)\s*\)|(\w+)\s*!=\s*(-?\d+))\s*$")
# window-exclusion fast path: `!(A <= v && v <= B)` — exact at any value-set size
_IVAL_RE = re.compile(
    r"^\s*!\s*\(\s*(-?\d+)\s*<=?\s*(\w+)\s*&&\s*(\w+)\s*<=?\s*(-?\d+)\s*\)\s*$")
# generic single-var exact check is an eval per observed value — cap the scan
_MAX_EXACT_VALUES = 20000


class PositiveFilter:
    """Keep invariants that are (a) in scope and (b) not violated by any positive state."""

    name = "positive"

    def __init__(self):
        self._rep_cache: dict = {}

    def _positives(self, positives: List[State]):
        """(representative subsample, per-var full value sets) — id-cached."""
        key = id(positives)
        rep = self._rep_cache.get(key)
        if rep is None or rep[0] is not positives:
            values: dict = {}
            for s in positives:
                for v, val in s.vars.items():
                    values.setdefault(v, set()).add(val)
            rep = (positives, representative_positives(positives), values)
            self._rep_cache[key] = rep
        return rep[1], rep[2]

    def filter(self, prog: Program, loop_idx: int, invariants: List[str],
               positives: Optional[List[State]] = None) -> List[str]:
        sample, values = self._positives(positives or [])
        kept: List[str] = []
        for inv in invariants:
            cond = normalize_invariant(inv)
            if not cond:
                continue
            # complexity gate: drop memorization-sized predicates (see too_complex)
            if too_complex(cond):
                continue
            # scope gate: reject invariants naming out-of-scope identifiers
            # (Frama-C would reject them, and an undeclared name can break parsing
            #  of the whole file).
            if out_of_scope_ids(cond, prog.pre_vars):
                continue
            # single-variable predicates get an EXACT check against all
            # observed values of that variable (see comment on _DISEQ_RE)
            if self._exact_single_var_unsound(cond, values):
                continue
            unsound = any(eval_predicate(cond, s) is False for s in sample)
            if not unsound:
                kept.append(cond)
        return kept

    @staticmethod
    def _exact_single_var_unsound(cond: str, values: dict) -> bool:
        """True iff `cond` constrains a single program variable and some
        OBSERVED value of that variable falsifies it.  Fast paths for the two
        farm shapes (`v != c`, `!(a <= v && v <= b)`), generic per-value eval
        for everything else (modular tricks, shifted windows, …)."""
        m = _DISEQ_RE.match(cond)
        if m:
            v, c = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            return int(c) in values.get(v, ())
        m = _IVAL_RE.match(cond)
        if m and m.group(2) == m.group(3):
            v = m.group(2)
            a, b = int(m.group(1)), int(m.group(4))
            vv = values.get(v)
            return bool(vv) and any(a <= val <= b for val in vv)
        if "\\" in cond:                     # \at(...) references the pre-state
            return False
        ids = set(re.findall(r"[A-Za-z_]\w*", cond)) - _ACSL_STOPWORDS
        prog_ids = [i for i in ids if i in values]
        if len(prog_ids) != 1 or len(ids) != 1:
            return False
        v = prog_ids[0]
        vv = values[v]
        if len(vv) > _MAX_EXACT_VALUES:      # fall back to the state subsample
            return False
        return any(eval_predicate(cond, State(vars={v: val}, pre={})) is False
                   for val in vv)


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
