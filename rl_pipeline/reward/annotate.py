"""Insert an ACSL loop-invariant block into a program (shared by reward + inference)."""
from __future__ import annotations

import re
from typing import List

from ..common.program import Program
from ..common.state import normalize_invariant


def modified_vars(body: str) -> List[str]:
    """Variables assigned in the loop body (for the `loop assigns` frame clause)."""
    names: List[str] = []
    for m in re.finditer(r"\b(\w+)\s*(?:[-+*/%]?=)(?!=)", body):
        v = m.group(1)
        if v not in names:
            names.append(v)
    return names


def build_annotated(prog: Program, invariants: List[str], loop_idx: int = 0) -> str:
    """Return the program source with an ACSL block (invariants + assigns) before the loop."""
    loop = prog.loops[loop_idx]
    invs = [normalize_invariant(i) for i in invariants if normalize_invariant(i)]
    lines = [f"      loop invariant {i};" for i in invs]
    assigns = modified_vars(loop.body)
    if assigns:
        lines.append(f"      loop assigns {', '.join(assigns)};")
    block = "/*@\n" + "\n".join(lines) + "\n    */\n    "
    src = prog.source
    return src[:loop.kw_start] + block + src[loop.kw_start:]
