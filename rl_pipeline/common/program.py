"""
Lightweight parser for the benchmark C programs used in SAM2INV.

A program looks like:

    /*@ requires n>=0; */
    void foo100(int n) {
        int x = n;
        int y = 0;
        while (x > 0) {
            y = y + 1;
            x = x - 1;
        }
        /*@ assert y == n ; */
    }

We extract exactly what the sampler / reward / inference components need:
signature, params, precondition (requires), the loop(s) (guard + body span),
the local declarations in scope at the loop entry, and the postcondition
(assert / ensures).  We deliberately avoid a full C parser: the benchmark
programs are small and regular, and every downstream consumer only needs the
loop-entry variable set + guard + postcondition.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

_TYPE_KEYWORDS = ("int", "long", "unsigned", "short", "void", "float", "double")


@dataclass
class LoopInfo:
    keyword: str          # 'while' | 'for'
    guard: str            # e.g. 'x > 0'
    body: str             # source text between the loop's { }
    kw_start: int         # index of the loop keyword in source
    body_open: int        # index of the '{' opening the loop body
    body_close: int       # index of the matching '}'


@dataclass
class Program:
    source: str
    func_name: str
    ret_type: str
    params: List[str]                       # int parameter names, in order
    requires: str                           # precondition (ACSL), may be ''
    post: str                               # assert/ensures postcondition, may be ''
    pre_vars: List[str]                     # variables in scope at loop entry
    local_inits: List[Tuple[str, str]]      # (name, init_expr) declared before first loop
    loops: List[LoopInfo] = field(default_factory=list)
    func_open: int = 0                      # index of the function body '{'

    @property
    def loop(self) -> Optional[LoopInfo]:
        return self.loops[0] if self.loops else None


def _match_brace(src: str, open_idx: int) -> int:
    """Given index of an opening '{', return index of the matching '}'."""
    depth = 0
    i = open_idx
    n = len(src)
    while i < n:
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _match_paren(src: str, open_idx: int) -> int:
    """Given index of an opening '(', return index of the matching ')'."""
    depth = 0
    i = open_idx
    n = len(src)
    while i < n:
        c = src[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _strip_comments(src: str) -> str:
    """Blank out /* ... */ and // comments (preserve length for index stability)."""
    out = list(src)
    # block comments
    for m in re.finditer(r"/\*.*?\*/", src, flags=re.DOTALL):
        for i in range(m.start(), m.end()):
            if out[i] != "\n":
                out[i] = " "
    # line comments
    for m in re.finditer(r"//[^\n]*", "".join(out)):
        for i in range(m.start(), m.end()):
            out[i] = " "
    return "".join(out)


def _extract_requires(src: str) -> str:
    m = re.search(r"requires\s+(.+?);", src, flags=re.DOTALL)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()


def strip_postcondition(source: str) -> str:
    """Remove the postcondition (assert/ensures) from the program text.

    Shown to the invariant-GENERATING model so it never sees the goal it must
    prove — it must synthesise invariants from the loop semantics, not read off
    (or restate) the assertion.  The reward/sampler keeps the full program (with
    the assert) to derive negatives.  `requires` (the input contract) is kept."""
    # drop /*@ ... */ ACSL blocks that mention assert/ensures (the postcondition)
    def _repl(m):
        body = m.group(0)
        return "" if ("assert" in body or "ensures" in body) else body
    out = re.sub(r"/\*@.*?\*/", _repl, source, flags=re.DOTALL)
    # drop single-line //@ assert/ensures ...
    out = re.sub(r"//@[^\n]*\b(?:assert|ensures)\b[^\n]*\n?", "", out)
    return out


def _extract_post(src: str, after: int) -> str:
    """Find an `assert <expr>;` (preferred, after the loop) or an `ensures`."""
    # assert after the loop
    for m in re.finditer(r"\bassert\s*(.+?);", src, flags=re.DOTALL):
        if m.start() >= after:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    # fall back to any assert
    m = re.search(r"\bassert\s*(.+?);", src, flags=re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    # ensures clause
    m = re.search(r"ensures\s+(.+?);", src, flags=re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def _parse_params(param_str: str) -> List[str]:
    names: List[str] = []
    for p in param_str.split(","):
        p = p.strip()
        if not p or p == "void":
            continue
        m = re.match(r"(?:const\s+)?(?:unsigned\s+|signed\s+)?(?:int|long|short)\s*\*?\s*(\w+)", p)
        if m:
            names.append(m.group(1))
    return names


def _find_signature(clean: str) -> Optional[Tuple[str, str, str, int, int]]:
    """Return (ret_type, name, param_str, sig_start, body_open_idx)."""
    for m in re.finditer(r"\b(int|void|long|unsigned|short)\b[\w\s\*]*?(\w+)\s*\(", clean):
        name = m.group(2)
        paren_open = clean.index("(", m.end() - 1)
        paren_close = _match_paren(clean, paren_open)
        if paren_close < 0:
            continue
        # next non-space char must be '{'
        j = paren_close + 1
        while j < len(clean) and clean[j].isspace():
            j += 1
        if j < len(clean) and clean[j] == "{":
            ret_type = m.group(1)
            param_str = clean[paren_open + 1: paren_close]
            return ret_type, name, param_str, m.start(), j
    return None


def _find_loops(clean: str, start: int, end: int) -> List[LoopInfo]:
    loops: List[LoopInfo] = []
    for m in re.finditer(r"\b(while|for)\b", clean):
        if m.start() < start or m.start() >= end:
            continue
        paren_open = clean.find("(", m.end())
        if paren_open < 0:
            continue
        paren_close = _match_paren(clean, paren_open)
        if paren_close < 0:
            continue
        inner = clean[paren_open + 1: paren_close].strip()
        if m.group(1) == "for":
            # middle expression is the guard
            parts, part, depth = [], "", 0
            for ch in inner:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                if ch == ";" and depth == 0:
                    parts.append(part.strip())
                    part = ""
                else:
                    part += ch
            parts.append(part.strip())
            guard = parts[1] if len(parts) >= 2 and parts[1] else "1"
        else:
            guard = inner
        j = paren_close + 1
        while j < len(clean) and clean[j].isspace():
            j += 1
        if j >= len(clean) or clean[j] != "{":
            continue
        body_close = _match_brace(clean, j)
        if body_close < 0:
            continue
        loops.append(LoopInfo(
            keyword=m.group(1),
            guard=re.sub(r"\s+", " ", guard).strip(),
            body=clean[j + 1: body_close],
            kw_start=m.start(),
            body_open=j,
            body_close=body_close,
        ))
    loops.sort(key=lambda l: l.kw_start)
    return loops


def _find_local_inits(src: str, func_open: int, loop_start: int) -> List[Tuple[str, str]]:
    """Locals in scope at the loop entry, including comma-separated declarator lists
    like `int a,b,p,q,r,s;` (values assigned later) — every name must be captured so
    it appears in pre_vars, else the sampler has no variables to work with."""
    region = src[func_open + 1: loop_start]
    inits: List[Tuple[str, str]] = []
    seen = set()
    # `int|long|short <declarator-list>;` — split the list on commas
    for m in re.finditer(r"\b(?:unsigned\s+|signed\s+)?(?:int|long|short)\s+([^;{}]+);", region):
        decls = m.group(1)
        if "(" in decls:            # skip function declarations
            continue
        for part in decls.split(","):
            part = part.strip()
            if "=" in part:
                nm, _, expr = part.partition("=")
                nm, expr = nm.strip(), re.sub(r"\s+", " ", expr).strip()
            else:
                nm, expr = part, "0"
            nm = re.sub(r"\[.*\]", "", nm.lstrip("*")).strip()   # drop ptr/array decorators
            if re.fullmatch(r"\w+", nm) and nm not in seen:
                seen.add(nm)
                inits.append((nm, expr))
    return inits


def parse_program(source: str) -> Program:
    """Parse a benchmark C program. Raises ValueError if no function/loop found."""
    clean = _strip_comments(source)
    sig = _find_signature(clean)
    if sig is None:
        raise ValueError("could not locate a function signature")
    ret_type, name, param_str, _sig_start, func_open = sig
    params = _parse_params(param_str)

    func_close = _match_brace(clean, func_open)
    if func_close < 0:
        func_close = len(clean)

    loops = _find_loops(clean, func_open, func_close)
    if not loops:
        raise ValueError("no loop found in function body")

    first_loop = loops[0]
    local_inits = _find_local_inits(source, func_open, first_loop.kw_start)

    # variables in scope at the loop entry = params + locals declared before it
    pre_vars: List[str] = list(params)
    for n_, _e in local_inits:
        if n_ not in pre_vars:
            pre_vars.append(n_)

    # requires/assert live inside /*@ ... */ blocks, which _strip_comments blanks
    # out.  Comment-stripping preserves indices (spaces, not deletion), so we can
    # extract these from the ORIGINAL source using the same offsets.
    requires = _extract_requires(source)
    post = _extract_post(source, after=first_loop.body_close)

    return Program(
        source=source,
        func_name=name,
        ret_type=ret_type,
        params=params,
        requires=requires,
        post=post,
        pre_vars=pre_vars,
        local_inits=local_inits,
        loops=loops,
        func_open=func_open,
    )
