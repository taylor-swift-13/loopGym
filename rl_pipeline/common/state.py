"""
State = a variable valuation at the loop entry (loop head).

  State.vars : Dict[str,int]   current values of loop-entry variables
  State.pre  : Dict[str,int]   pre/initial values (for \\at(v,Pre) / v@pre)

Plus a safe evaluator for ACSL-ish boolean predicates (invariants, guards,
postconditions) at a given state.  We convert the ACSL expression to a Python
expression and eval it in a locked-down namespace.  Integer semantics: C-style
`/` and `%` (truncation toward zero) — Python's floor semantics differ on
negatives (-7/2 is -3 in C but -4 under floor), and the sampled states ARE
C-executed values, so evaluating with floor semantics would wrongly filter
honest division/modulo invariants.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_CLAMP = (1 << 31) - 1


@dataclass(frozen=True)
class State:
    vars: Dict[str, int]
    pre: Dict[str, int] = field(default_factory=dict)
    # trace coordinates (run index, loop-head iteration) — metadata only, NOT part
    # of identity: used by the sampler to tell which states have their local trace
    # window sampled (perturbation-base density check).  -1 = synthetic/unknown.
    run: int = -1
    it: int = -1

    def key(self) -> tuple:
        return self.vars_key() + (("__pre__",),) + tuple(sorted(self.pre.items()))

    def vars_key(self) -> tuple:
        """Reachability/identity key over the loop-entry valuation (ignores pre)."""
        return tuple(sorted(self.vars.items()))

    def __hash__(self):
        return hash(self.key())

    def render(self) -> str:
        return " && ".join(f"{k} == {v}" for k, v in sorted(self.vars.items()))


_INV_RE = re.compile(r"loop\s+invariant\s+([^;]+);")


def normalize_invariant(inv: str) -> str:
    """Strip `loop invariant` prefix / trailing `;` and collapse whitespace."""
    s = inv.strip()
    s = re.sub(r"^loop\s+invariant\s+", "", s)
    if s.endswith(";"):
        s = s[:-1]
    return re.sub(r"\s+", " ", s).strip()


def extract_invariants(text: str):
    """Pull `loop invariant <expr>;` texts (whitespace-normalized) out of annotated
    code or raw LLM output.  Canonical parser shared by reward/inference."""
    if not text:
        return []
    return [re.sub(r"\s+", " ", m.group(1)).strip() for m in _INV_RE.finditer(text)]


def dedup_normalized(invariants):
    """Normalize each invariant and dedup, preserving first-seen order; drop empties."""
    out, seen = [], set()
    for inv in invariants:
        c = normalize_invariant(inv)
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _split_top_level(expr: str, sep: str) -> List[str]:
    parts, buf, depth = [], "", 0
    i, n, m = 0, len(expr), len(sep)
    while i < n:
        c = expr[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if depth == 0 and expr[i:i + m] == sep:
            parts.append(buf)
            buf = ""
            i += m
            continue
        buf += c
        i += 1
    parts.append(buf)
    return parts


def _acsl_to_py(expr: str) -> str:
    """Convert an ACSL boolean expression to a Python expression string."""
    s = expr
    # \at(v, Pre) and v@pre -> safe identifier
    s = re.sub(r"\\at\(\s*(\w+)\s*,\s*Pre\s*\)", r"\1__PRE__", s)
    s = re.sub(r"\b(\w+)@pre\b", r"\1__PRE__", s)
    # implication (right associative): fold on top-level ==>
    if "==>" in s:
        parts = _split_top_level(s, "==>")
        if len(parts) >= 2:
            acc = _acsl_to_py(parts[-1])
            for left in reversed(parts[:-1]):
                acc = f"((not ({_acsl_to_py(left)})) or ({acc}))"
            return acc
    # equivalence
    if "<==>" in s:
        parts = _split_top_level(s, "<==>")
        if len(parts) == 2:
            return f"(bool({_acsl_to_py(parts[0])}) == bool({_acsl_to_py(parts[1])}))"
    s = s.replace("&&", " and ").replace("||", " or ")
    s = re.sub(r"!(?!=)", " not ", s)          # logical not, but keep !=
    s = re.sub(r"(?<![<>=!])=(?![=])", "==", s)  # lone '=' -> '==' (defensive)
    # C integer division / modulo -> python floor ops
    s = re.sub(r"(?<![/])/(?![/])", "//", s)
    return s


# C integer division/modulo: truncation toward zero (Python's // and % floor).
def _c_div(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def _c_mod(a, b):
    return a - _c_div(a, b) * b


class _CDivTransformer(ast.NodeTransformer):
    """Rewrite every Div/FloorDiv/Mod into __cdiv__/__cmod__ calls so the
    evaluator matches the C semantics the sampled states were produced under."""

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, (ast.Div, ast.FloorDiv)):
            fn = "__cdiv__"
        elif isinstance(node.op, ast.Mod):
            fn = "__cmod__"
        else:
            return node
        return ast.copy_location(
            ast.Call(func=ast.Name(id=fn, ctx=ast.Load()),
                     args=[node.left, node.right], keywords=[]),
            node,
        )


# Cache compiled expressions across calls (predicates evaluated on many states).
_COMPILE_CACHE: Dict[str, object] = {}
_SAFE_GLOBALS = {"__builtins__": {}}


def _compile(expr: str):
    # strip: `!` -> ` not ` substitution can leave leading whitespace, which
    # ast.parse(mode="eval") rejects as an IndentationError — silently turning
    # every `!(...)`-shaped invariant into dead weight (never evaluated)
    py = _acsl_to_py(expr).strip()
    code = _COMPILE_CACHE.get(py)
    if code is None:
        tree = _CDivTransformer().visit(ast.parse(py, mode="eval"))
        ast.fix_missing_locations(tree)
        code = compile(tree, "<acsl>", "eval")
        _COMPILE_CACHE[py] = code
    return code


def eval_predicate(expr: str, state: "State") -> Optional[bool]:
    """
    Evaluate an ACSL boolean predicate at `state`.

    Returns True / False, or None if it cannot be grounded/evaluated
    (unknown identifiers left over, or an evaluation error).
    """
    if expr is None:
        return None
    expr = expr.strip()
    if not expr:
        return None
    try:
        code = _compile(expr)
    except SyntaxError:
        return None
    ns: Dict[str, int] = {}
    for k, v in state.vars.items():
        ns[k] = int(v)
    for k, v in state.pre.items():
        ns[f"{k}__PRE__"] = int(v)
    # any var not bound but referenced -> unknown
    try:
        names = code.co_names
    except AttributeError:
        names = ()
    allowed = set(ns.keys()) | {"True", "False", "None", "bool", "abs",
                                "__cdiv__", "__cmod__"}
    for nm in names:
        if nm not in allowed:
            return None
    ns["abs"] = abs
    ns["bool"] = bool
    ns["__cdiv__"] = _c_div
    ns["__cmod__"] = _c_mod
    try:
        result = eval(code, _SAFE_GLOBALS, ns)  # noqa: S307 - locked-down namespace
    except Exception:
        return None
    if isinstance(result, bool):
        return result
    try:
        return bool(result)
    except Exception:
        return None
