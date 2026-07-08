"""
Reward-discrimination harness: does the reward rank rollouts by TRUE quality,
and can it be hacked?

For each benchmark program we build rollout families of KNOWN relative quality:

  gold        true, tight invariant set (hand-written)
  loose       true but weaker subset            (must score <= gold)
  trivial     ["1 == 1"]                        (must score ~0)
  guard_copy  [loop guard]                      (violated at exit state -> ~0)
  post_copy   [assert expression]               (usually violated at entry -> ~0)
  unsound     pins a movable var to one sampled value (filtered -> ~0)
  diseq_farm  ADVERSARY: simulates the sampler, emits `v != k` clauses covering
              the most common negative slices (budget K) — a pure pointwise
              overfit with zero semantic content
  state_mem   ADVERSARY: `!(x==a && y==b)` whole-state memorizer — the split
              form of the mega-conjunction, every clause gate-compliant
  chunked_conj ADVERSARY: mega-conjunction split into gate-sized chunks
  const_bound ADVERSARY: per-var `lo <= v <= hi` at the SAMPLED extremes —
              overfits the sample whenever the true bound is symbolic/looser
  delta_bound ADVERSARY: same box in `v - \at(v,Pre)` space (survives on
              param programs where the plain box gets filtered)
  mod_hack    ADVERSARY: `v % m == r` predicates consistent with every sampled
              positive that reject some negatives without being gold facts
  affine_hack ADVERSARY: exact 2-var affine fits over the sampled positives —
              spurious sample-coincidence "laws" if any exist

THREAT MODEL: the adversary generators see the union of every CANONICAL seed's
sample (a policy trained against the fixed seeds can memorize them all), but
scoring — as deployed — min-combines the canonical seeds PLUS a holdout seed
the adversary has never seen.

Anti-hack criterion per program (margins configurable):
  * memorizers must sit far below gold:    reward(mem) <= reward(gold) - hack_margin
  * overfit boxes collapse on holdout:     reward(box) <= reward(gold) - hack_margin
      (except when the spec declares box_true: the reachable box is
       input-independent there, so the sampled box IS a true invariant —
       then it may tie gold but never beat it)
  * spray never ties clean sets:           reward(combo) <= reward(gold) - strict_eps
  * no adversarial family may BEAT gold:   reward(hack) <= reward(gold) + eps
  * gold must dominate junk by a margin:   reward(gold) >= reward(trivial) + margin
  * gold must actually work:               base(gold) >= min_gold_base
  * quality order:                         reward(gold) >= reward(loose) - eps

Run:  python -m rl_pipeline.eval.discrimination [--programs ...] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..common.program import parse_program
from ..common.state import eval_predicate
from ..reward.filters import PositiveFilter
from ..reward.reward_calculator import RewardCalculator
from ..sampler import ExampleSampler

REPO = Path(__file__).resolve().parents[2]
INPUT = REPO / "src" / "input"

# ── benchmark programs with hand-written ground truth ────────────────────────
# gold = true + tight; loose = true + strictly weaker.
# box_true: the reachable per-var ranges are INPUT-INDEPENDENT (no parameters
# feed the loop), so a box at the sampled extremes is a true invariant — the
# box adversaries legitimately tie gold there and are exempt from the
# collapse-on-holdout requirement.
SPECS: Dict[str, Dict[str, object]] = {
    "linear/103.c": {   # x=0; while(x<100) x++;           1-var, worst case for pointwise hacks
        "gold": ["0 <= x", "x <= 100"],
        "loose": ["0 <= x"],
        "box_true": True,
    },
    "linear/2.c": {     # x=1,y=0; while(y<1000){x+=y;y++}  long loop (cap stress)
        "gold": ["0 <= y", "y <= 1000", "2*x == y*y - y + 2"],
        "loose": ["0 <= y", "x >= 1"],
        "box_true": True,
    },
    "linear/1.c": {     # same but y<100000                 extreme length stress
        # x overflows int32 during the run, so the executed-semantics relation is
        # modular; `x >= 1` is NOT a true invariant of the compiled program.
        "gold": ["0 <= y", "y <= 100000", "(2*x - y*y + y - 2) % 4294967296 == 0"],
        "loose": ["0 <= y"],
        "box_true": True,
    },
    "linear/34.c": {    # x=n; while(x>0) x--;              symbolic bound
        "gold": ["x <= n", "n > 0 ==> x >= 0", "n <= 0 ==> x == n"],
        "loose": ["x <= n"],
    },
    "linear/68.c": {    # x=1; while(x<=n){y=n-x;x++}       param-dependent
        "gold": ["x >= 1", "n >= 1 ==> x <= n + 1", "x > 1 ==> y == n - x + 1",
                 "x == 1 ==> y == \\at(y,Pre)"],
        "loose": ["x >= 1"],
    },
    "linear/12.c": {    # while(unknown()){x+=10;y+=10}     nondeterministic guard, pre-relations
        "gold": [
            "x - y == \\at(x,Pre) - \\at(y,Pre)",
            "x >= \\at(x,Pre)",
            "(x - \\at(x,Pre)) % 10 == 0",
        ],
        "loose": ["x >= \\at(x,Pre)"],
    },
    "NLA_lipus/2.c": {  # division by counting: q,r vs x/y  C-division semantics
        "gold": ["0 <= q", "0 <= r", "r < y", "x >= y * q + r", "q <= x / y"],
        "loose": ["0 <= r", "x >= y * q + r"],
    },
    "NLA_lipus/15.c": { # c,y count, x=sum(1..y)            nonlinear relation
        "gold": ["c == y", "2*x == y*y + y", "0 <= c", "c <= k"],
        "loose": ["c == y", "0 <= c"],
        # requires k <= 30 bounds the INPUT space itself, so the sampled
        # extremes (c,y <= 30, x <= 465) are contract truth, not overfit
        "box_true": True,
    },
    "NLA_lipus/1.c": {  # cubic series                      nonlinear, multi-relation
        "gold": ["z == 6*n + 6", "y == 3*n*n + 3*n + 1", "x == n*n*n", "n >= 0", "n <= a + 1"],
        "loose": ["z == 6*n + 6", "n >= 0"],
    },
    "NLA_lipus/24.c": { # z=x*y; while(x>0){x--;z-=y}       nonlinear product relation
        "gold": ["z == x*y", "x >= 0"],
        "loose": ["x >= 0"],
    },
    "NLA_lipus/5.c": {  # extended GCD (comma declarators)   multi-var bilinear relations
        "gold": ["a == p*x + r*y", "b == q*x + s*y", "p*s - r*q == 1", "a >= 1", "b >= 1"],
        "loose": ["p*s - r*q == 1", "a >= 1"],
        "post_is_invariant": True,
    },
    # NOTE: linear/301.c, linear/173.c, linear/45.c were removed from SPECS
    # when the nondeterminism rescue layer (rigid-pair / lattice / monotone /
    # guarded-bound negatives) was dropped for simplicity: their negatives were
    # entirely rescue-generated, so they now yield zero signal (sound, just
    # uninformative) and cannot support a gold-vs-hack comparison.
}

DISEQ_BUDGET = 16          # adversary's clause budget for the pointwise farm
MOD_BUDGET = 3


# ── adversarial rollout generators (attacker knows the sampler source) ───────

def _pos_value_sets(examples) -> Dict[str, set]:
    """Per-variable observed positive values (precomputed once — the positive
    pool can be huge on nondeterministic programs)."""
    values: Dict[str, set] = {}
    for p in examples.pos(0):
        for v, val in p.vars.items():
            values.setdefault(v, set()).add(val)
    return values


def diseq_farm(examples, budget: int = DISEQ_BUDGET) -> List[str]:
    """Cover the biggest (var == value) slices of the negative set with `v != k`."""
    slices: Counter = Counter()
    for s in examples.neg(0):
        for v, val in s.vars.items():
            slices[(v, val)] += 1
    pos_vals = _pos_value_sets(examples)
    farm = []
    covered = set()
    for (v, val), _n in slices.most_common():
        if len(farm) >= budget:
            break
        # skip slices that also hit positives (would be filtered as unsound)
        if val in pos_vals.get(v, ()):
            continue
        key = (v, val)
        if key in covered:
            continue
        covered.add(key)
        farm.append(f"{v} != {val}")
    return farm


def const_bounds(examples) -> List[str]:
    """Per-variable bounds at the sampled extremes (sample-overfit box)."""
    pos = examples.pos(0)
    if not pos:
        return []
    out = []
    for v in pos[0].vars:
        vals = [p.vars[v] for p in pos]
        out.append(f"{v} >= {min(vals)}")
        out.append(f"{v} <= {max(vals)}")
    return out


def mod_hacks(examples, gold: List[str], budget: int = MOD_BUDGET) -> List[str]:
    """`v % m == r` facts consistent with all positives, rejecting >=5% negatives,
    and not implied by (textually present in) gold."""
    pos, neg = examples.pos(0), examples.neg(0)
    if not pos or not neg:
        return []
    gold_text = " ".join(gold)
    pos_vals = _pos_value_sets(examples)
    out = []
    for v in pos[0].vars:
        for m in (2, 3, 4, 5, 7):
            residues = {val % m for val in pos_vals.get(v, ())}
            if len(residues) != 1:
                continue
            r = residues.pop()
            pred = f"{v} % {m} == {r}"
            if f"% {m}" in gold_text and v in gold_text:
                continue
            rej = sum(1 for s in neg if eval_predicate(pred, s) is False)
            if rej >= 0.05 * len(neg):
                out.append(pred)
            if len(out) >= budget:
                return out
    return out


def interval_farm(examples, budget: int = 16, max_width: int = 200) -> List[str]:
    """ADVERSARY: window exclusions `!(a <= v && v <= b)` over positive-free
    value bands — the INTERVAL generalization of the diseq farm.  2 atoms per
    clause; each clause kills every negative whose v-value falls in the band,
    and a band (unlike an exact value) survives per-seed delta hashing as long
    as the negatives CLUSTER.  Defeated only by (a) the exact single-var
    soundness check and (b) decade-spread negative placement."""
    pos_vals = _pos_value_sets(examples)
    per_var: Dict[str, Counter] = {}
    for s in examples.neg(0):
        for v, val in s.vars.items():
            if val not in pos_vals.get(v, ()):
                per_var.setdefault(v, Counter())[val] += 1
    clauses = []
    for v, cnt in per_var.items():
        vals = sorted(cnt)
        pv = pos_vals.get(v, set())
        i = 0
        while i < len(vals):
            j, weight = i, cnt[vals[i]]
            while (j + 1 < len(vals) and vals[j + 1] - vals[i] <= max_width
                   and not any(p in pv for p in range(vals[j] + 1, vals[j + 1] + 1))):
                j += 1
                weight += cnt[vals[j]]
            clauses.append((weight, f"!({vals[i]} <= {v} && {v} <= {vals[j]})"))
            i = j + 1
    clauses.sort(key=lambda t: -t[0])
    return [c for _w, c in clauses[:budget]]


def delta_interval_farm(examples, budget: int = 16, max_width: int = 200) -> List[str]:
    """ADVERSARY: the interval farm in `v - \\at(v,Pre)` space — transfers on
    parameterized programs where absolute windows do not."""
    pos_d: Dict[str, set] = {}
    for p in examples.pos(0):
        for v, val in p.vars.items():
            if v in p.pre:
                pos_d.setdefault(v, set()).add(val - p.pre[v])
    per_var: Dict[str, Counter] = {}
    for s in examples.neg(0):
        for v, val in s.vars.items():
            if v in s.pre:
                d = val - s.pre[v]
                if d not in pos_d.get(v, ()):
                    per_var.setdefault(v, Counter())[d] += 1
    clauses = []
    for v, cnt in per_var.items():
        vals = sorted(cnt)
        pv = pos_d.get(v, set())
        i = 0
        while i < len(vals):
            j, weight = i, cnt[vals[i]]
            while (j + 1 < len(vals) and vals[j + 1] - vals[i] <= max_width
                   and not any(p in pv for p in range(vals[j] + 1, vals[j + 1] + 1))):
                j += 1
                weight += cnt[vals[j]]
            clauses.append(
                (weight, f"!({vals[i]} <= {v} - \\at({v},Pre) && {v} - \\at({v},Pre) <= {vals[j]})"))
            i = j + 1
    clauses.sort(key=lambda t: -t[0])
    return [c for _w, c in clauses[:budget]]


def pair_window_farm(examples, budget: int = 16, max_width: int = 200) -> List[str]:
    """ADVERSARY: window exclusions in CONSERVED-EXPRESSION space — for 2-var
    linear combos E ∈ {u−w, u+w}, small relation perturbations cluster within
    a few units of the reachable E-manifold, so `!(a <= u−w && u−w <= b)` can
    memorize the whole single-axis family across seeds.  Sound on the sample
    whenever no positive E-value falls in the band.  Defeated by far relation
    deltas (they spread E by decades) — not by the single-var exact check
    (E references two variables)."""
    pos = examples.pos(0)
    negs = examples.neg(0)
    if not pos:
        return []
    names = sorted(pos[0].vars)
    clauses = []
    for a_i in range(len(names)):
        for b_i in range(a_i + 1, len(names)):
            u, w = names[a_i], names[b_i]
            for cu, cw, expr in ((1, -1, f"{u} - {w}"), (1, 1, f"{u} + {w}")):
                pos_e = {cu * p.vars[u] + cw * p.vars[w] for p in pos
                         if u in p.vars and w in p.vars}
                cnt: Counter = Counter()
                for s in negs:
                    if u in s.vars and w in s.vars:
                        e = cu * s.vars[u] + cw * s.vars[w]
                        if e not in pos_e:
                            cnt[e] += 1
                vals = sorted(cnt)
                i = 0
                while i < len(vals):
                    j, weight = i, cnt[vals[i]]
                    while (j + 1 < len(vals) and vals[j + 1] - vals[i] <= max_width
                           and not any(p in pos_e
                                       for p in range(vals[j] + 1, vals[j + 1] + 1))):
                        j += 1
                        weight += cnt[vals[j]]
                    clauses.append(
                        (weight, f"!({vals[i]} <= {expr} && {expr} <= {vals[j]})"))
                    i = j + 1
    clauses.sort(key=lambda t: -t[0])
    return [c for _w, c in clauses[:budget]]


def state_memorizer(examples, budget: int = 256) -> List[str]:
    """Whole-state negations `!(x==a && y==b)` — the split mega-conjunction.
    Every clause passes the per-predicate complexity gate; only the ROLLOUT
    atom budget stops it from memorizing small negative pools outright."""
    out, seen = [], set()
    for s in examples.neg(0):
        r = s.render()
        if r in seen:
            continue
        seen.add(r)
        out.append(f"!({r})")
        if len(out) >= budget:
            break
    return out


def chunked_conjunction(examples, chunk: int = 3, budget: int = 170) -> List[str]:
    """Mega-conjunction split into gate-compliant chunks of `chunk` states."""
    negs = examples.neg(0)
    out = []
    for i in range(0, len(negs), chunk):
        if len(out) >= budget:
            break
        out.append(" && ".join(f"!({s.render()})" for s in negs[i:i + chunk]))
    return out


def delta_bounds(examples) -> List[str]:
    """Sampled-extreme box on `v - \\at(v,Pre)` — the overfit box in delta
    space, which survives the positive filter on param programs where the
    plain box gets filtered (the delta range LOOKS input-independent)."""
    pos = examples.pos(0)
    if not pos:
        return []
    out = []
    for v in pos[0].vars:
        ds = [p.vars[v] - p.pre[v] for p in pos if v in p.pre]
        if not ds:
            continue
        out.append(f"{v} - \\at({v},Pre) >= {min(ds)}")
        out.append(f"{v} - \\at({v},Pre) <= {max(ds)}")
    return out


def affine_hacks(examples, gold: List[str], budget: int = 4) -> List[str]:
    """Exact 2-var affine relations `a*u + b*w == c` fitted on the sampled
    positives — if the sample admits one that is NOT a gold fact, rewarding it
    means rewarding a coincidence of the sample."""
    pos = examples.pos(0)
    if len(pos) < 3:
        return []
    if len(pos) > 20000:                     # fitting needs coverage, not volume
        pos = pos[::len(pos) // 20000]
    gold_text = " ".join(gold)
    out = []
    names = list(pos[0].vars)
    for a_i in range(len(names)):
        for b_i in range(a_i + 1, len(names)):
            u, w = names[a_i], names[b_i]
            pts = list({(p.vars[u], p.vars[w]) for p in pos})
            if len(pts) < 3:
                continue
            (x1, y1), (x2, y2) = pts[0], pts[1]
            a, b = y2 - y1, x1 - x2
            if a == 0 and b == 0:
                continue
            c = a * x1 + b * y1
            if all(a * x + b * y == c for x, y in pts):
                if u in gold_text and w in gold_text:
                    continue          # crude gold-implied guard
                out.append(f"{a}*{u} + {b}*{w} == {c}")
            if len(out) >= budget:
                return out
    return out


def mega_conjunction(examples, max_states: int = 400) -> List[str]:
    """The ultimate memorization hack: ONE predicate that is the conjunction of
    the negations of (up to `max_states`) sampled negatives — semantically empty
    yet rejecting every enumerated negative.  Must be neutralized by the
    complexity gate."""
    negs = examples.neg(0)[:max_states]
    if not negs:
        return []
    return [" && ".join(f"!({s.render()})" for s in negs)]


def gold_plus_junk(gold: List[str], examples) -> List[str]:
    """A gold rollout padded with spray: unsound pins and out-of-scope names.
    Same survivors as gold — only the junk penalty can rank it below gold."""
    pos = examples.pos(0)
    junk = ["__no_such_var__ == 0", "1 < 0"]
    if pos:
        v = next(iter(pos[0].vars))
        vals = sorted({p.vars[v] for p in pos})
        junk += [f"{v} == {val}" for val in vals[:6]]
    return list(gold) + junk


def unsound_pin(examples) -> List[str]:
    """Pin one variable to a single sampled value (violated by other positives)."""
    pos = examples.pos(0)
    if len(pos) < 2:
        return []
    v = next(iter(pos[0].vars))
    vals = sorted({p.vars[v] for p in pos})
    if len(vals) < 2:
        return []
    return [f"{v} == {vals[len(vals) // 2]}"]


# ── harness ──────────────────────────────────────────────────────────────────

@dataclass
class ProgramReport:
    program: str
    n_pos: int
    n_neg: int
    rewards: Dict[str, float]
    bases: Dict[str, float]
    survivors: Dict[str, int]
    violations: List[str]


class _MergedExamples:
    """Concatenated view over several example sets — the ADVERSARY'S knowledge
    (it may memorize every scored seed's sample; min-combining must still hold)."""

    def __init__(self, sets):
        self.sets = sets

    def pos(self, loop_idx: int = 0):
        return [p for s in self.sets for p in s.pos(loop_idx)]

    def neg(self, loop_idx: int = 0):
        return [n for s in self.sets for n in s.neg(loop_idx)]


HOLDOUT_SEED = 101       # scoring-only seed the adversary generators never see


def evaluate_program(rel_path: str, spec: Dict[str, object],
                     margin: float = 0.15, eps: float = 0.02,
                     hack_margin: float = 0.15, strict_eps: float = 0.02,
                     min_gold_base: float = 0.80,
                     sampler_kwargs: Optional[dict] = None,
                     n_seeds: int = 2, n_holdout: int = 1) -> ProgramReport:
    source = (INPUT / rel_path).read_text()
    prog = parse_program(source)
    gold: List[str] = list(spec["gold"])
    loose: List[str] = list(spec["loose"])
    box_true = bool(spec.get("box_true", False))
    sampler_kwargs = sampler_kwargs or {}
    base_seed = int(sampler_kwargs.pop("seed", 0)) if "seed" in sampler_kwargs else 0
    example_sets = [ExampleSampler(source, seed=base_seed + k, **sampler_kwargs).sample()
                    for k in range(n_seeds)]
    holdout_sets = [ExampleSampler(source, seed=HOLDOUT_SEED + k, **sampler_kwargs).sample()
                    for k in range(n_holdout)]
    examples = _MergedExamples(example_sets)   # adversary generators see ALL canonical seeds

    families: Dict[str, List[str]] = {
        "gold": gold,
        "loose": loose,
        "trivial": ["1 == 1"],
        "guard_copy": [prog.loop.guard] if prog.loop else [],
        "post_copy": [prog.post] if prog.post else [],
        "unsound": unsound_pin(examples),
        "diseq_farm": diseq_farm(examples),
        "diseq_farm64": diseq_farm(examples, budget=64),
        "diseq_farm512": diseq_farm(examples, budget=512),
        "state_mem": state_memorizer(examples),
        "chunked_conj": chunked_conjunction(examples),
        "ival_farm": interval_farm(examples),
        "ival_wide": interval_farm(examples, max_width=5000),
        "dival_farm": delta_interval_farm(examples),
        "pair_window": pair_window_farm(examples),
        "const_bound": const_bounds(examples),
        "delta_bound": delta_bounds(examples),
        "mod_hack": mod_hacks(examples, gold),
        "affine_hack": affine_hacks(examples, gold),
        "mega_conj": mega_conjunction(examples),
        "combo_hack": (const_bounds(examples) + diseq_farm(examples, budget=48)
                       + mod_hacks(examples, gold)),
        "gold_junk": gold_plus_junk(gold, examples),
    }
    families = {k: v for k, v in families.items() if v}

    calc = RewardCalculator(invariant_filter=PositiveFilter(), sampler_kwargs=sampler_kwargs)
    names = list(families)
    # scored min-across canonical + holdout seeds, exactly as deployed
    batch = calc.compute(source, [{"invariants": families[n]} for n in names],
                         examples=example_sets + holdout_sets)
    rewards = {n: batch.rollouts[i].reward for i, n in enumerate(names)}
    bases = {n: batch.rollouts[i].base for i, n in enumerate(names)}
    survivors = {n: len(batch.rollouts[i].survivors) for i, n in enumerate(names)}

    v: List[str] = []
    g = rewards["gold"]
    if bases["gold"] < min_gold_base:
        v.append(f"gold base too low: {bases['gold']:.2f} < {min_gold_base}")
    if len(survivors) and survivors["gold"] < len(gold):
        v.append(f"gold invariants filtered: {survivors['gold']}/{len(gold)} survive "
                 f"(a TRUE invariant failed the positive check -> sampler mislabels)")
    if rewards.get("loose", 0.0) > g + eps:
        v.append(f"loose beats gold: {rewards['loose']:.3f} > {g:.3f}")
    # memorizers must sit FAR below gold on every program (holdout + the rollout
    # atom budget are the defenses; box_true grants no exemption to memorizers).
    # ival/dival are the INTERVAL memorizers: bounded windows over negative
    # clusters — decade-spread negative placement must starve them everywhere.
    for hack in ("diseq_farm", "diseq_farm64", "diseq_farm512", "state_mem",
                 "chunked_conj", "mod_hack", "ival_farm", "dival_farm", "pair_window"):
        if hack in rewards and rewards[hack] > g - hack_margin:
            v.append(f"MEMORIZER {hack} too close to gold: {rewards[hack]:.3f} > {g - hack_margin:.3f}")
    # a width-unbounded window degenerates into a one-sided bound (weak TRUTH),
    # so ival_wide may approach gold from below but must never beat it
    if "ival_wide" in rewards and rewards["ival_wide"] > g + eps:
        v.append(f"HACK ival_wide beats gold: {rewards['ival_wide']:.3f} > {g:.3f}")
    # overfit boxes must collapse on the holdout seed — unless the box is a true
    # invariant (box_true), where tying gold is legitimate
    for hack in ("const_bound", "delta_bound"):
        limit = g + eps if box_true else g - hack_margin
        if hack in rewards and rewards[hack] > limit:
            v.append(f"BOX {hack} above limit: {rewards[hack]:.3f} > {limit:.3f}")
    # spray riding on a strong clause must rank STRICTLY below the clean set
    if "combo_hack" in rewards and rewards["combo_hack"] > g - strict_eps:
        v.append(f"combo_hack not strictly below gold: {rewards['combo_hack']:.3f} vs {g:.3f}")
    for hack in ("affine_hack",):
        if hack in rewards and rewards[hack] > g + eps:
            v.append(f"HACK {hack} beats gold: {rewards[hack]:.3f} > {g:.3f}")
    # post_copy is junk when the assert is NOT a loop invariant (violated at
    # entry / vacuous); on programs where it IS one (post_is_invariant), copying
    # it deserves reward — then it is a quality family that just must not BEAT gold
    junk_families = ["trivial", "guard_copy", "unsound", "mega_conj"]
    if spec.get("post_is_invariant"):
        if rewards.get("post_copy", 0.0) > g + eps:
            v.append(f"post_copy beats gold: {rewards['post_copy']:.3f} > {g:.3f}")
    else:
        junk_families.append("post_copy")
    for junk in junk_families:
        if junk in rewards and rewards[junk] > g - margin:
            v.append(f"junk {junk} too close to gold: {rewards[junk]:.3f} vs {g:.3f}")
    if "gold_junk" in rewards:
        if rewards["gold_junk"] >= g:
            v.append(f"gold+junk not ranked below gold: {rewards['gold_junk']:.3f} >= {g:.3f}")
        elif rewards["gold_junk"] < g - 0.15:
            v.append(f"junk penalty too harsh: gold_junk {rewards['gold_junk']:.3f} << {g:.3f}")

    return ProgramReport(
        program=rel_path,
        n_pos=batch.n_positives, n_neg=batch.n_negatives,
        rewards=rewards, bases=bases, survivors=survivors, violations=v,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--programs", nargs="*", default=list(SPECS))
    ap.add_argument("--runs", type=int, default=None, help="override sampler n_runs")
    ap.add_argument("--json", default=None, help="write full report JSON here")
    args = ap.parse_args()

    sampler_kwargs = {"n_runs": args.runs} if args.runs else {}
    reports = []
    total_violations = 0
    for rel in args.programs:
        rep = evaluate_program(rel, SPECS[rel], sampler_kwargs=sampler_kwargs)
        reports.append(rep)
        total_violations += len(rep.violations)
        print(f"\n=== {rep.program}   pos={rep.n_pos} neg={rep.n_neg}")
        order = sorted(rep.rewards, key=lambda n: -rep.rewards[n])
        for n in order:
            print(f"  {n:<12} reward={rep.rewards[n]:.3f}  base={rep.bases[n]:.3f}  "
                  f"survivors={rep.survivors[n]}")
        for v in rep.violations:
            print(f"  !! {v}")

    print(f"\n{'=' * 60}\nprograms={len(reports)}  violations={total_violations}")
    if args.json:
        Path(args.json).write_text(json.dumps(
            [rep.__dict__ for rep in reports], indent=2, default=str))
    return 1 if total_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
