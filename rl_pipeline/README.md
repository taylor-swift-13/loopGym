# rl_pipeline — reward-oriented invariant generation

Three **independent-but-collaborating** components for scoring LLM rollouts that
generate ACSL loop invariants. See `docs/reward_pipeline_plan.md` for the design.

```
 ┌─────────────┐   positives (fast filter)   ┌──────────────────┐
 │  Sampler    │────────────────────────────▶│    Inference     │
 │ (Comp. 1)   │                             │    (Comp. 3)     │
 │ pos + neg   │──negatives──┐               │ sample→filter→   │
 └─────────────┘             │               │ combine→Houdini  │
                             ▼               └──────────────────┘
                     ┌──────────────┐                 ▲
                     │   Reward     │─── batch_score ─┘ (re-roll?)
                     │  (Comp. 2)   │
                     │ HTTP service │
                     └──────────────┘
```

## Core idea

A **sample** is a variable valuation **at the loop entry**.

- **Positive** examples = reachable loop-entry valuations (run the *correct*
  program). Used for **fast filtering** — an invariant violated by a reachable
  state is unsound and dropped.
- **Negative** examples = "must-exclude" valuations. A correct invariant `I`
  must satisfy `I ∧ ¬guard ⟹ post`, so any valuation with `¬guard ∧ ¬post` must
  be excluded. Used to **compute reward** = how many negatives an invariant set
  rejects.

Negatives are proposed by **random + mutation-loop + mutation-trace** (broad
coverage of realistic errors) and then kept only if they pass the spec-derived
acceptance test `¬guard ∧ ¬post ∧ not-reachable`. Mutation only steers proposals
toward realistic near-misses; representativeness comes from the spec filter — so
we never treat "wrong traces from wrong code" as negatives.

## Components

### 1. Sampler — `rl_pipeline/sampler`
```python
from rl_pipeline.sampler import ExampleSampler
es = ExampleSampler(source, n_runs=16, n_random=3000, max_loop_mutants=20).sample()
es.pos(0)  # List[State]   reachable loop-entry valuations
es.neg(0)  # List[State]   must-exclude valuations
```
CLI: `python -m rl_pipeline.sampler.example_sampler <file.c>`

### 2. Reward Calculator + Service — `rl_pipeline/reward`
```python
from rl_pipeline.reward import RewardCalculator
rc = RewardCalculator(w_base=0.5, w_marg=0.5, reroll_threshold=0.6)
br = rc.compute(source, rollouts, examples=es)   # rollout = {"invariants":[...]}
br.to_dict()  # base[], marginal[], rollout_rewards[], batch_score, should_reroll
```
- `base[A]` = negatives rejected by **Houdini(A)** — "hudini 后的分数"
- `marginal[A]` = `rejected(Houdini(∪)) − rejected(Houdini(∪ \ A))` — ablation gain
- `batch_score` = negatives rejected by `Houdini(∪)`; `should_reroll` if below threshold

HTTP service (FastAPI):
```bash
python -m rl_pipeline.reward.service --host 0.0.0.0 --port 8000
curl -X POST localhost:8000/reward -H 'content-type: application/json' \
     -d '{"program":"...C...","rollouts":[{"invariants":["x+y==n"]}]}'
```

### 3. Inference Framework — `rl_pipeline/inference`
```python
from rl_pipeline.inference import InferenceFramework, LLMRolloutProvider
inf = InferenceFramework(source, n_rollouts=4, max_rerolls=1,
                         reward_calculator=rc)   # provider defaults to the LLM
res = inf.run()   # sample → positive-filter → combine → Houdini → verify
res.final_invariants, res.verified, res.batch_score
```
Swap `rollout_provider=MockRolloutProvider([...])` for offline tests.

## Houdini / Frama-C

The authoritative "hudini 后的分数" uses `HoudiniFilter` (reuses
`src/houdini_pruner.py` + `src/output_verify.py`; needs `frama-c` on PATH).
When Frama-C is absent, `auto_filter()` falls back to `PositiveFilter`
("Houdini-lite": drop invariants that are out-of-scope or unsound on positives),
so every component remains runnable in a Frama-C-less environment.

## Tests
```bash
python -m rl_pipeline.tests.test_pipeline      # no frama-c / no LLM needed
```
