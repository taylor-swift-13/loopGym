"""
Mutation operators for negative-example generation.

Two families:

  * loop mutations   — textual edits to the loop (guard + body) that model
                       REAL bug patterns (off-by-one, wrong direction, swapped
                       operator/variable, dropped/duplicated update, wrong
                       guard bound).  Running a mutated program yields loop-entry
                       valuations that drift off the correct reachable set.
  * trace mutations  — perturb a real (positive) valuation directly (no
                       execution): +/-k, sign flip, single-var and joint.

Coverage is intentionally broad ("尽可能覆盖真实的错误 / 尽可能广泛").  Neither
family is trusted to be negative on its own — the ExampleSampler filters the
candidates against the spec and the reachable set afterwards.
"""
from __future__ import annotations

import re
from typing import Dict, List

from ..common.program import Program
from ..common.state import State


# ── loop mutations (produce full mutated source strings) ─────────────────────

def _single_site_variants(region: str, pattern: str, repl_fn) -> List[str]:
    """For each match of `pattern` in region, produce one variant with that site replaced."""
    out: List[str] = []
    for m in re.finditer(pattern, region):
        rep = repl_fn(m)
        if rep is None or rep == m.group(0):
            continue
        variant = region[:m.start()] + rep + region[m.end():]
        if variant != region:
            out.append(variant)
    return out


def mutate_loop(prog: Program, loop_idx: int = 0, max_variants: int = 48) -> List[str]:
    """Return full mutated source strings (loop region edited)."""
    loop = prog.loops[loop_idx]
    lo, hi = loop.kw_start, loop.body_close + 1
    region = prog.source[lo:hi]
    prefix, suffix = prog.source[:lo], prog.source[hi:]

    variants: List[str] = []

    # 1. numeric literal +/- 1  (off-by-one on constants, guard bounds)
    def _num_pm(delta):
        return _single_site_variants(
            region, r"(?<![\w.])(-?\d+)(?![\w.])",
            lambda m: str(int(m.group(1)) + delta),
        )
    variants += _num_pm(1) + _num_pm(-1)

    # 2. swap additive direction  +  <->  -   (one site at a time)
    variants += _single_site_variants(region, r"\s([+\-])\s", lambda m: (" - " if m.group(1) == "+" else " + "))

    # 3. swap operator families  *  <->  +
    variants += _single_site_variants(region, r"\s([*+])\s", lambda m: (" + " if m.group(1) == "*" else " * "))

    # 4. comparison operator flips (mostly hits the guard)
    cmp_map = {">": ">=", ">=": ">", "<": "<=", "<=": "<", "==": "!=", "!=": "=="}
    for op, rep in cmp_map.items():
        pat = r"(?<![<>=!])" + re.escape(op) + r"(?![=])" if op in ("<", ">") else re.escape(op)
        variants += _single_site_variants(region, pat, (lambda r: (lambda m: r))(rep))

    # 5. swap a variable on an assignment RHS with another pre_var
    pv = prog.pre_vars
    for m in re.finditer(r"(\w+)\s*=\s*([^;]+);", region):
        rhs = m.group(2)
        for var in pv:
            for other in pv:
                if other == var:
                    continue
                if re.search(r"\b" + re.escape(var) + r"\b", rhs):
                    new_rhs = re.sub(r"\b" + re.escape(var) + r"\b", other, rhs, count=1)
                    if new_rhs != rhs:
                        new_region = region[:m.start(2)] + new_rhs + region[m.end(2):]
                        variants.append(new_region)

    # 6. drop one update statement in the body
    body_lo = loop.body_open - lo + 1
    body = region[body_lo: loop.body_close - lo]
    for m in re.finditer(r"[ \t]*\w+\s*=\s*[^;]+;", body):
        dropped = body[:m.start()] + body[m.end():]
        variants.append(region[:body_lo] + dropped + region[loop.body_close - lo:])

    # dedup, rebuild full sources
    seen, sources = set(), []
    for v in variants:
        if v in seen or v == region:
            continue
        seen.add(v)
        sources.append(prefix + v + suffix)
        if len(sources) >= max_variants:
            break
    return sources


# ── trace mutations (perturb a positive valuation directly) ──────────────────

_DELTAS = (1, -1, 2, -2, 3, -3, 5, -5)


def mutate_traces(states: List[State], max_out: int = 4000) -> List[State]:
    """Perturb positive valuations to nearby off-trace candidate valuations."""
    out: List[State] = []
    seen = set()

    def _emit(vars_: Dict[str, int], pre):
        st = State(vars=vars_, pre=dict(pre))
        k = st.key()
        if k not in seen:
            seen.add(k)
            out.append(st)

    for s in states:
        keys = list(s.vars.keys())
        # single-variable perturbations
        for k in keys:
            for d in _DELTAS:
                v = dict(s.vars)
                v[k] = v[k] + d
                _emit(v, s.pre)
            # sign flip
            v = dict(s.vars)
            v[k] = -v[k]
            _emit(v, s.pre)
        # joint small perturbation
        for d in (1, -1, 2):
            v = {k: s.vars[k] + d for k in keys}
            _emit(v, s.pre)
        if len(out) >= max_out:
            break
    return out[:max_out]
