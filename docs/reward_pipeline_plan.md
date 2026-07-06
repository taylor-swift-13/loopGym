# Reward Pipeline Refactor — Design & Plan

## Context

The current pipeline (`loop_factory/batch_pipeline.py` + `src/inv_generator.py`) mixes many
concerns into one giant `generate_all` flow: LLM candidate generation, a syntax gate, a
trace "sampling gate" (disabled: `config.USE_TRACES = False`), invariant merging, Houdini
pruning, Frama-C verification, DPO chosen/rejected mining, and several ad-hoc DPO
augmentation heuristics (`_aug_error_subset_reject`, `_aug_mixed_invariant_reject`,
`_sample_subset_code`). There is **no real reward signal** — "score" is just binary Frama-C
success and an acceptance rate.

We are refactoring toward an **RL-style reward** for invariant generation, decomposed into
**three independent-but-collaborating components**:

1. **Example Sampler** — produces representative **positive** (reachable) and **negative**
   ("must-exclude") example states for a program.
2. **Reward Calculator (HTTP service)** — given a *group of rollouts* + the example sets,
   returns per-rollout reward, base score, marginal gain, and an overall batch score.
3. **Inference Framework** — the generation loop: *sample rollouts → positive-filter →
   combine → Houdini → verify*.

### Why the original "negatives from wrong traces" idea was rejected

Generating dynamic traces by running *arbitrarily wrong code* and calling the raw traces
"negatives" is **not representative** — a wrong program's behavior is uncontrolled. The fix:
use mutation only to *propose* candidate bad states, then **filter** to keep only states that
are genuinely negative w.r.t. the spec (satisfy `¬guard ∧ ¬post`) and are **not** in the true
reachable/positive set. Negatives are thus grounded in the specification, not in buggy runs.

---

## Component 1 — Example Sampler  (`rl_pipeline/sampler/`)

**Interface**
```python
ExampleSampler(program_source: str).sample() -> ExampleSet
# ExampleSet.positives[loop_idx]: List[State]   # reachable loop-ENTRY valuations
# ExampleSet.negatives[loop_idx]: List[State]   # must-exclude loop-ENTRY valuations
# State = Dict[str, int]  (variable -> value at loop entry), plus pre-values for \at(v,Pre)
```

**A "sample" is a variable valuation at the loop entry (loop head).** Both positives and
negatives are loop-entry valuations over the same variable set. Reward is judged by whether an
invariant holds / is violated at these loop-entry valuations.

Design goals from the user: **cover real errors as broadly as possible** — the negative
generators must (a) use a *broad, realistic* mutation-operator set that mirrors the mistakes
which produce plausible-but-wrong invariants, and (b) sample the state space *widely* (varied
magnitudes, signs, and edge values 0/±1) so negatives densely surround the reachable region.

**Positives** (for *fast filtering*): reachable loop-head states from executing the **correct,
unmodified** program with sampled inputs. Reuse `DynamicExecutorConfigurable.execute_c_code`
(gcc compile+run, timeout/stdout caps) and `simple.parse_samples`; loop-head state printing via
lightweight printf instrumentation (self-contained, modeled on `loop_sampler.dynamic_loop_file`).

**Negatives** (for *reward*) — three generators, then a **representativeness filter**:
- **random**: sample variable assignments over domains (`_get_constraints`-style ranges), keep
  those satisfying `¬(loop guard) ∧ ¬(assert/ensures post)`.
- **mutation-loop**: apply a *broad, realistic* operator set to the loop body/guard, modeling
  real bug patterns — off-by-one on updates, wrong update direction (`+`↔`-`), swapped
  operators (`*`↔`+`), constant perturbation, comparison flips (`<`↔`<=`, `>`↔`>=`), swapped
  variables, dropped/duplicated updates, wrong guard bound — run the *mutated* program, collect
  its loop-entry valuations.
- **mutation-trace**: perturb real positive valuations (±k for several k, sign flip, scale,
  single-variable vs joint perturbation) — no execution; wide coverage.
- **filter**: drop any candidate that (a) equals a real positive/reachable state, or (b) does
  not violate the property. Only survivors become negatives → representative by construction.

**Files**: `state.py` (State repr, safe predicate eval), `program.py` (parse signature/params/
requires/loop guard/assert — reuse `loop_analysis.extract_first_loop_condition`), `mutators.py`
(loop + trace mutation ops), `example_sampler.py` (orchestrator + CLI).

## Component 2 — Reward Calculator + Service  (`rl_pipeline/reward/`)

**Interface**
```python
RewardCalculator.compute(program_source, rollouts, examples=None) -> BatchReward
# rollout = {"invariants": [str, ...]}  (or annotated code)
# base[A]     = negatives rejected by Houdini(A alone)          -> "hudini 后的分数"
# marginal[A] = rejected(Houdini(U)) - rejected(Houdini(U\A))   -> ablation gain (增益)
# reward[A]   = w_base*base[A] + w_marg*marginal[A]
# batch_score = rejected(Houdini(union)) / |negatives|          -> batch performance
# should_reroll = batch_score < threshold
```
A set *rejects* a negative state `s` iff some invariant is False at `s` (pure-Python eval on
states — cheap). The only Frama-C cost is the **Houdini** step per subset (reuse
`HoudiniPruner.hudini` + `OutputVerifier`); ablation is `G+1` Houdini runs for `G` rollouts.

**Service**: `service.py` = FastAPI app, `POST /reward` (body `{program, rollouts}` → the
`BatchReward` JSON), callable from any RL trainer (verl/OpenRLHF-style). If `examples` omitted,
the service invokes the Sampler itself (components collaborate).

## Component 3 — Inference Framework  (`rl_pipeline/inference/`)

**Interface**
```python
InferenceFramework(program_source).run(n_rollouts=k) -> Result
# 1. sample rollouts   (LLM via src/llm.Chatbot)
# 2. positive-filter    (drop invariants violated by any positive state — Sampler positives)
# 3. combine (union)    across surviving rollouts
# 4. Houdini prune      (HoudiniPruner) + Frama-C verify (OutputVerifier)
```
Reuses the Sampler (positives) and the Houdini/verifier core; optionally queries the Reward
service to score/re-roll.

---

## Redundant logic to delete (with user's OK)

- `batch_pipeline.py`: `_sample_subset_code`, `_build_subset_invariant_code`,
  `_aug_error_subset_reject`, `_aug_mixed_invariant_reject`, and the `dpo_aug` emission path.
- `inv_generator.py`: the `sampling_gate` filter (`_filter_invariants_by_sampling`,
  `_check_invariant_at_state`) is superseded by the Sampler's positive-filter; the scattered
  per-gate `dpo_reject` bookkeeping is replaced by the Reward Calculator's per-rollout scoring.
- `config.USE_TRACES` dead path.
  (Kept & reused: `HoudiniPruner`, `OutputVerifier`, `llm.Chatbot`, `DynamicExecutorConfigurable`,
  `simple.parse_samples`, `loop_analysis`.)

## Package layout
```
rl_pipeline/
  common/        state.py, program.py, predicates.py   (shared)
  sampler/       example_sampler.py, mutators.py
  reward/        reward_calculator.py, service.py
  inference/     inference.py
  tests/         smoke tests on src/input/linear/100, NLA_lipus/24
```

## Verification
- Sampler: run on `linear/foo100` (`while(x>0){y++;x--;} assert y==n`) and `NLA/main24`
  (`assert z==0`); assert positives satisfy the true invariant and negatives satisfy `¬guard∧¬post`
  and are disjoint from positives.
- Reward: feed a known-good rollout (true invariants) vs a weak rollout; good must score higher,
  base/marginal/batch sane; `curl POST /reward` returns valid JSON.
- Inference: end-to-end on `NLA/main24`, confirm it recovers a verifying invariant set (Frama-C).

---

## Implementation status (built)

Delivered under `rl_pipeline/` (see `rl_pipeline/README.md`):

| Component | Files | Status |
|-----------|-------|--------|
| Shared core | `common/{program,state,paths}.py` | ✅ parser + safe ACSL predicate evaluator |
| 1. Sampler | `sampler/{cexec,mutators,example_sampler}.py` | ✅ positives (gcc run) + negatives (random+mutation-loop+mutation-trace, spec-filtered) |
| 2. Reward | `reward/{annotate,filters,reward_calculator,service}.py` | ✅ base/marginal/batch + FastAPI `/reward` `/sample` `/health` |
| 3. Inference | `inference/inference.py` | ✅ sample→pos-filter→combine→Houdini→verify, swappable provider (LLM/mock), re-roll loop |
| Tests | `tests/test_pipeline.py` | ✅ 4/4 pass (no frama-c / no LLM) |

Verified: sampler positives satisfy the reference invariants; negatives satisfy `¬guard∧¬post`
and are disjoint from positives; the true invariant rejects 350/350 (foo100) and 251/251 (main24)
negatives; reward ranks complete > partial > weak > unsound(=0); the FastAPI service answers over
real HTTP. **Frama-C is not installed in the dev env**, so tests exercise the `PositiveFilter`
Houdini-lite fallback; on the production env `auto_filter()` will pick the real `HoudiniFilter`.

### Also delivered (later directives)
- **JSONL/Parquet I/O** for the reward chain: `reward/io.py` (grouped + flat layouts, auto-detect
  by extension) and `reward/score_file.py` CLI (`--input rollouts.{jsonl,parquet} --output
  rewards.{jsonl,parquet}`); per-rollout reward rows for RL trainers. String rollouts accept raw
  LLM text (`loop invariant …;`) or JSON. pyarrow installed.
- **Speed: Houdini-lite → real Houdini cascade** (`reward/filters.CascadeFilter`) + per-batch
  **memoization** of filter/verify results (ablation subsets ∪\A share sets → Frama-C runs once).
- **Robust "only-strongest-rejects-all"**: `_exit_boundary_negatives` guarantees witness negatives
  adjacent to every reachable exit state, so each necessary conjunct is witnessed (DROP-margin for
  the primary invariant grew 3→187 on foo100). Property holds: only a sufficient+inductive
  invariant rejects all negatives; weaker ones strictly fewer.
- **Old chain DEPRECATED**: `batch_pipeline.py` (module banner + runtime warning), the
  `sampling_gate` methods in `inv_generator.py`, all pointing to `rl_pipeline`.

### Old chain DELETED (2026-07-05)
The entire DPO synthesis chain was removed (git rm, staged — recoverable, not committed) and
replaced by `rl_pipeline/`:
- Deleted: `loop_factory/{batch_pipeline,reverse_cot,generate_distill,generate_dpo_spec,
  test_cot_quality,test_reverse_cot_empty}.py`, `loop_factory/scripts/{evaluate_structural_diversity,
  test_reverse_cot_once}.py`, and 8 `grouped_batch_*.sh` launchers.
- Replacement entry points: `python -m rl_pipeline.batch` (inference over a dir/glob of programs)
  and `python -m rl_pipeline.reward.score_file` (batch reward over JSONL/Parquet).
- Kept: `loop_factory/loop_factory.py` (program generator), `loop_factory/dedup_curated.py`,
  `src/inv_generator.py` (engine, now orphaned; `sampling_gate` deprecated), and
  `src/{houdini_pruner,output_verify,llm}.py` (reused by rl_pipeline).

### Remaining / follow-up
- Optionally delete the orphaned `src/inv_generator.py` engine + its deprecated `sampling_gate`
  if it is confirmed unused elsewhere.
- Real Frama-C run of `HoudiniFilter`/cascade end-to-end on the production env.
- Negatives for posts referencing `\at(v,Pre)` of modified vars; multi-loop negatives;
  `unknown()` nondeterministic loops.
- Extend negatives to posts referencing `\at(v,Pre)` of *modified* vars (sample pre-values too).
- Multi-loop negatives (currently loop 0 uses the program post; positives cover all loops).
- Real Frama-C run of `HoudiniFilter` end-to-end on the production env.
- **Coverage gaps** found in the 12-program sweep (no crashes; graceful `neg=0`):
  - Large guard bounds / high iteration counts (e.g. `linear/1`, `y<100000`): the
    `_ITER_CAP` truncates before the true `¬guard` exit. **Addressed** by
    `_boundary_candidates` — sampling relative to guard/post constants (values
    around/beyond each literal), which now recovers negatives for these. Could still
    raise the cap for non-divergent loops to also get boundary *positives*.
  - Nondeterministic `unknown()` loops (~40% of `linear/`): currently `unknown()` is
    stubbed as `rand()%2`. Model it as a free nondeterministic input for representative
    reachable states.
