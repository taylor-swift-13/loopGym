"""
Self-contained C instrumentation + execution for collecting loop-ENTRY
valuations (the sampler's definition of a "sample").

No dependency on src/ — the sampler component is standalone.  We:
  1. instrument the target function to print the loop-entry valuation on entry,
     through a dense prefix and periodic bursts, and once on exit;
  2. generate a main() that calls the function with sampled inputs (respecting
     the FULL `requires`, including param-vs-param constraints), sweeping a
     broad range of magnitudes/signs/edge values;
  3. compile with gcc and run, capturing the printed valuations.

Trace-collection safeguards (the reward depends on them):
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


# ── input domain ────────────────────────────────────────────────────────────

def _strip_outer_parens(expr: str) -> str:
    expr = expr.strip()
    while len(expr) >= 2 and expr[0] == "(" and expr[-1] == ")":
        depth = 0
        for index, char in enumerate(expr):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(expr) - 1:
                    return expr
        if depth != 0:
            return expr
        expr = expr[1:-1].strip()
    return expr


def _requirement_conjuncts(expr: str) -> List[str]:
    """Split only top-level conjunctions, preserving negated subexpressions."""
    expr = _strip_outer_parens(expr)
    parts: List[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(expr):
        if expr[index] == "(":
            depth += 1
        elif expr[index] == ")":
            depth -= 1
        elif depth == 0 and expr[index:index + 2] == "&&":
            parts.extend(_requirement_conjuncts(expr[start:index]))
            start = index + 2
            index += 1
        index += 1
    if parts:
        parts.extend(_requirement_conjuncts(expr[start:]))
        return parts
    return [expr]


def param_constraints(requires: str, params: List[str]) -> Dict[str, Dict[str, int]]:
    """Extract direct, non-negated literal bounds for each parameter.

    The bounds only shape candidate generation; the complete requirement is
    still evaluated before a tuple is admitted.  Matching whole conjunctions
    matters here: scanning arbitrary substrings would read ``!(n < 0)`` as
    ``n < 0`` and generate exclusively out-of-contract inputs.
    """
    cons: Dict[str, Dict[str, int]] = {p: {} for p in params}
    if not requires:
        return cons

    inverse = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "=="}

    def add_bound(name: str, operator: str, value: int) -> None:
        if name not in cons:
            return
        if operator == "==":
            lower = upper = value
        elif operator == ">=":
            lower, upper = value, None
        elif operator == ">":
            lower, upper = value + 1, None
        elif operator == "<=":
            lower, upper = None, value
        else:
            lower, upper = None, value - 1
        if lower is not None:
            cons[name]["min"] = max(lower, cons[name].get("min", lower))
        if upper is not None:
            cons[name]["max"] = min(upper, cons[name].get("max", upper))

    for raw_clause in _requirement_conjuncts(requires):
        clause = _strip_outer_parens(raw_clause)
        if clause.startswith("!"):
            continue
        direct = re.fullmatch(r"([A-Za-z_]\w*)\s*(==|>=|>|<=|<)\s*(-?\d+)", clause)
        if direct:
            add_bound(direct.group(1), direct.group(2), int(direct.group(3)))
            continue
        reversed_ = re.fullmatch(r"(-?\d+)\s*(==|>=|>|<=|<)\s*([A-Za-z_]\w*)", clause)
        if reversed_:
            add_bound(
                reversed_.group(3),
                inverse[reversed_.group(2)],
                int(reversed_.group(1)),
            )
    return cons


def _integer_source_constants(source: str) -> Dict[str, int]:
    """Return integer object-like macros and initialized file-scope globals."""
    constants: Dict[str, int] = {}
    literal = r"[+-]?(?:0[xX][0-9A-Fa-f]+|\d+)[uUlL]*"

    for match in re.finditer(
        rf"(?m)^\s*#\s*define\s+([A-Za-z_]\w*)\s+\(?\s*({literal})\s*\)?\s*$",
        source,
    ):
        raw = re.sub(r"[uUlL]+$", "", match.group(2))
        constants[match.group(1)] = int(raw, 0)

    # Blank comments and function bodies so local initializers cannot be
    # mistaken for the caller-visible value of a global.
    clean = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), source, flags=re.DOTALL)
    clean = re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), clean)
    top = list(clean)
    depth = 0
    for index, char in enumerate(clean):
        if char == "{":
            depth += 1
            top[index] = " "
        elif char == "}":
            top[index] = " "
            depth = max(0, depth - 1)
        elif depth and char != "\n":
            top[index] = " "
    top_level = "".join(top)
    declaration = re.compile(
        rf"(?m)^\s*(?:(?:static|extern|const|volatile|unsigned|signed)\s+)*"
        rf"(?:int|long|short)\s+([A-Za-z_]\w*)\s*=\s*({literal})\s*;"
    )
    for match in declaration.finditer(top_level):
        raw = re.sub(r"[uUlL]+$", "", match.group(2))
        constants[match.group(1)] = int(raw, 0)
    return constants


def _bind_integer_constants(expr: str, constants: Dict[str, int]) -> str:
    for name in sorted(constants, key=len, reverse=True):
        expr = re.sub(rf"\b{re.escape(name)}\b", str(constants[name]), expr)
    return expr


def _eval_requirement(requires: str, values: Dict[str, int]) -> Optional[bool]:
    """Evaluate a requirement after aliasing C identifiers to Python-safe names."""
    expression = requires
    aliases: Dict[str, int] = {}
    for index, name in enumerate(sorted(values, key=len, reverse=True)):
        alias = f"__req_value_{index}"
        expression = re.sub(rf"\b{re.escape(name)}\b", alias, expression)
        aliases[alias] = values[name]
    return eval_predicate(expression, State(vars=aliases, pre=aliases))


# tiers give broad coverage: edges, small, medium (both signs where allowed)
_TIERS = [0, 1, 2, -1, 3, 5, 8, -2, 10, 17, 4, -3, 25, 6, 40, 7, -5, 13, 50, 9]

# Far probes: a few large-magnitude input tuples (COVERAGE: they widen the
# input envelope far beyond the small tiers, witnessing deep loop states and
# input-relative ranges the near tiers never reach).  Magnitude is capped
# cube-safe (512^3 < 2^31) so nonlinear gold invariants stay overflow-free.
_FAR_MAX = 512
_FAR_COUNT = 3
_FAR_BAND = 149          # probe k roams band [65 + k*149, 65 + (k+1)*149)


def _far_probe(params: List[str], cons: Dict[str, Dict[str, int]],
               seed: int, k: int) -> Dict[str, int]:
    """Probe k < _FAR_COUNT: independent signed magnitudes per param.
    Probe k >= _FAR_COUNT: ORDERED all-positive tuples (descending for even k,
    ascending for odd), so multi-param programs whose deep states need
    `0 < p_i < p_j` at scale (e.g. a remainder counting up to a large divisor)
    get their real range witnessed — sign-independent probes almost never
    produce ordered positive pairs, leaving envelope holes that sample-extreme
    boxes memorize."""
    vals: Dict[str, int] = {}
    ordered = k >= _FAR_COUNT
    for j, p in enumerate(params):
        h = (seed * 1000003 + k * 8191 + j * 131) % _FAR_BAND
        if ordered:
            rank = j if k % 2 else (len(params) - 1 - j)
            mag = max(65, _FAR_MAX - rank * (_FAR_MAX // max(2, len(params))) - h)
        else:
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


def _tier_tuple(params: List[str], cons: Dict[str, Dict[str, int]], r: int, seed: int) -> Dict[str, int]:
    """Phase-1 stripe: all params move together — broad, diverse tuples."""
    return {p: _clamp_tier(_TIERS[(r + j * 7 + seed) % len(_TIERS)], cons, p)
            for j, p in enumerate(params)}


def _grid_tuple(
    params: List[str],
    cons: Dict[str, Dict[str, int]],
    r: int,
    seed: int,
    rotation: int = 0,
) -> Dict[str, int]:
    """Enumerate tier combinations with a rotating least-significant input.

    A fixed mixed-radix order needs ``len(_TIERS) ** j`` candidates before
    parameter ``j`` changes.  Rotating the digit positions prevents a bounded
    search from leaving the last inputs fixed in four-or-more parameter code.
    """
    n = len(_TIERS)
    vals: Dict[str, int] = {}
    for j, p in enumerate(params):
        exponent = (j - rotation) % max(1, len(params))
        digit = (r // (n ** exponent) + seed) % n
        vals[p] = _clamp_tier(_TIERS[digit], cons, p)
    return vals


def _requirement_tuples(params: List[str], cons: Dict[str, Dict[str, int]],
                        requires: str, seed: int):
    """Target large constants and simple parameter relations in `requires`.

    The regular tier grid is intentionally small.  Clauses such as
    `a == b + 10000` still need in-contract inputs, so combine every literal
    with small offsets on each ordered parameter pair before giving up.
    """
    literals = sorted({int(v) for v in re.findall(r"(?<![A-Za-z_])-?\d+", requires)})
    offsets = _TIERS[:12]

    def bounded(value: int, param: str) -> int:
        lo = cons.get(param, {}).get("min")
        hi = cons.get(param, {}).get("max")
        if lo is not None:
            value = max(value, lo)
        if hi is not None:
            value = min(value, hi)
        return int(value)

    for literal in literals:
        for offset_idx, offset in enumerate(offsets):
            base = {
                p: _clamp_tier(
                    _TIERS[(seed + offset_idx + index) % len(_TIERS)], cons, p
                )
                for index, p in enumerate(params)
            }
            for param in params:
                vals = dict(base)
                vals[param] = bounded(literal + offset, param)
                yield vals
            for left in params:
                for right in params:
                    if left == right:
                        continue
                    vals = dict(base)
                    vals[right] = bounded(offset, right)
                    vals[left] = bounded(literal + offset, left)
                    yield vals


def sample_inputs(params: List[str], cons: Dict[str, Dict[str, int]], n_runs: int,
                  seed: int = 0, requires: str = "", single_ok: bool = True) -> List[Dict[str, int]]:
    """Deterministic broad sweep of input tuples honoring the FULL requires.

    Literal per-param bounds shape the tiers; the complete `requires` (including
    param-vs-param constraints like `a >= n`) is then CHECKED by evaluation and
    violating tuples are skipped — inputs outside the precondition would produce
    "reachable" states no true invariant has to cover, poisoning the filter.
    """
    if n_runs < 1:
        raise ValueError("n_runs must be at least 1")

    runs: List[Dict[str, int]] = []
    seen: set = set()

    def admit(vals: Dict[str, int]) -> bool:
        key = tuple(sorted(vals.items()))
        if params and key in seen:
            return False
        if requires:
            ok = _eval_requirement(requires, vals)
            if ok is not True:
                return False
        seen.add(key)
        runs.append(vals)
        return True

    # phase 0 — far probes (guaranteed slots): wide input envelope coverage.
    # Probes _FAR_COUNT.._FAR_COUNT+1 are the ORDERED all-positive tuples
    # (see _far_probe) — only emitted for multi-param programs, where ordering
    # exists at all
    if params:
        probe_count = _FAR_COUNT + (2 if len(params) > 1 else 0)
        for k in range(probe_count):
            if len(runs) >= n_runs:
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
    limit = max(n_runs * 400, 4000)
    rotations = max(1, len(params))
    for candidate in range(limit):
        if len(runs) >= n_runs:
            break
        rotation = candidate % rotations
        r = candidate // rotations
        admit(_grid_tuple(params, cons, r, seed, rotation=rotation))
    # Phase 3 targets large constants and pairwise offsets from the contract.
    if requires and len(runs) < n_runs:
        for vals in _requirement_tuples(params, cons, requires, seed):
            admit(vals)
            if len(runs) >= n_runs:
                break
    if not runs:
        detail = f" satisfying requires: {requires}" if requires else ""
        raise ValueError("could not construct any input" + detail)
    if not single_ok and len(runs) < n_runs:
        # Oracle-controlled programs need repeated executions even when the
        # precondition admits only one input tuple. Each generated main gets a
        # distinct srand seed in collect_traces().
        unique_runs = list(runs)
        runs.extend(
            dict(unique_runs[index % len(unique_runs)])
            for index in range(n_runs - len(runs))
        )
    return runs


# ── instrumentation ─────────────────────────────────────────────────────────

def _printf_stmt(loop_idx: int, tag: str, pre_vars: List[str], unsigned_vars,
                 it_expr: str = "0") -> str:
    fmt = " ".join(f"{v}={'%u' if v in unsigned_vars else '%d'}" for v in pre_vars)
    args = ", ".join(pre_vars)
    suffix = f", {args}" if args else ""
    return f'printf("{_MARK}{tag}{loop_idx} #%d {fmt}\\n", {it_expr}{suffix}); '


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
    synthetic negative candidates."""
    loop = prog.loops[loop_idx]
    pv = prog.pre_vars
    unsigned = set(prog.unsigned_vars)
    li = loop_idx
    entry = _printf_stmt(li, "E", pv, unsigned, "0")
    head = _printf_stmt(li, "H", pv, unsigned, f"__it{li}")
    exit_ = _printf_stmt(li, "X", pv, unsigned, f"__it{li} + 1")
    over_pf = _printf_stmt(li, "O", pv, unsigned, "-1")
    counters = f"int __it{li}=0; int __pr{li}=0; "
    gate = (
        f'if(++__it{li} > {_ITER_CAP}) {{ printf("{_MARK}C{li}\\n"); break; }} '
        f"if((__it{li} <= {_PRINT_DENSE} || __it{li} % {_PRINT_STRIDE} < {_PRINT_BURST})"
        f" && __pr{li} < {_PRINT_MAX}) {{ __pr{li}++; {head} }} "
    )

    open_, close = loop.body_open, loop.body_close
    body_text = source[open_ + 1:close]          # original body (no injected printfs)
    # Replaying a body containing an escape or a label is not a closed
    # transition.  In particular, copying a label makes the instrumented C
    # invalid because labels have function scope, even when the copies live in
    # different blocks.
    if (re.search(r"\b(return|goto)\b", body_text)
            or re.search(r"(?m)^\s*[A-Za-z_]\w*\s*:", body_text)):
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


def _oracle_return_type(source: str, name: str) -> str:
    """Return the declared scalar C type for an undefined oracle function."""
    scalar = (
        r"_Bool|(?:unsigned\s+|signed\s+)?"
        r"(?:char|short|int|long(?:\s+long)?)|float|double"
    )
    matches = list(re.finditer(
        rf"\b(?P<type>{scalar})\s+{re.escape(name)}\s*\([^;{{}}]*\)\s*;",
        source,
    ))
    return re.sub(r"\s+", " ", matches[-1].group("type")).strip() if matches else "int"


def _oracle_definition(source: str, name: str) -> str:
    return_type = _oracle_return_type(source, name)
    if return_type == "_Bool" or name.endswith("bool"):
        expression = f"({return_type})(rand() & 1)"
    elif name.endswith("uchar"):
        expression = f"({return_type})(rand()%256)"
    elif name.endswith("ushort"):
        expression = f"({return_type})(rand()%65536)"
    elif return_type in {"float", "double"}:
        expression = f"({return_type})(rand()%2001 - 1000) / 1000"
    elif "unsigned" in return_type:
        expression = f"({return_type})(rand()%513)"
    else:
        expression = f"({return_type})(rand()%1025 - 512)"
    return f"{return_type} {name}(void){{ return {expression}; }}\n"


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
            prelude += _oracle_definition(instr_func, name)
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
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "unknown compiler error").strip()
            raise ValueError(f"gcc failed to compile instrumented program: {detail[:500]}") from exc
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"could not compile instrumented program: {exc}") from exc
        try:
            res = subprocess.run([cbin], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            states, _ = _parse_output(stdout, loop_idx, prog.pre_vars, inputs, run_id)
            return states, True
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
    requires = _bind_integer_constants(
        prog.requires,
        _integer_source_constants(src),
    )
    cons = param_constraints(requires, prog.params)
    for param in prog.unsigned_vars:
        if param in cons:
            cons[param]["min"] = max(0, cons[param].get("min", 0))
    # nondeterministic programs need many runs even with no/identical inputs:
    # each run gets a distinct srand, exploring different unknown() traces
    deterministic = not re.search(r"\bunknown\w*\s*\(", src)
    inputs_list = sample_inputs(prog.params, cons, n_runs, seed=seed,
                                requires=requires, single_ok=deterministic)
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
    if not reachable:
        raise ValueError("sampling produced no reachable loop-head states")
    return reachable, overrun, capped_any
