"""
Self-contained C instrumentation + execution for collecting loop-ENTRY
valuations (the sampler's definition of a "sample").

No dependency on src/ — the sampler component is standalone.  We:
  1. instrument the target function to print the loop-entry variable valuation
     on entry, at the top of every iteration, and once on exit;
  2. generate a main() that calls the function with sampled inputs (respecting
     `requires`), sweeping a broad range of magnitudes/signs/edge values;
  3. compile with gcc and run, capturing the printed valuations.

Used for BOTH the correct program (positives) and mutated programs
(mutation-loop negatives).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional

from ..common.program import Program
from ..common.state import State

_ITER_CAP = 200          # per-loop iteration cap (keeps mutated/divergent loops finite)
_MARK = "__LH__"
_DEFAULT_MIN = -64
_DEFAULT_MAX = 64


def gcc_available() -> bool:
    return shutil.which("gcc") is not None


# ── input domain ────────────────────────────────────────────────────────────

def param_constraints(requires: str, params: List[str]) -> Dict[str, Dict[str, int]]:
    """Very small requires -> per-param {min,max} parser."""
    cons: Dict[str, Dict[str, int]] = {p: {"min": _DEFAULT_MIN, "max": _DEFAULT_MAX} for p in params}
    if not requires:
        return cons
    rules = [
        (r"(\w+)\s*==\s*(-?\d+)", lambda v: {"min": v, "max": v}),
        (r"(\w+)\s*>=\s*(-?\d+)", lambda v: {"min": v}),
        (r"(\w+)\s*>\s*(-?\d+)", lambda v: {"min": v + 1}),
        (r"(\w+)\s*<=\s*(-?\d+)", lambda v: {"max": v}),
        (r"(\w+)\s*<\s*(-?\d+)", lambda v: {"max": v - 1}),
    ]
    for pat, fn in rules:
        for m in re.finditer(pat, requires):
            name = m.group(1)
            if name in cons:
                cons[name].update(fn(int(m.group(2))))
    return cons


# tiers give broad coverage: edges, small, medium (both signs where allowed)
_TIERS = [0, 1, 2, -1, 3, 5, 8, -2, 10, 17, 4, -3, 25, 6, 40, 7, -5, 13, 50, 9]


def sample_inputs(params: List[str], cons: Dict[str, Dict[str, int]], n_runs: int, seed: int = 0) -> List[Dict[str, int]]:
    """Deterministic broad sweep of input tuples honoring constraints."""
    runs: List[Dict[str, int]] = []
    for r in range(n_runs):
        vals: Dict[str, int] = {}
        for j, p in enumerate(params):
            lo = cons.get(p, {}).get("min", _DEFAULT_MIN)
            hi = cons.get(p, {}).get("max", _DEFAULT_MAX)
            cand = _TIERS[(r + j * 7 + seed) % len(_TIERS)]
            if cand < lo:
                cand = lo + (cand % max(1, hi - lo + 1)) if hi > lo else lo
            if cand > hi:
                cand = hi
            vals[p] = int(cand)
        runs.append(vals)
    return runs


# ── instrumentation ─────────────────────────────────────────────────────────

def _printf_stmt(loop_idx: int, tag: str, pre_vars: List[str]) -> str:
    fmt = " ".join(f"{v}=%d" for v in pre_vars)
    args = ", ".join(pre_vars)
    return f'printf("{_MARK}{tag}{loop_idx} {fmt}\\n", {args}); '


def instrument(source: str, prog: Program, loop_idx: int = 0) -> str:
    """Insert loop-entry printfs around loop `loop_idx` (default: first loop)."""
    loop = prog.loops[loop_idx]
    pv = prog.pre_vars
    entry = _printf_stmt(loop_idx, "E", pv)      # entry (before loop)
    head = _printf_stmt(loop_idx, "H", pv)       # top of body
    exit_ = _printf_stmt(loop_idx, "X", pv)      # after loop (guard false)
    counter = f"int __it{loop_idx}=0; "
    cap = f"if(++__it{loop_idx} > {_ITER_CAP}) break; "

    # insert from latest offset to earliest so indices stay valid
    out = source
    close = loop.body_close
    out = out[:close + 1] + "\n" + exit_ + out[close + 1:]
    open_ = loop.body_open
    out = out[:open_ + 1] + "\n" + cap + head + out[open_ + 1:]
    kw = loop.kw_start
    out = out[:kw] + entry + counter + out[kw:]
    return out


def _build_program(instr_func: str, prog: Program, inputs: Dict[str, int]) -> str:
    prelude = '#include <stdio.h>\n#include <stdlib.h>\n'
    if re.search(r"\bunknown\s*\(", instr_func) and "int unknown" not in instr_func:
        prelude += "int unknown(){ return rand()%2; }\n"
    decls = "\n".join(f"    int {p} = {inputs.get(p, 0)};" for p in prog.params)
    call = f"    {prog.func_name}({', '.join(prog.params)});"
    main = f"\nint main(){{\n    srand(12345);\n{decls}\n{call}\n    return 0;\n}}\n"
    return prelude + instr_func + main


_LINE_RE = re.compile(rf"{re.escape(_MARK)}([EHX])(\d+)\s+(.*)")


def _parse_output(stdout: str, loop_idx: int, pre_vars: List[str], pre: Dict[str, int]) -> List[State]:
    states: List[State] = []
    for line in stdout.splitlines():
        m = _LINE_RE.search(line)
        if not m or int(m.group(2)) != loop_idx:
            continue
        vals: Dict[str, int] = {}
        for kv in m.group(3).split():
            if "=" in kv:
                k, v = kv.split("=", 1)
                try:
                    vals[k] = int(v)
                except ValueError:
                    pass
        if len(vals) == len(pre_vars):
            states.append(State(vars=vals, pre=dict(pre)))
    return states


def run_and_collect(
    source: str,
    prog: Program,
    inputs: Dict[str, int],
    loop_idx: int = 0,
    timeout: float = 5.0,
) -> List[State]:
    """Instrument `source`, run once with `inputs`, return loop-entry valuations."""
    instr = instrument(source, prog, loop_idx)
    full = _build_program(instr, prog, inputs)
    return _compile_run_parse(full, prog, inputs, loop_idx, timeout)


def _compile_run_parse(full: str, prog: Program, inputs, loop_idx, timeout) -> List[State]:
    tmpdir = tempfile.mkdtemp(prefix="rlsampler_")
    csrc = os.path.join(tmpdir, "prog.c")
    cbin = os.path.join(tmpdir, "prog.out")
    try:
        with open(csrc, "w") as f:
            f.write(full)
        try:
            subprocess.run(["gcc", csrc, "-o", cbin], check=True,
                           capture_output=True, text=True, timeout=10)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return []
        try:
            res = subprocess.run([cbin], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return []
        return _parse_output(res.stdout, loop_idx, prog.pre_vars, inputs)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def collect_reachable(
    prog: Program,
    loop_idx: int = 0,
    n_runs: int = 24,
    source_override: Optional[str] = None,
    seed: int = 0,
) -> List[State]:
    """Run the (possibly overridden) program over many inputs; gather loop-entry states."""
    src = source_override if source_override is not None else prog.source
    cons = param_constraints(prog.requires, prog.params)
    all_states: List[State] = []
    for inputs in sample_inputs(prog.params, cons, n_runs, seed=seed):
        all_states.extend(run_and_collect(src, prog, inputs, loop_idx))
    return all_states
