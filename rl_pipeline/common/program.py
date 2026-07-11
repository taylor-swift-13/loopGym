"""
Lightweight parser for the benchmark C programs used in LoopGym.

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
signature, params, precondition (requires), one loop (guard + body span),
the local declarations in scope at the loop entry, and the postcondition
(assert / ensures).  We deliberately avoid a full C parser: the benchmark
programs are small and regular, and every downstream consumer only needs the
loop-entry variable set + guard + postcondition.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class LoopInfo:
    guard: str            # e.g. 'x > 0'
    body: str             # source text between the loop's { }
    kw_start: int         # index of the loop keyword in source
    body_open: int        # index of the '{' opening the loop body
    body_close: int       # index of the matching '}'


@dataclass
class Program:
    source: str
    func_name: str
    params: List[str]                       # int parameter names, in order
    requires: str                           # precondition (ACSL), may be ''
    post: str                               # assert/ensures postcondition, may be ''
    pre_vars: List[str]                     # variables in scope at loop entry
    local_inits: List[Tuple[str, str]]      # (name, init_expr) declared before first loop
    unsigned_vars: List[str] = field(default_factory=list)
    loops: List[LoopInfo] = field(default_factory=list)

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


_ACSL_BINDER_RE = re.compile(r"\\(?:forall|exists|lambda|let)\b")


def _acsl_clause_end(source: str, expression_start: int) -> int:
    """Return the terminating semicolon's index, ignoring binder semicolons."""
    pending_binders = 0
    index = expression_start
    while index < len(source):
        if source[index] == "\\":
            binder = _ACSL_BINDER_RE.match(source, index)
            if binder:
                pending_binders += 1
                index = binder.end()
                continue
        if source[index] == ";":
            if pending_binders:
                pending_binders -= 1
            else:
                return index
        index += 1
    return len(source)


def _iter_acsl_clauses(source: str, keyword: str):
    for match in re.finditer(rf"\b{re.escape(keyword)}\b", source):
        end = _acsl_clause_end(source, match.end())
        stop = end + 1 if end < len(source) else end
        yield match.start(), stop, source[match.end():end].strip()


def _strip_acsl_targets(body: str) -> str:
    out: List[str] = []
    cursor = 0
    for match in re.finditer(r"\b(?:assert|ensures)\b", body):
        if match.start() < cursor:
            continue
        end = _acsl_clause_end(body, match.end())
        stop = end + 1 if end < len(body) else end
        out.append(body[cursor:match.start()])
        out.append(re.sub(r"[^\n]", " ", body[match.start():stop]))
        cursor = stop
    out.append(body[cursor:])
    return "".join(out)


def _extract_requires(src: str) -> str:
    """All `requires <expr>;` clauses conjoined — a precondition may span several
    clauses (`requires x>0; requires y>0;`) and dropping any of them lets
    out-of-contract inputs poison the sampled positives."""
    clauses = [expression for _, _, expression in _iter_acsl_clauses(src, "requires")]
    if len(clauses) > 1:
        return " && ".join(f"({c})" for c in clauses)
    if not clauses:
        return ""
    return re.sub(r"\s+", " ", clauses[0]).strip()


def strip_postcondition(source: str) -> str:
    """Remove the postcondition (assert/ensures) from the program text.

    Shown to the invariant-GENERATING model so it never sees the goal it must
    prove — it must synthesise invariants from the loop semantics, not read off
    (or restate) the assertion. The reward caller retains the full source for
    verification, while the sampler ignores the target. `requires` is kept."""
    # Preserve input contracts when `requires` and `ensures` share one block.
    def _strip_target_clauses(match):
        body = _strip_acsl_targets(match.group(1))
        return "/*@" + body + "*/" if body.strip() else ""

    out = re.sub(r"/\*@(.*?)\*/", _strip_target_clauses, source, flags=re.DOTALL)

    def _strip_line_target(match):
        body = _strip_acsl_targets(match.group(1))
        prefix = "//@" + body.rstrip() if body.strip() else ""
        return prefix + match.group(2)

    out = re.sub(r"//@([^\n]*)(\n|$)", _strip_line_target, out)
    return out


def _function_contract(src: str, signature_start: int) -> str:
    """Return the ACSL block or consecutive ``//@`` lines before a function."""
    contract = ""
    for match in re.finditer(r"/\*@.*?\*/", src[:signature_start], flags=re.DOTALL):
        if not src[match.end():signature_start].strip():
            contract = match.group(0)
    line_contract = re.search(
        r"(?m)((?:^[ \t]*//@[^\n]*(?:\n|$))+)[ \t]*$",
        src[:signature_start],
    )
    if line_contract:
        contract = line_contract.group(1)
    return contract


def _extract_post(src: str, after: int, before: int, contract: str = "") -> str:
    """Find an `assert <expr>;` (preferred, after the loop) or an `ensures`."""
    # assert after the loop
    for start, _, expression in _iter_acsl_clauses(src, "assert"):
        if after <= start < before:
            return re.sub(r"\s+", " ", expression).strip()
    # ensures clause
    for _, _, expression in _iter_acsl_clauses(contract, "ensures"):
        return re.sub(r"\s+", " ", expression).strip()
    return ""


def _parse_params(param_str: str) -> Tuple[List[str], List[str]]:
    names: List[str] = []
    unsigned: List[str] = []
    for p in param_str.split(","):
        p = p.strip()
        if not p or p == "void":
            continue
        if "*" in p or "[" in p:
            raise ValueError("only scalar integer parameters are supported")
        m = re.fullmatch(
            r"(?:const\s+)?(?:unsigned\s+|signed\s+)?int\s+(\w+)",
            p,
        )
        if not m:
            raise ValueError(f"unsupported parameter declaration: {p}")
        names.append(m.group(1))
        if re.search(r"\bunsigned\b", p):
            unsigned.append(m.group(1))
    return names, unsigned


def _find_signature(clean: str, start: int = 0) -> Optional[Tuple[str, str, int, int]]:
    """Return (name, param_str, signature_start, body_open_index)."""
    pattern = re.compile(r"\b(int|void|long|unsigned|short)\b[\w\s\*]*?(\w+)\s*\(")
    for m in pattern.finditer(clean, start):
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
            param_str = clean[paren_open + 1: paren_close]
            return name, param_str, m.start(), j
    return None


def _find_loops(clean: str, start: int, end: int) -> List[LoopInfo]:
    """Find braced ``while`` loops.

    C ``for`` loops are intentionally rejected: copying only their body for an
    over-run omits the increment expression, and a declaration in the init
    clause is out of scope after the loop. Silently treating those as ``while``
    loops produced invalid or semantically wrong samples.
    """
    loops: List[LoopInfo] = []
    for m in re.finditer(r"\bwhile\b", clean):
        if m.start() < start or m.start() >= end:
            continue
        paren_open = clean.find("(", m.end())
        if paren_open < 0:
            continue
        paren_close = _match_paren(clean, paren_open)
        if paren_close < 0:
            continue
        guard = clean[paren_open + 1: paren_close].strip()
        j = paren_close + 1
        while j < len(clean) and clean[j].isspace():
            j += 1
        if j >= len(clean) or clean[j] != "{":
            continue
        body_close = _match_brace(clean, j)
        if body_close < 0:
            continue
        loops.append(LoopInfo(
            guard=re.sub(r"\s+", " ", guard).strip(),
            body=clean[j + 1: body_close],
            kw_start=m.start(),
            body_open=j,
            body_close=body_close,
        ))
    loops.sort(key=lambda loop: loop.kw_start)
    return loops


def _find_local_inits(src: str, func_open: int, loop_start: int) -> List[Tuple[str, str]]:
    """Locals in scope at the loop entry, including comma-separated declarator lists
    like `int a,b,p,q,r,s;` (values assigned later) — every name must be captured so
    it appears in pre_vars, else the sampler has no variables to work with."""
    region = src[func_open + 1: loop_start]
    if re.search(r"\b(?:long|short|char|float|double|_Bool)\b", region):
        raise ValueError("only scalar int locals are supported")
    inits: List[Tuple[str, str]] = []
    seen = set()
    # `int <declarator-list>;` — split the list on commas. A bare
    # declarator has an UNKNOWN entry value ("") — inventing "0" here poisoned
    # downstream entry-value reasoning whenever the real pre-loop assignment
    # was nondeterministic (`int c; c = unknown();`).
    for m in re.finditer(r"\b(?:unsigned\s+|signed\s+)?int\s+([^;{}]+);", region):
        decls = m.group(1)
        if re.fullmatch(r"\s*\w+\s*\([^=]*\)\s*", decls):
            # A function declaration, not a variable whose initializer happens
            # to contain parentheses (for example ``int k = n % (d - 2)``).
            continue
        for part in decls.split(","):
            part = part.strip()
            declarator = part.partition("=")[0]
            if "*" in declarator or "[" in declarator:
                raise ValueError("only scalar integer locals are supported")
            if "=" in part:
                nm, _, expr = part.partition("=")
                nm, expr = nm.strip(), re.sub(r"\s+", " ", expr).strip()
            else:
                nm, expr = part, ""
            nm = re.sub(r"\[.*\]", "", nm.lstrip("*")).strip()   # drop ptr/array decorators
            if re.fullmatch(r"\w+", nm) and nm not in seen:
                seen.add(nm)
                inits.append((nm, expr))
    # pre-loop assignments override: the LAST top-level `name = expr;` before
    # the loop is the value actually in scope at entry (`int i; ... i = 0;` ->
    # "0").  Assignments nested in braces (pre-loop conditionals) are skipped —
    # they are not guaranteed to execute.
    last_assign: dict = {}
    for m in re.finditer(r"\b(\w+)\s*=\s*([^=;][^;]*);", region):
        prefix = region[:m.start()]
        if prefix.count("{") != prefix.count("}"):
            continue
        last_assign[m.group(1)] = re.sub(r"\s+", " ", m.group(2)).strip()
    inits = [(nm, last_assign.get(nm, expr)) for nm, expr in inits]
    return inits


def _find_unsigned_locals(src: str, func_open: int, loop_start: int) -> List[str]:
    region = src[func_open + 1:loop_start]
    names: List[str] = []
    for match in re.finditer(r"\bunsigned\s+(?:int\s+)?([^;{}]+);", region):
        for declarator in match.group(1).split(","):
            name = declarator.partition("=")[0].strip().lstrip("*")
            name = re.sub(r"\[.*\]", "", name).strip()
            if re.fullmatch(r"\w+", name) and name not in names:
                names.append(name)
    return names


def _find_global_ints(src: str, before: int) -> Tuple[List[str], List[str]]:
    """Return file-scope scalar integer names visible to the selected function.

    Globals are part of the loop-head state. Omitting one can collapse two
    distinct concrete states to the same sampled valuation and turn a reachable
    projection into a synthetic negative.
    """
    clean = _strip_comments(src[:before])
    top = list(clean)
    depth = 0
    for index, char in enumerate(clean):
        if char == "{":
            depth += 1
            top[index] = "\n"
        elif char == "}":
            top[index] = "\n"
            depth = max(0, depth - 1)
        elif depth and char != "\n":
            top[index] = " "
    top_level = "".join(top)

    names: List[str] = []
    unsigned: List[str] = []
    declaration = re.compile(
        r"(?m)^\s*(?P<type>(?:(?:static|extern|const|volatile)\s+)*"
        r"(?:(?:unsigned|signed)\s+)?(?:int|long|short))\s+"
        r"(?P<decls>[^;{}]+);"
    )
    for match in declaration.finditer(top_level):
        if re.search(r"\b(?:long|short)\b", match.group("type")):
            raise ValueError("only scalar int globals are supported")
        decls = match.group("decls")
        if "(" in decls:
            continue
        for declarator in decls.split(","):
            raw = declarator.partition("=")[0].strip()
            if "*" in raw or "[" in raw:
                raise ValueError("only scalar integer globals are supported")
            name = raw.strip()
            if re.fullmatch(r"\w+", name) and name not in names:
                names.append(name)
                if re.search(r"\bunsigned\b", match.group("type")):
                    unsigned.append(name)
    return names, unsigned


def parse_program(source: str) -> Program:
    """Parse a benchmark C program. Raises ValueError if no function/loop found."""
    clean = _strip_comments(source)
    search_from = 0
    selected = None
    while True:
        sig = _find_signature(clean, search_from)
        if sig is None:
            break
        name, param_str, sig_start, func_open = sig
        func_close = _match_brace(clean, func_open)
        if func_close < 0:
            raise ValueError(f"unclosed function body for {name}")
        loops = _find_loops(clean, func_open, func_close)
        if loops:
            if len(loops) != 1:
                raise ValueError(
                    f"multiple loops are not supported in function {name}"
                )
            selected = (name, param_str, sig_start, func_open, func_close, loops)
            break
        search_from = func_close + 1
    if selected is None:
        if re.search(r"\bfor\s*\(", clean):
            raise ValueError("for loops are not supported; use a braced while loop")
        raise ValueError("no function containing a loop was found")
    name, param_str, sig_start, func_open, func_close, loops = selected
    params, unsigned_params = _parse_params(param_str)
    global_vars, unsigned_globals = _find_global_ints(source, sig_start)

    first_loop = loops[0]
    local_inits = _find_local_inits(source, func_open, first_loop.kw_start)
    unsigned_vars = unsigned_globals + [
        name for name in unsigned_params if name not in unsigned_globals
    ] + [
        name for name in _find_unsigned_locals(source, func_open, first_loop.kw_start)
        if name not in unsigned_globals and name not in unsigned_params
    ]

    # variables in scope at the loop entry = params + locals declared before it
    pre_vars: List[str] = list(global_vars) + [
        param for param in params if param not in global_vars
    ]
    for n_, _e in local_inits:
        if n_ not in pre_vars:
            pre_vars.append(n_)

    # requires/assert live inside /*@ ... */ blocks, which _strip_comments blanks
    # out.  Comment-stripping preserves indices (spaces, not deletion), so we can
    # extract these from the ORIGINAL source using the same offsets.
    contract = _function_contract(source, sig_start)
    requires = _extract_requires(contract)
    post = _extract_post(source, after=first_loop.body_close,
                         before=func_close, contract=contract)

    return Program(
        source=source,
        func_name=name,
        params=params,
        requires=requires,
        post=post,
        pre_vars=pre_vars,
        local_inits=local_inits,
        unsigned_vars=unsigned_vars,
        loops=loops,
    )
