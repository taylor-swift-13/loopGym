"""
JSONL / Parquet I/O for the reward chain.

Reads rollout batches and writes per-rollout rewards in either format (chosen by
file extension: `.parquet` -> pandas+pyarrow, else JSON Lines).

Input layouts (both supported):
  * grouped : one row per prompt, with a list column of rollouts
      {"group_id": "...", "program": "<C src>", "rollouts": [{"invariants":[...]}|{"code":"..."}|"<text>", ...]}
  * flat    : one row per rollout; rows are grouped by `group_field`
      {"group_id": "g0", "program": "<C src>", "response": "<llm text or code>"}

Output: one row per rollout, aligned to input order, with reward fields —
ready to feed an RL trainer (verl/OpenRLHF style).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class IOConfig:
    program_field: str = "program"       # column holding the C source
    rollouts_field: str = "rollouts"     # list column (grouped layout)
    response_field: str = "response"     # per-rollout text/code (flat layout)
    group_field: str = "group_id"        # grouping key (flat layout)


@dataclass
class Batch:
    group_id: Any
    program: str
    rollouts: List[Any]


def _read_rows(path: str) -> List[Dict[str, Any]]:
    if path.endswith(".parquet"):
        import pandas as pd
        df = pd.read_parquet(path)
        return df.to_dict("records")
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _norm_list(v):
    # parquet round-trips lists as numpy arrays; normalize to plain list
    if v is None:
        return []
    try:
        import numpy as np
        if isinstance(v, np.ndarray):
            return v.tolist()
    except Exception:
        pass
    return list(v) if isinstance(v, (list, tuple)) else [v]


def read_batches(path: str, cfg: Optional[IOConfig] = None) -> List[Batch]:
    """Read rollout batches from JSONL/Parquet (auto-detects grouped vs flat)."""
    cfg = cfg or IOConfig()
    rows = _read_rows(path)
    if not rows:
        return []
    grouped = cfg.rollouts_field in rows[0]
    batches: List[Batch] = []
    if grouped:
        for i, r in enumerate(rows):
            batches.append(Batch(
                group_id=r.get(cfg.group_field, i),
                program=r[cfg.program_field],
                rollouts=_norm_list(r.get(cfg.rollouts_field)),
            ))
    else:  # flat: group consecutive rows by group_field (falls back to program)
        order: List[Any] = []
        groups: Dict[Any, Batch] = {}
        for i, r in enumerate(rows):
            gid = r.get(cfg.group_field, r.get(cfg.program_field))
            if gid not in groups:
                groups[gid] = Batch(group_id=gid, program=r[cfg.program_field], rollouts=[])
                order.append(gid)
            groups[gid].rollouts.append(r.get(cfg.response_field, ""))
        batches = [groups[g] for g in order]
    return batches


def write_rows(path: str, rows: List[Dict[str, Any]]) -> None:
    """Write reward rows to JSONL/Parquet (by extension)."""
    if path.endswith(".parquet"):
        import pandas as pd
        pd.DataFrame(rows).to_parquet(path, index=False)
        return
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def batch_reward_to_rows(batch: Batch, br, include_program: bool = False) -> List[Dict[str, Any]]:
    """Flatten a BatchReward into one output row per rollout."""
    out: List[Dict[str, Any]] = []
    for rs in br.rollouts:
        row = {
            "group_id": batch.group_id,
            "rollout_index": rs.index,
            "reward": rs.reward,
            "base": rs.base,
            "marginal": rs.marginal,
            "rejected": rs.rejected,
            "invariants": rs.invariants,
            "survivors": rs.survivors,
            "batch_score": br.batch_score,
            "should_reroll": br.should_reroll,
            "filter_mode": br.filter_mode,
            "n_positives": br.n_positives,
            "n_negatives": br.n_negatives,
        }
        if include_program:
            row["program"] = batch.program
        out.append(row)
    return out
