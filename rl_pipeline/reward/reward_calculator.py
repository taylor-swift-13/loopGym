"""
RewardCalculator — Component 2.

Given a program and a GROUP of rollouts (each a candidate invariant set), score
each rollout and the batch, using the negative examples from the sampler:

  base[A]     = fraction of negatives rejected by Houdini(A alone)   ("hudini 后的分数")
  marginal[A] = fraction of negatives that Houdini(union) rejects but
                Houdini(union \ A) does not                          (ablation 增益)
  junk[A]     = fraction of A's emitted invariants that are NOT useful: killed
                by the filter (unsound / out-of-scope / memorization-sized) OR
                surviving without a UNIQUE rejection (pure spray that only
                shadows stronger clauses in the same rollout)
  reward[A]   = max(0, w_base * base[A] + w_marg * marginal[A] - w_junk * junk[A])
  batch_score = fraction of negatives rejected by Houdini(union)     (batch performance)
  should_reroll = batch_score < reroll_threshold

The junk term is a gentle tie-breaker (w_junk defaults to 0.05): the filter
already strips garbage from scoring, but without a cost, "gold + spray" ties
"gold" and the policy is free to spam unsound candidates — or to ride a strong
true clause with dozens of redundant ones (they all "survive", so only the
unique-kill accounting can rank the clean set strictly above the sprayed one).

Rollout size budget (_MAX_ROLLOUT_ATOMS): a real invariant set is a handful of
short laws.  Without a rollout-level cap, a policy can emit HUNDREDS of
gate-compliant clauses (`v != k`, `!(x==a && y==b)`) and memorize the entire
negative pool of small-sample programs.  Scoring uses only the emission-order
prefix within the atom budget — honest sets fit with room to spare.

Multi-seed scoring (n_seeds, default 2): example sets are deterministic per
(program, seed), so a policy trained against one fixed sample can profit from
MEMORIZING it (measured: up to ~2x base for a pointwise farm on some programs).
Scoring against n_seeds independent samples and taking the per-rollout MINIMUM
removes the memorization surplus — a true invariant scores identically under
every seed, while an overfit predicate only keeps its structural share.

Holdout seeds (n_holdout, default 1): the canonical seeds are FIXED, so a
long-trained policy sees their samples reflected in its rewards and can adapt
to them; sample-extreme boxes (`lo <= v <= hi` at observed extremes) survive
min-combining over seen seeds.  Each compute() additionally scores against
n_holdout freshly-seeded example sets (random seed unless pinned) — an overfit
box is violated by the fresh positives (filtered) or misses the fresh
negatives, while a true invariant is indifferent to the seed.

A candidate set "rejects" a negative valuation s iff some (Houdini-surviving)
invariant evaluates to False at s — a cheap pure-Python check on states.  The
only Frama-C cost is the Houdini step (swappable; see filters.py).
"""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Set, Union

from ..common.program import Program, parse_program
from ..common.state import (
    State, eval_predicate, normalize_invariant, dedup_normalized, extract_invariants,
)
from ..sampler import ExampleSampler, ExampleSet
from . import filters

# Rollout-level size budget (total comparison atoms across the whole invariant
# set).  The per-predicate complexity gate (filters.too_complex) blocks single
# mega-predicates; this blocks the split version — hundreds of small
# gate-compliant clauses memorizing the negative pool one state at a time.
# Honest sets are ~3-6 clauses x 1-4 atoms; 32 leaves generous headroom.
_MAX_ROLLOUT_ATOMS = 32


def _atom_budget_prefix(invariants: List[str], budget: int = _MAX_ROLLOUT_ATOMS) -> List[str]:
    """Emission-order prefix whose cumulative atom count fits the budget."""
    out, atoms = [], 0
    for inv in invariants:
        n = max(1, len(filters._ATOM_RE.findall(inv)))
        if out and atoms + n > budget:
            break
        out.append(inv)
        atoms += n
    return out


@dataclass
class RolloutScore:
    index: int
    invariants: List[str]
    survivors: List[str]          # Houdini-surviving invariants (standalone)
    base: float
    marginal: float
    reward: float
    rejected: int                 # negatives rejected standalone


@dataclass
class BatchReward:
    program: str
    n_positives: int
    n_negatives: int
    batch_score: float
    should_reroll: bool
    filter_mode: str
    seeds: int = 1
    rollouts: List[RolloutScore] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "program": self.program,
            "n_positives": self.n_positives,
            "n_negatives": self.n_negatives,
            "batch_score": self.batch_score,
            "should_reroll": self.should_reroll,
            "filter_mode": self.filter_mode,
            "seeds": self.seeds,
            "rollout_rewards": [r.reward for r in self.rollouts],
            "base": [r.base for r in self.rollouts],
            "marginal": [r.marginal for r in self.rollouts],
            "rollouts": [
                {"index": r.index, "reward": r.reward, "base": r.base,
                 "marginal": r.marginal, "rejected": r.rejected,
                 "survivors": r.survivors}
                for r in self.rollouts
            ],
        }


def _rollout_invariants(rollout, prog: Program) -> List[str]:
    """Accept {'invariants': [...]} or {'code': '<annotated>'} or a raw list/str.

    A string may be (a) a JSON-encoded dict/list (unwrapped and recursed), or
    (b) raw LLM text / annotated code containing `loop invariant ...;` lines.
    """
    if isinstance(rollout, dict):
        if rollout.get("invariants"):
            invs = rollout["invariants"]
        elif rollout.get("code"):
            invs = extract_invariants(rollout["code"])
        else:
            invs = []
    elif isinstance(rollout, (list, tuple)):
        invs = list(rollout)
    elif isinstance(rollout, str):
        s = rollout.strip()
        parsed = None
        if s[:1] in ("{", "["):
            try:
                parsed = json.loads(s)
            except ValueError:
                parsed = None
        if parsed is not None:
            return _rollout_invariants(parsed, prog)
        # raw text / annotated code: extract explicit `loop invariant` lines only
        invs = extract_invariants(s)
    else:
        invs = []
    return _atom_budget_prefix(dedup_normalized(invs))


class RewardCalculator:
    def __init__(
        self,
        invariant_filter=None,
        w_base: float = 0.5,
        w_marg: float = 0.5,
        w_junk: float = 0.05,
        n_seeds: int = 2,
        n_holdout: int = 1,
        holdout_seed: Optional[int] = None,
        reroll_threshold: float = 0.6,
        logger: Optional[logging.Logger] = None,
        sampler_kwargs: Optional[dict] = None,
    ):
        self.log = logger or logging.getLogger("rl_pipeline.reward")
        self.filter = invariant_filter or filters.auto_filter(self.log)
        self.w_base = w_base
        self.w_marg = w_marg
        self.w_junk = w_junk
        self.n_seeds = max(1, n_seeds)
        self.n_holdout = max(0, n_holdout)
        self.holdout_seed = holdout_seed          # None -> fresh random per compute()
        self.reroll_threshold = reroll_threshold
        self.sampler_kwargs = sampler_kwargs or {}

    # ── negative-rejection bookkeeping ───────────────────────────────────────
    @staticmethod
    def _rejected_set(negatives: List[State], invariants: List[str]) -> Set[int]:
        """Indices of negatives excluded by at least one invariant."""
        rej: Set[int] = set()
        for inv in invariants:
            cond = normalize_invariant(inv)
            for i, s in enumerate(negatives):
                if i in rej:
                    continue
                if eval_predicate(cond, s) is False:
                    rej.add(i)
        return rej

    @staticmethod
    def _per_clause_rejected(negatives: List[State], invariants: List[str]) -> List[Set[int]]:
        """Per-invariant rejected-index sets (no early exit — needed to tell
        clauses with a UNIQUE contribution from spray that only shadows others)."""
        out: List[Set[int]] = []
        for inv in invariants:
            cond = normalize_invariant(inv)
            out.append({i for i, s in enumerate(negatives)
                        if eval_predicate(cond, s) is False})
        return out

    # ── main ─────────────────────────────────────────────────────────────────
    def compute(self, source: str, rollouts: List,
                examples: Union[ExampleSet, Sequence[ExampleSet], None] = None,
                loop_idx: int = 0) -> BatchReward:
        """Score rollouts against one or several example sets.

        With several sets (the default samples `n_seeds` consecutive seeds plus
        `n_holdout` freshly-seeded ones) each rollout's reward/base/marginal are
        combined by MINIMUM across seeds — memorizing any one deterministic
        sample (or even every canonical seed) earns nothing."""
        if examples is None:
            kw = dict(self.sampler_kwargs)
            base_seed = int(kw.pop("seed", 0))
            examples = [ExampleSampler(source, seed=base_seed + k, **kw).sample()
                        for k in range(self.n_seeds)]
            for j in range(self.n_holdout):
                hs = (self.holdout_seed + j if self.holdout_seed is not None
                      else random.randrange(1 << 30))
                examples.append(ExampleSampler(source, seed=hs, **kw).sample())
        if isinstance(examples, ExampleSet):
            return self._compute_one(source, rollouts, examples, loop_idx)
        examples = list(examples)
        batches = [self._compute_one(source, rollouts, es, loop_idx) for es in examples]
        if len(batches) == 1:
            return batches[0]
        return self._combine(batches)

    @staticmethod
    def _combine(batches: List[BatchReward]) -> BatchReward:
        first = batches[0]
        rollouts: List[RolloutScore] = []
        for i, r0 in enumerate(first.rollouts):
            per = [b.rollouts[i] for b in batches]
            k = min(range(len(per)), key=lambda j: per[j].reward)
            rollouts.append(RolloutScore(
                index=r0.index, invariants=r0.invariants,
                survivors=per[k].survivors,
                base=min(r.base for r in per),
                marginal=min(r.marginal for r in per),
                reward=min(r.reward for r in per),
                rejected=min(r.rejected for r in per),
            ))
        return BatchReward(
            program=first.program,
            n_positives=min(b.n_positives for b in batches),
            n_negatives=min(b.n_negatives for b in batches),
            batch_score=min(b.batch_score for b in batches),
            should_reroll=any(b.should_reroll for b in batches),
            filter_mode=first.filter_mode,
            seeds=len(batches),
            rollouts=rollouts,
        )

    @staticmethod
    def _to_groups(state_rej: Set[int], groups: List[List[int]]) -> Set[int]:
        """Impossible-trace indices rejected: a trace is excluded when ANY of
        its witness states is (an invariant false at one point of the history
        proves the whole history cannot be produced)."""
        return {g for g, idxs in enumerate(groups) if any(i in state_rej for i in idxs)}

    def _compute_one(self, source: str, rollouts: List, examples: ExampleSet,
                     loop_idx: int = 0) -> BatchReward:
        prog = parse_program(source)
        positives = examples.pos(loop_idx)
        negatives = examples.neg(loop_idx)
        # scoring unit = impossible TRACE (witness group), not witness state
        if hasattr(examples, "groups"):
            groups = examples.groups(loop_idx)
        else:
            groups = [[i] for i in range(len(negatives))]
        n_neg = len(groups)

        roll_invs = [_rollout_invariants(r, prog) for r in rollouts]

        # memoize filter results across base/union/ablation calls — the ablation
        # subsets (∪ \ A) overlap heavily, so identical invariant sets are filtered
        # (and, in Houdini mode, verified by Frama-C) only once.
        survive_cache: dict = {}

        def survive(invs: List[str]) -> List[str]:
            if not invs:
                return []
            key = frozenset(normalize_invariant(i) for i in invs)
            cached = survive_cache.get(key)
            if cached is None:
                cached = self.filter.filter(prog, loop_idx, sorted(key), positives)
                survive_cache[key] = cached
            return cached

        # union across all rollouts
        union = dedup_normalized(c for invs in roll_invs for c in invs)
        union_surv = survive(union)
        union_rej = self._to_groups(self._rejected_set(negatives, union_surv), groups)
        batch_score = (len(union_rej) / n_neg) if n_neg else 0.0

        scores: List[RolloutScore] = []
        for idx, invs in enumerate(roll_invs):
            # base: standalone Houdini, with per-clause trace attribution
            surv = survive(invs)
            per_clause = [self._to_groups(rj, groups)
                          for rj in self._per_clause_rejected(negatives, surv)]
            base_rej: Set[int] = set().union(*per_clause) if per_clause else set()
            base = (len(base_rej) / n_neg) if n_neg else 0.0
            # marginal: ablation on the union (skipped when unweighted — the
            # ablation refilters |rollouts| near-union sets, dominating cost)
            if self.w_marg:
                rest = dedup_normalized(c for j, other in enumerate(roll_invs) if j != idx for c in other)
                rest_surv = survive(rest)
                rest_rej = self._to_groups(self._rejected_set(negatives, rest_surv), groups)
                marginal = (len(union_rej - rest_rej) / n_neg) if n_neg else 0.0
            else:
                marginal = 0.0
            # useful = survivors rejecting at least one TRACE nothing else in
            # this rollout rejects; filtered clauses and shadow spray are junk
            cover: dict = {}
            for rj in per_clause:
                for g in rj:
                    cover[g] = cover.get(g, 0) + 1
            useful = sum(1 for rj in per_clause if any(cover[g] == 1 for g in rj))
            junk = (1.0 - useful / len(invs)) if invs else 0.0
            reward = max(0.0, self.w_base * base + self.w_marg * marginal - self.w_junk * junk)
            scores.append(RolloutScore(
                index=idx, invariants=invs, survivors=surv,
                base=base, marginal=marginal, reward=reward, rejected=len(base_rej),
            ))

        return BatchReward(
            program=prog.func_name,
            n_positives=len(positives),
            n_negatives=n_neg,
            batch_score=batch_score,
            should_reroll=batch_score < self.reroll_threshold,
            filter_mode=getattr(self.filter, "name", "unknown"),
            rollouts=scores,
        )
