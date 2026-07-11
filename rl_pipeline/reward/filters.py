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
and a verdict-returning variant:
  filter_verdicts(...) -> (survivors, List[Verdict])   # per-invariant keep/drop + reason
HoudiniFilter additionally offers precheck() — syntax scrub + ONE WP round (no
fixpoint), the cheap feedback source for the refine loop.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..common.program import Program
from ..common.state import State, eval_predicate, normalize_invariant, extract_invariants
from . import annotate

# ACSL / boolean tokens that are not program variables
_ACSL_STOPWORDS = {"at", "Pre", "Post", "old", "result", "true", "false",
                   "True", "False", "None", "and", "or", "not"}

def frama_c_available() -> bool:
    return shutil.which("frama-c") is not None


@dataclass
class Verdict:
    """Per-invariant filter outcome.  `stage` values:
      scope    — unparsable / names out-of-scope identifiers
      unsound  — violated by a sampled reachable state
      syntax   — Frama-C rejects it (parse/typecheck)
      wp       — failed the WP precheck; the reason states WHICH proof broke:
                 establishment (false at loop entry) or preservation (not
                 maintained by one iteration, with the pool as hypothesis —
                 pool-relative: a new companion can rescue it)
      houdini  — pruned in a later round (casualty: lost its supporting invariants),
                 or kept=True for survivors
    Reasons are target-free (never mention the assert/postcondition) so they can
    be fed back to a closed-book model."""
    invariant: str
    kept: bool
    stage: str
    reason: str


def precheck_stage(flt):
    """The stage of `flt` that offers precheck() (HoudiniFilter), or None."""
    if hasattr(flt, "precheck"):
        return flt
    for st in getattr(flt, "stages", []):
        if hasattr(st, "precheck"):
            return st
    return None


def build_feedback(verdicts: List["Verdict"]) -> str:
    """Render verdicts as the table prompt/refine_prompt.txt expects (never raw
    Frama-C output; reasons are target-free by construction)."""
    lines = []
    for v in verdicts:
        tag = ("KEPT (passing so far)" if v.kept
               else f"REJECTED [{v.stage}]: {v.reason}")
        lines.append(f"loop invariant {v.invariant};   -- {tag}")
    return "\n".join(lines)


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
        return self.filter_verdicts(prog, loop_idx, invariants, positives)[0]

    def filter_verdicts(self, prog: Program, loop_idx: int, invariants: List[str],
                        positives: Optional[List[State]] = None
                        ) -> Tuple[List[str], List[Verdict]]:
        sample, values = self._positives(positives or [])
        kept: List[str] = []
        verdicts: List[Verdict] = []
        for inv in invariants:
            cond = normalize_invariant(inv)
            if not cond:
                verdicts.append(Verdict(inv, False, "scope", "unparsable invariant"))
                continue
            # scope gate: reject invariants naming out-of-scope identifiers
            # (Frama-C would reject them, and an undeclared name can break parsing
            #  of the whole file).
            bad = out_of_scope_ids(cond, prog.pre_vars)
            if bad:
                verdicts.append(Verdict(cond, False, "scope",
                                        "out-of-scope identifiers: " + ", ".join(sorted(set(bad)))))
                continue
            witness = next((s for s in sample if eval_predicate(cond, s) is False), None)
            if witness is not None:
                verdicts.append(Verdict(cond, False, "unsound",
                                        f"false at the reachable state ({witness.render()})"))
                continue
            kept.append(cond)
            verdicts.append(Verdict(cond, True, "positive", "passing so far"))
        return kept, verdicts

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
        return self.filter_verdicts(prog, loop_idx, invariants, positives)[0]

    def filter_verdicts(self, prog: Program, loop_idx: int, invariants: List[str],
                        positives: Optional[List[State]] = None
                        ) -> Tuple[List[str], List[Verdict]]:
        verdicts: List[Verdict] = []
        invs: List[str] = []
        for i in invariants:
            cond = normalize_invariant(i)
            if cond:
                invs.append(cond)
            else:
                verdicts.append(Verdict(i, False, "scope", "unparsable invariant"))
        # cheap positive pre-filter first (mirrors the inference pipeline)
        if self.prefilter_positives and positives:
            invs, pv = self._positive.filter_verdicts(prog, loop_idx, invs, positives)
            verdicts += [v for v in pv if not v.kept]
        if not invs:
            return [], verdicts
        invs, syn_verdicts = self._scrub_verdicts(prog, loop_idx, invs)
        verdicts += syn_verdicts
        if not invs:
            return [], verdicts
        code = annotate.build_annotated(prog, invs, loop_idx)
        tmpdir = tempfile.mkdtemp(prefix="rlreward_")
        cpath = os.path.join(tmpdir, "prog.c")
        record: dict = {}
        try:
            with open(cpath, "w") as f:
                f.write(code)
            verifier = self._OutputVerifier(logger=self.log)
            pruner = self._HoudiniPruner(logger=self.log)
            pruned_code, _valid = pruner.hudini(code, verifier, cpath, record=record)
            survivors = extract_invariants(pruned_code) if pruned_code else []
        except Exception as e:  # frama-c hiccup -> conservative empty
            self.log.warning("Houdini filter failed: %s", e)
            verdicts += [Verdict(i, False, "houdini", "frama-c error during Houdini")
                         for i in invs]
            return [], verdicts
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        verdicts += self._houdini_verdicts(invs, survivors, record)
        return survivors, verdicts

    @staticmethod
    def _houdini_verdicts(invs: List[str], survivors: List[str], record: dict) -> List[Verdict]:
        """Attribute each pruned invariant: round-0 failure = iron reject (stage
        "wp"), later rounds = casualty of losing support (stage "houdini")."""
        surv = {normalize_invariant(s) for s in survivors}
        iron = set()
        rounds = record.get("rounds") or []
        if rounds:
            r0_invs, r0_ok = rounds[0]["invariants"], rounds[0]["validate_result"]
            for inv, ok in zip(r0_invs, r0_ok):   # positional, same order as source
                if not ok:
                    iron.add(normalize_invariant(inv))
        out: List[Verdict] = []
        for inv in invs:
            key = normalize_invariant(inv)
            if key in surv:
                out.append(Verdict(inv, True, "houdini", "inductive (survived Houdini)"))
            elif key in iron:
                out.append(Verdict(inv, False, "wp",
                                   "not inductive with the current set — it may need "
                                   "a companion invariant to support it"))
            else:
                out.append(Verdict(inv, False, "houdini",
                                   "pruned in a later Houdini round (its supporting "
                                   "invariants were removed)"))
        return out

    def _scrub_verdicts(self, prog: Program, loop_idx: int, invs: List[str]
                        ) -> Tuple[List[str], List[Verdict]]:
        dropped: List[Tuple[str, str]] = []
        kept = self._syntax_scrub(prog, loop_idx, invs, dropped=dropped)
        return kept, [Verdict(d, False, "syntax", f"frama-c: {msg}")
                      for d, msg in dropped]

    def precheck(self, prog: Program, loop_idx: int, invariants: List[str]
                 ) -> List[Verdict]:
        """Cheap refine-feedback pass: syntax scrub + at most TWO WP rounds, no
        fixpoint.  Two rounds because an establishment failure makes WP's
        preservation hypotheses inconsistent (the entry state contradicts the
        assumed invariant), turning every OTHER preservation goal vacuously
        Valid — so pass 1 harvests the establishment verdicts (independent,
        hence reliable), and pass 2 re-checks preservation with the
        entry-failing candidates removed.  Every rejection carries its
        specific WHY.  Rejections are pool-relative (new companions can rescue
        them); a pass is only "passing so far", NOT proven inductive."""
        verdicts: List[Verdict] = []
        invs: List[str] = []
        for i in invariants:
            cond = normalize_invariant(i)
            if cond:
                invs.append(cond)
            else:
                verdicts.append(Verdict(i, False, "scope", "unparsable invariant"))
        if not invs:
            return verdicts
        invs, syn_verdicts = self._scrub_verdicts(prog, loop_idx, invs)
        verdicts += syn_verdicts
        if not invs:
            return verdicts

        ok1, status1 = self._wp_round(prog, loop_idx, invs)
        est_failed = [inv for inv in invs
                      if (status1.get(inv) or {}).get("Establishment") is False]
        for inv in est_failed:
            verdicts.append(Verdict(inv, False, "wp",
                                    "fails establishment: it does not hold when the "
                                    "loop is first reached — check it against the "
                                    "initialization"))
        rest = [inv for inv in invs if inv not in est_failed]
        if not rest:
            return verdicts
        if est_failed:   # pass 2: honest preservation without the vacuous-truth mask
            ok2, status2 = self._wp_round(prog, loop_idx, rest)
        else:
            ok2, status2 = ok1, status1
        for inv in rest:
            if ok2.get(inv, True):
                verdicts.append(Verdict(inv, True, "wp", "passing so far"))
                continue
            st = status2.get(inv) or {}
            if st.get("Preservation") is False:
                reason = ("fails preservation: one loop iteration does not "
                          "maintain it (even assuming the whole pool) — adjust it "
                          "to the loop's step, or add a companion invariant that "
                          "supports it")
            else:
                reason = ("not inductive with the current set — it may need a "
                          "companion invariant to support it")
            verdicts.append(Verdict(inv, False, "wp", reason))
        return verdicts

    def _wp_round(self, prog: Program, loop_idx: int, invs: List[str]
                  ) -> Tuple[dict, dict]:
        """ONE WP run over `invs`.  Returns (ok, status): ok maps invariant ->
        combined bool (missing entries treated as passing); status maps
        invariant -> {'Establishment': bool, 'Preservation': bool} where the
        goal split could be line-mapped."""
        code = annotate.build_annotated(prog, invs, loop_idx)
        tmpdir = tempfile.mkdtemp(prefix="rlwp_")
        cpath = os.path.join(tmpdir, "prog.c")
        vr: List[bool] = []
        by_line: dict = {}
        try:
            with open(cpath, "w") as f:
                f.write(code)
            verifier = self._OutputVerifier(logger=self.log)
            verifier.run(cpath)
            vr = list(verifier.validate_result or [])
            by_line = dict(getattr(verifier, "goal_status_by_line", {}) or {})
        except Exception as e:
            self.log.warning("WP round failed: %s", e)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        if len(vr) != len(invs):   # unmappable -> conservative: passing so far
            if vr:
                self.log.warning("WP round: %d results for %d invariants; "
                                 "treating unmapped as passing", len(vr), len(invs))
            vr = vr[:len(invs)] + [True] * (len(invs) - len(vr))
        inv_line = {}
        for ln, text in enumerate(code.splitlines(), 1):
            for inv in invs:
                if f"loop invariant {inv};" in text:
                    inv_line[inv] = ln
        ok = dict(zip(invs, vr))
        status = {inv: by_line[inv_line[inv]] for inv in invs
                  if inv in inv_line and inv_line[inv] in by_line}
        return ok, status


    def _syntax_scrub(self, prog: Program, loop_idx: int, invs: List[str],
                      dropped: Optional[List[Tuple[str, str]]] = None) -> List[str]:
        """Drop `loop invariant` entries FRAMA-C rejects (parse/typecheck): one
        kernel-only run per round; the error's line number maps back to the
        offending entry (each sits on its own line).  An unmappable error falls
        back to per-clause checks.  `dropped`, if given, collects
        (entry, frama-c error text) pairs — the WHY for refine feedback."""
        import subprocess

        def kernel_error(code: str):
            """None if clean, else (line or -1, first error message line)."""
            tmpdir = tempfile.mkdtemp(prefix="rlsyn_")
            cpath = os.path.join(tmpdir, "prog.c")
            try:
                with open(cpath, "w") as f:
                    f.write(code)
                res = subprocess.run(["frama-c", cpath], capture_output=True,
                                     text=True, timeout=30)
                err = res.stdout + res.stderr
                if res.returncode == 0 and "user error" not in err:
                    return None                       # parses clean
                # frama-c wraps long messages onto indented continuation lines
                m = re.search(rf"{re.escape(cpath)}:(\d+):\s*([^\n]*(?:\n[ \t]+[^\n]*)*)", err)
                if m:
                    msg = re.sub(r"\s+", " ", m.group(2)).strip()
                    msg = re.sub(r"^Warning:\s*", "", msg)
                    return int(m.group(1)), msg[:120]
                return -1, ""                         # error, no line info
            except Exception:
                return -1, ""
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)

        def note(inv: str, msg: str):
            self.log.info("syntax scrub (frama-c): dropping %r (%s)", inv, msg)
            if dropped is not None:
                dropped.append((inv, msg or "parse/typecheck error"))

        invs = list(invs)
        for _ in range(len(invs) + 1):
            if not invs:
                return []
            code = annotate.build_annotated(prog, invs, loop_idx)
            hit_err = kernel_error(code)
            if hit_err is None:
                return invs
            line, msg = hit_err
            if line > 0:
                text = code.splitlines()[line - 1]
                hit = next((i for i in invs if i in text), None)
                if hit is not None:
                    note(hit, msg)
                    invs.remove(hit)
                    continue
            # unmappable: per-clause fallback
            self.log.info("syntax scrub: per-clause fallback over %d entries", len(invs))
            kept = []
            for i in invs:
                res = kernel_error(annotate.build_annotated(prog, [i], loop_idx))
                if res is None:
                    kept.append(i)
                else:
                    note(i, res[1])
            return kept
        return invs


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

    def filter_verdicts(self, prog: Program, loop_idx: int, invariants: List[str],
                        positives: Optional[List[State]] = None
                        ) -> Tuple[List[str], List[Verdict]]:
        invs = invariants
        verdicts: List[Verdict] = []
        for st in self.stages:
            if not invs:
                break
            invs, vs = st.filter_verdicts(prog, loop_idx, invs, positives)
            # keep drop verdicts from every stage; only the LAST stage's keeps count
            verdicts = [v for v in verdicts if not v.kept] + vs
        return invs, verdicts


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
