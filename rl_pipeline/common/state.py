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
        current = " && ".join(f"{k} == {v}" for k, v in sorted(self.vars.items()))
        if not self.pre:
            return current
        initial = " && ".join(f"{k} == {v}" for k, v in sorted(self.pre.items()))
        return f"{current}; Pre: {initial}"


_INV_RE = re.compile(r"loop\s+invariant\s+([^;]+);")


def normalize_invariant(inv: str) -> str:
    """Strip `loop invariant` prefix / trailing `;` and collapse whitespace."""
    s = inv.strip()
    s = re.sub(r"^loop\s+invariant\s+", "", s)
    if s.endswith(";"):
        s = s[:-1]
    return re.sub(r"\s+", " ", s).strip()


def extract_invariants(text: str) -> List[str]:
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


def _has_outer_parens(expr: str) -> bool:
    if len(expr) < 2 or expr[0] != "(" or expr[-1] != ")":
        return False
    depth = 0
    for index, char in enumerate(expr):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(expr) - 1:
                return False
    return depth == 0


def _translate_logic(expr: str) -> str:
    """Recursively translate ACSL boolean operators with their precedence."""
    s = expr.strip()
    if _has_outer_parens(s):
        return f"({_translate_logic(s[1:-1])})"

    for operator, python_operator in (("<==>", None), ("==>", None),
                                      ("||", "or"), ("&&", "and")):
        parts = _split_top_level(s, operator)
        if len(parts) == 1:
            continue
        if operator == "<==>":
            translated = [_translate_logic(part) for part in parts]
            result = translated[0]
            for part in translated[1:]:
                result = f"(bool({result}) == bool({part}))"
            return result
        if operator == "==>":
            result = _translate_logic(parts[-1])
            for part in reversed(parts[:-1]):
                result = f"((not ({_translate_logic(part)})) or ({result}))"
            return result
        return f" {python_operator} ".join(
            f"({_translate_logic(part)})" for part in parts
        )

    if s.startswith("!") and not s.startswith("!="):
        return f"(not ({_translate_logic(s[1:])}))"

    # Translate boolean expressions nested inside otherwise atomic parentheses.
    out, index = [], 0
    while index < len(s):
        if s[index] != "(":
            out.append(s[index])
            index += 1
            continue
        depth, end = 1, index + 1
        while end < len(s) and depth:
            if s[end] == "(":
                depth += 1
            elif s[end] == ")":
                depth -= 1
            end += 1
        if depth:
            return s
        out.append("(" + _translate_logic(s[index + 1:end - 1]) + ")")
        index = end
    return "".join(out)


def _acsl_to_py(expr: str) -> str:
    """Convert an ACSL boolean expression to a Python expression string."""
    s = re.sub(r"\\true\b", "True", expr)
    s = re.sub(r"\\false\b", "False", s)
    s = re.sub(r"\\at\(\s*(\w+)\s*,\s*Pre\s*\)", r"\1__PRE__", s)
    s = re.sub(r"\b(\w+)@pre\b", r"\1__PRE__", s)
    s = _translate_logic(s)
    s = re.sub(r"(?<![<>=!])=(?![=])", "==", s)
    return re.sub(r"(?<![/])/(?![/])", "//", s)


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


class _VectorTransformer(ast.NodeTransformer):
    """Make Python boolean AST nodes work element-wise on NumPy arrays."""

    @staticmethod
    def _fold(name: str, values):
        result = values[0]
        for value in values[1:]:
            result = ast.Call(
                func=ast.Name(id=name, ctx=ast.Load()),
                args=[result, value],
                keywords=[],
            )
        return result

    def visit_BoolOp(self, node):
        values = [self.visit(value) for value in node.values]
        name = "__logical_and__" if isinstance(node.op, ast.And) else "__logical_or__"
        return ast.copy_location(self._fold(name, values), node)

    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(id="__logical_not__", ctx=ast.Load()),
                    args=[operand],
                    keywords=[],
                ),
                node,
            )
        node.operand = operand
        return node

    def visit_Compare(self, node):
        left = self.visit(node.left)
        comparators = [self.visit(value) for value in node.comparators]
        comparisons = []
        current = left
        for operator, right in zip(node.ops, comparators):
            comparisons.append(ast.Compare(left=current, ops=[operator], comparators=[right]))
            current = right
        result = comparisons[0]
        if len(comparisons) > 1:
            result = self._fold("__logical_and__", comparisons)
        return ast.copy_location(result, node)

    def visit_Call(self, node):
        node = self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "bool" and len(node.args) == 1:
            return ast.copy_location(node.args[0], node)
        return node


# Cache compiled expressions across calls (predicates evaluated on many states).
_COMPILE_CACHE: Dict[str, object] = {}
_VECTOR_COMPILE_CACHE: Dict[str, object] = {}
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


def _compile_vector(expr: str):
    py = _acsl_to_py(expr).strip()
    code = _VECTOR_COMPILE_CACHE.get(py)
    if code is None:
        tree = ast.parse(py, mode="eval")
        tree = _CDivTransformer().visit(tree)
        tree = _VectorTransformer().visit(tree)
        ast.fix_missing_locations(tree)
        code = compile(tree, "<acsl-vector>", "eval")
        _VECTOR_COMPILE_CACHE[py] = code
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
    except (SyntaxError, TypeError, ValueError):
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


def first_falsifying_state(expr: str, states: List[State]) -> Optional[State]:
    """Return the first sampled state falsifying ``expr``.

    NumPy evaluates the same predicate over every state column at once.  The
    scalar fallback stops on an unevaluable expression, leaving syntax and
    induction decisions to Frama-C rather than spending time rescanning a
    predicate the lite evaluator cannot ground.
    """
    if not states:
        return None
    try:
        import numpy as np

        code = _compile_vector(expr)
        function_names = {
            "abs", "__cdiv__", "__cmod__", "__logical_and__",
            "__logical_or__", "__logical_not__",
        }
        columns = {}
        for name in code.co_names:
            if name in function_names:
                continue
            if name.endswith("__PRE__"):
                key = name[:-7]
                if any(key not in state.pre for state in states):
                    return None
                columns[name] = np.fromiter(
                    (state.pre[key] for state in states), dtype=object, count=len(states)
                )
            else:
                if any(name not in state.vars for state in states):
                    return None
                columns[name] = np.fromiter(
                    (state.vars[name] for state in states), dtype=object, count=len(states)
                )

        def cdiv(left, right):
            left, right = np.asarray(left), np.asarray(right)
            if np.any(right == 0):
                raise ZeroDivisionError
            quotient = np.floor_divide(np.abs(left), np.abs(right))
            return np.where((left >= 0) == (right >= 0), quotient, -quotient)

        def cmod(left, right):
            return np.asarray(left) - cdiv(left, right) * np.asarray(right)

        namespace = {
            **columns,
            "abs": np.abs,
            "__cdiv__": cdiv,
            "__cmod__": cmod,
            "__logical_and__": np.logical_and,
            "__logical_or__": np.logical_or,
            "__logical_not__": np.logical_not,
        }
        result = np.asarray(eval(code, _SAFE_GLOBALS, namespace), dtype=bool)
        if result.ndim == 0:
            return None if bool(result) else states[0]
        false_indices = np.flatnonzero(~result)
        return states[int(false_indices[0])] if false_indices.size else None
    except Exception:
        for state in states:
            result = eval_predicate(expr, state)
            if result is False:
                return state
            if result is None:
                return None
        return None
