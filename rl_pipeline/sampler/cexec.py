"""
Self-contained C instrumentation + execution for collecting loop-ENTRY
valuations (the sampler's definition of a "sample").

No dependency on src/ — the sampler component is standalone.  We:
  1. instrument the target function to print the loop-entry variable valuation
     on entry, at the top of every iteration, and once on exit;
  2. generate a main() that calls the function with sampled inputs (respecting
     the FULL `requires`, including param-vs-param constraints), sweeping a
     broad range of magnitudes/signs/edge values;
  3. compile with gcc and run, capturing the printed valuations.

Truthfulness guarantees (the reward depends on them):
  * loops run to their REAL exit — the iteration cap is a huge safety net for
    divergent loops only.  Printing is throttled (dense prefix + periodic
    bursts + exit), so long loops stay cheap while every printed state carries
    its (run, iteration) coordinates for density checks downstream;
  * a run that hits the cap is flagged: its over-run states are DISCARDED
    (they would be reachable continuations, not negatives) and the flag is
    surfaced so the sampler can disable range-based negatives;
  * over-run states (tag O) are only meaningful when the guard genuinely went
    false — they continue the loop's real dynamics past the exit, preserving
    every relation while leaving the reachable range.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple

from ..common.program import Program
from ..common.state import State, eval_predicate

_ITER_CAP = 2_000_000    # safety net for divergent loops (wall-clock is the real guard)
_OVERRUN_STEPS = 24      # body executions past the exit (out-of-bounds negatives)
_PRINT_DENSE = 512       # print every state for the first N iterations
_PRINT_STRIDE = 251      # afterwards print bursts every STRIDE iterations…
_PRINT_BURST = 8         # …of BURST consecutive states (keeps windows dense)
_PRINT_MAX = 20_000      # hard per-run print budget
_MARK = "__LH__"
_DEFAULT_MIN = -64
_DEFAULT_MAX = 64


def gcc_available() -> bool:
    return shutil.which("gcc") is not None


# ── input domain ────────────────────────────────────────────────────────────

def param_constraints(requires: str, params: List[str]) -> Dict[str, Dict[str, int]]:
    """Very small requires -> per-param {min,max} parser (EXPLICIT literal bounds
    only; the tier clamp falls back to the +/-64 defaults where nothing is
    stated, while far probes may roam wider)."""
    cons: Dict[str, Dict[str, int]] = {p: {} for p in params}
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

# Far probes: a few large-magnitude input tuples whose values are HASHED FROM
# THE SEED, so every seed's input envelope is different.  The small tiers above
# are seed-independent (the seed only rotates their phase), which lets a
# sample-extreme box (`lo <= v <= hi` at observed extremes) stay consistent
# across ALL seeds — the holdout seed could never punish it.  With far probes,
# a box fitted to the canonical seeds' extremes is violated by the holdout's
# positives (different probe values) and gets filtered as unsound, while a true
# symbolic bound (x <= n) is indifferent.  Magnitude is capped cube-safe
# (512^3 < 2^31) so nonlinear gold invariants stay overflow-free.
_FAR_MAX = 512
_FAR_COUNT = 3
_FAR_BAND = 149          # probe k roams band [65 + k*149, 65 + (k+1)*149)


def _far_probe(params: List[str], cons: Dict[str, Dict[str, int]],
               seed: int, k: int) -> Dict[str, int]:
    vals: Dict[str, int] = {}
    for j, p in enumerate(params):
        h = (seed * 1000003 + k * 8191 + j * 131) % _FAR_BAND
        mag = min(65 + k * _FAR_BAND + h, _FAR_MAX)
        if (seed + k + j) % 2:
            mag = -mag
        lo = cons.get(p, {}).get("min")
        hi = cons.get(p, {}).get("max")
        if lo is not None and mag < lo:
            mag = lo
        if hi is not None and mag > hi:
            mag = hi
        vals[p] = int(mag)
    return vals


def _clamp_tier(cand: int, cons: Dict[str, Dict[str, int]], p: str) -> int:
    lo = cons.get(p, {}).get("min", _DEFAULT_MIN)
    hi = cons.get(p, {}).get("max", _DEFAULT_MAX)
    if cand < lo:
        cand = lo + (cand % max(1, hi - lo + 1)) if hi > lo else lo
    if cand > hi:
        cand = hi
    return int(cand)


def _jitter_tier(t: int, seed: int, r: int) -> int:
    """Seed-hashed +/-2 jitter on NON-EDGE tiers: decorrelates the sampled
    values across seeds so pointwise value memorization (`v != k` farms) fitted
    on the canonical seeds misses the holdout's clusters.  Edge tiers
    (0, +/-1, 2, 3) stay exact — boundary behavior must always be sampled.
    The jitter is the same for every param of a run, so all-equal tuples
    (needed by `z == k`-style requires) stay all-equal."""
    if abs(t) < 4:
        return t
    return t + (seed * 131 + r * 17) % 5 - 2


def _tier_tuple(params: List[str], cons: Dict[str, Dict[str, int]], r: int, seed: int) -> Dict[str, int]:
    """Phase-1 stripe: all params move together — broad, diverse tuples."""
    return {p: _clamp_tier(_jitter_tier(_TIERS[(r + j * 7 + seed) % len(_TIERS)], seed, r), cons, p)
            for j, p in enumerate(params)}


def _grid_tuple(params: List[str], cons: Dict[str, Dict[str, int]], r: int, seed: int) -> Dict[str, int]:
    """Phase-2 mixed-radix grid: systematically enumerates tier COMBINATIONS.
    Unlike the stripe (whose params never coincide — the tiers are distinct), the
    grid reaches e.g. equal-value tuples, so param-vs-param requires like
    `z == k` are satisfiable (r=0 yields all-equal)."""
    n = len(_TIERS)
    vals: Dict[str, int] = {}
    for j, p in enumerate(params):
        digit = (r // (n ** j) + seed) % n
        vals[p] = _clamp_tier(_jitter_tier(_TIERS[digit], seed, r), cons, p)
    return vals


def sample_inputs(params: List[str], cons: Dict[str, Dict[str, int]], n_runs: int,
                  seed: int = 0, requires: str = "", single_ok: bool = True) -> List[Dict[str, int]]:
    """Deterministic broad sweep of input tuples honoring the FULL requires.

    Literal per-param bounds shape the tiers; the complete `requires` (including
    param-vs-param constraints like `a >= n`) is then CHECKED by evaluation and
    violating tuples are skipped — inputs outside the precondition would produce
    "reachable" states no true invariant has to cover, poisoning the filter.
    """
    runs: List[Dict[str, int]] = []
    seen: set = set()

    def admit(vals: Dict[str, int]) -> bool:
        key = tuple(sorted(vals.items()))
        if params and key in seen:
            return False
        if requires:
            ok = eval_predicate(requires, State(vars=dict(vals), pre=dict(vals)))
            if ok is False:
                return False
        seen.add(key)
        runs.append(vals)
        return True

    # phase 0 — seed-hashed far probes (guaranteed slots): every seed's input
    # envelope differs, so sample-extreme boxes cannot generalize across seeds
    if params:
        for k in range(_FAR_COUNT):
            if len(runs) >= max(n_runs, _FAR_COUNT):
                break
            admit(_far_probe(params, cons, seed, k))
    # phase 1 — diverse stripe tuples (all params move together)
    for r in range(max(n_runs * 4, 80)):
        if len(runs) >= n_runs:
            break
        if admit(_tier_tuple(params, cons, r, seed)) and not params and single_ok:
            break               # no inputs to vary, deterministic — one run is exhaustive
    # phase 2 — mixed-radix grid: reaches tier COMBINATIONS the stripe cannot
    # (e.g. equal values), so `requires z == k`-style constraints are satisfied
    # instead of falling through to unchecked inputs.
    r = 0
    limit = max(n_runs * 400, 4000)
    while len(runs) < n_runs and r < limit:
        admit(_grid_tuple(params, cons, r, seed))
        r += 1
    if not runs:            # unparseable/unsatisfiable requires -> best effort
        runs = [_tier_tuple(params, cons, r, seed) for r in range(n_runs)]
    return runs


# ── instrumentation ─────────────────────────────────────────────────────────

def _printf_stmt(loop_idx: int, tag: str, pre_vars: List[str], it_expr: str = "0") -> str:
    fmt = " ".join(f"{v}=%d" for v in pre_vars)
    args = ", ".join(pre_vars)
    return f'printf("{_MARK}{tag}{loop_idx} #%d {fmt}\\n", {it_expr}, {args}); '


def instrument(source: str, prog: Program, loop_idx: int = 0) -> str:
    """Insert loop-entry printfs around loop `loop_idx` (default: first loop).

    Every printed state carries `#<iteration>` so downstream code knows which
    states have their local trace window sampled.  Printing is throttled for
    long loops (dense prefix + bursts) but the loop itself always runs to its
    genuine exit (up to a huge divergence cap, which is flagged when hit).

    Also emits OVER-RUN states (tag O): after the loop exits, the body is
    executed `_OVERRUN_STEPS` more times, printing the loop-head valuation each
    time.  These continue the loop's REAL dynamics past the exit, so they
    preserve every relation (linear AND nonlinear, e.g. z==x*y) while going OUT
    of the reachable range — exactly the hard "law holds but bound violated"
    negatives."""
    loop = prog.loops[loop_idx]
    pv = prog.pre_vars
    li = loop_idx
    entry = _printf_stmt(li, "E", pv, "0")                     # entry (before loop)
    head = _printf_stmt(li, "H", pv, f"__it{li}")              # top of body
    exit_ = _printf_stmt(li, "X", pv, f"__it{li} + 1")         # after loop (guard false)
    over_pf = _printf_stmt(li, "O", pv, "-1")                  # over-run (past the guard)
    counters = f"int __it{li}=0; int __pr{li}=0; "
    gate = (
        f'if(++__it{li} > {_ITER_CAP}) {{ printf("{_MARK}C{li}\\n"); break; }} '
        f"if((__it{li} <= {_PRINT_DENSE} || __it{li} % {_PRINT_STRIDE} < {_PRINT_BURST})"
        f" && __pr{li} < {_PRINT_MAX}) {{ __pr{li}++; {head} }} "
    )

    open_, close = loop.body_open, loop.body_close
    body_text = source[open_ + 1:close]          # original body (no injected printfs)
    if re.search(r"\b(return|goto)\b", body_text):
        overrun = ""                             # body escapes the function -> unsafe
    else:
        ov = f"__ov{li}"
        overrun = (f"\n{{ int {ov}; for({ov}=0; {ov}<{_OVERRUN_STEPS}; {ov}++)"
                   f"{{ {body_text} {over_pf} }} }}\n")

    # insert from latest offset to earliest so indices stay valid
    out = source
    out = out[:close + 1] + "\n" + exit_ + overrun + out[close + 1:]
    out = out[:open_ + 1] + "\n" + gate + out[open_ + 1:]
    kw = loop.kw_start
    out = out[:kw] + counters + entry + out[kw:]
    return out


def _build_program(instr_func: str, prog: Program, inputs: Dict[str, int], run_seed: int = 12345) -> str:
    prelude = '#include <stdio.h>\n#include <stdlib.h>\n'
    # Define any unknown/unknownN oracle that is CALLED but not DEFINED — a bare
    # `int unknown();` DECLARATION is not a definition (the old check treated it as
    # one, causing a link error -> zero states).  Body is nondeterministic.
    # Body returns a value in [-10,10]: as a `while(unknown())` GUARD it is nonzero
    # ~95% of the time, so the loop runs long enough to sample the reachable
    # trajectory (bounded by _ITER_CAP); as an assigned VALUE it gives real spread.
    for name in sorted(set(re.findall(r"\b(unknown\w*)\s*\(", instr_func))):
        if not re.search(rf"\b{name}\s*\([^;{{)]*\)\s*\{{", instr_func):
            prelude += f"int {name}(){{ return rand()%21 - 10; }}\n"
    fname = prog.func_name
    if fname == "main":   # program's own function is main() -> rename to avoid clashing with the harness
        instr_func = re.sub(r"\bmain\s*\(", "__prog_main(", instr_func, count=1)
        fname = "__prog_main"
    decls = "\n".join(f"    int {p} = {inputs.get(p, 0)};" for p in prog.params)
    call = f"    {fname}({', '.join(prog.params)});"
    # per-run srand so NONDETERMINISTIC (unknown-driven) programs explore different
    # traces across runs; unbuffered stdout so states before an over-run crash survive
    main = f"\nint main(){{\n    setbuf(stdout, NULL);\n    srand({run_seed});\n{decls}\n{call}\n    return 0;\n}}\n"
    return prelude + instr_func + main


_LINE_RE = re.compile(rf"{re.escape(_MARK)}([EHXO])(\d+)\s+#(-?\d+)\s+(.*)")
_CAP_RE = re.compile(rf"{re.escape(_MARK)}C(\d+)")


def _parse_output(stdout: str, loop_idx: int, pre_vars: List[str], pre: Dict[str, int],
                  run_id: int = -1):
    """Return ([(kind, State)], capped) where kind is 'R' (reachable: E/H/X) or
    'O' (over-run).  States carry (run, iteration) trace coordinates."""
    out = []
    capped = False
    for line in stdout.splitlines():
        c = _CAP_RE.search(line)
        if c and int(c.group(1)) == loop_idx:
            capped = True
            continue
        m = _LINE_RE.search(line)
        if not m or int(m.group(2)) != loop_idx:
            continue
        it = int(m.group(3))
        vals: Dict[str, int] = {}
        for kv in m.group(4).split():
            if "=" in kv:
                k, v = kv.split("=", 1)
                try:
                    vals[k] = int(v)
                except ValueError:
                    pass
        if len(vals) == len(pre_vars):
            kind = "O" if m.group(1) == "O" else "R"
            out.append((kind, State(vars=vals, pre=dict(pre), run=run_id, it=it)))
    return out, capped


def run_and_collect(
    source: str,
    prog: Program,
    inputs: Dict[str, int],
    loop_idx: int = 0,
    timeout: float = 5.0,
    run_seed: int = 12345,
    run_id: int = -1,
):
    """Instrument `source`, run once with `inputs`; return ([(kind, State)], capped)."""
    instr = instrument(source, prog, loop_idx)
    full = _build_program(instr, prog, inputs, run_seed=run_seed)
    return _compile_run_parse(full, prog, inputs, loop_idx, timeout, run_id)


def _compile_run_parse(full: str, prog: Program, inputs, loop_idx, timeout, run_id=-1):
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
            return [], False
        try:
            res = subprocess.run([cbin], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return [], True     # treat a wall-clock kill like a capped (incomplete) run
        return _parse_output(res.stdout, loop_idx, prog.pre_vars, inputs, run_id)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def collect_traces(
    prog: Program,
    loop_idx: int = 0,
    n_runs: int = 24,
    source_override: Optional[str] = None,
    seed: int = 0,
) -> Tuple[List[State], List[State], bool]:
    """Run the program over many inputs; return (reachable, overrun, capped_any).

    reachable = real trace states; overrun = states from running the body past a
    GENUINE exit.  Runs that hit the divergence cap (or wall-clock) contribute
    positives but their over-run states are discarded — past-the-cap states are
    reachable continuations, not negatives — and capped_any is set so callers
    can disable range-based reasoning."""
    src = source_override if source_override is not None else prog.source
    cons = param_constraints(prog.requires, prog.params)
    # nondeterministic programs need many runs even with no/identical inputs:
    # each run gets a distinct srand, exploring different unknown() traces
    deterministic = not re.search(r"\bunknown\w*\s*\(", src)
    inputs_list = sample_inputs(prog.params, cons, n_runs, seed=seed,
                                requires=prog.requires, single_ok=deterministic)
    reachable: List[State] = []
    overrun: List[State] = []
    capped_any = False
    for i, inputs in enumerate(inputs_list):
        # distinct per-run seed so nondeterministic (unknown) loops vary trace length
        states, capped = run_and_collect(src, prog, inputs, loop_idx,
                                         run_seed=1000 + seed * 97 + i * 7 + 1, run_id=i)
        capped_any = capped_any or capped
        for kind, s in states:
            if kind == "O":
                if not capped:
                    overrun.append(s)
            else:
                reachable.append(s)
    return reachable, overrun, capped_any


def collect_reachable(
    prog: Program,
    loop_idx: int = 0,
    n_runs: int = 24,
    source_override: Optional[str] = None,
    seed: int = 0,
) -> List[State]:
    """Reachable loop-head states only (positives)."""
    return collect_traces(prog, loop_idx, n_runs, source_override, seed)[0]
