# SAM2INV

RL pipeline for training a model to generate **ACSL loop invariants** for C
programs, verified with **Frama-C/WP**. Three **independent** components (they
only share this repo):

```
   ┌────────────┐        rollouts (a group of        ┌──────────────────┐
   │  Sampler   │         candidate invariant sets)  │    Inference     │
   │  (traces)  │                                    │ generate→union→  │
   └─────┬──────┘                                    │ Houdini→verify   │
         │ pos + neg traces                          └──────────────────┘
         ▼                                            (testing: vLLM + frama-c)
   ┌──────────────┐   per-rollout reward
   │    Reward    │   = w_base·base + w_marg·marginal
   │ HTTP service │   (training: called by the RL trainer, e.g. verl)
   └──────────────┘
```

- **Training** calls only the **reward** HTTP service (scores a group of rollouts).
- **Testing** deploys a trained model to **vLLM** and runs **inference**.
- Both are packaged as Docker images with **frama-c bundled** (no host install).

---

## 1. Sampler — `rl_pipeline/sampler` (the core; the reward's quality depends on it)

**The sampler sees ONLY the loop — never the assert/postcondition.** It executes
the loop and works with *traces* (the group of loop-head variable valuations one
run passes through):

- **positive** = a reachable loop-head valuation (a state of a real trace);
- **negative** = an **impossible trace** — a history the loop cannot produce.
  Each is stored as its *witness states* (where the fake history departs from
  anything real, grouped in `neg_groups`): a one-shot perturbation is a
  singleton ("real prefix + this state"); an over-run continuation is one
  group holding its whole past-the-exit segment.  A rollout **rejects** the
  history iff some invariant is false at any witness — and rewards count in
  trace units, so one long fake continuation is one negative, not twenty-four.

The strongest invariant is the **tightest characterization of the reachable set**:
sound on every positive, ruling out as many impossible histories as possible.
Negatives come in two *balanced* dimensions, both truthful by construction
(no program-type special-casing):

- **relation** — small single-axis / joint pairwise steps (±1..3) off the
  reachable manifold, taken only from bases whose local trace window is densely
  sampled, so a surviving perturbation is genuinely off-manifold and not an
  unsampled trace neighbor;
- **bound** — the "law holds but range violated" dimension:
  *over-run* (the loop body executed past a **genuine** exit, continuing the real
  dynamics — preserves every relation, linear *and* nonlinear, e.g. `z==x*y`)
  plus *box-escape* (large ladder steps ±5..89 kept only when they leave the
  variable's sampled range).

Anti-reward-hack guards (verified by `rl_pipeline/eval/discrimination.py`):

- loops run to their **real exit** (printing is throttled, not the execution), so
  sampled ranges are true ranges and overfit constant bounds can't outscore the
  true invariant;
- inputs must satisfy the **full `requires`** (including param-vs-param
  constraints) — out-of-precondition traces would poison the positive filter;
- perturbed states that could be a **fresh loop entry** (params free, literal
  locals at inits, requires satisfiable) are never labeled negative — they are
  reachable under different inputs;
- runs hitting the divergence cap disable box-escape; `while(unknown())` guards
  disable the whole bound dimension (no range is sound there);
- `unknown()` INSIDE the body means the state graph branches: runs are doubled
  for branch coverage, and perturbations that merely RECOMBINE observed
  coordinate values are dropped (they may sit on an unobserved branch) — only
  candidates with a novel coordinate value survive;
- branch-dependent (taint-analyzed, incl. control dependence and braceless
  arms) variables are never perturbed directly — but four CONSERVATION rescues
  still give them sound negatives: rigid pairs (`cw·v − cv·w` constant when v,w
  are co-assigned constant steps at identical sites), gcd lattices
  (`v ≡ v_entry mod g` when every step of v is a multiple of g, e.g.
  `if(unknown()) i+=6; else i+=3;` → i mod 3), monotone floors/ceilings
  (`v >= min(entry, literals)` when every assignment is a same-sign const step
  or an int literal; literal-only state tags get both directions), and
  guard-derived bounds (`v <= X` when the single unit up-step sits under a
  `v != X` / `v < X` conjunct with X frozen — unit steps cannot skip the
  block; entry/reset literals are runtime-checked per state).  Rescue deltas
  are seed-hashed so the clustered bound±d values cannot be farm-memorized
  across seeds;
- multi-clause `requires` are conjoined, and param-vs-param constraints are
  enforced by evaluation, so out-of-precondition inputs never poison positives;
- ACSL predicates evaluate under C integer semantics (truncating `/` and `%`),
  matching the executed states — honest division invariants are never filtered
  by a floor-semantics artifact;
- input tuples are drawn in two phases (diverse stripe, then a mixed-radix grid
  over tier combinations) so param-vs-param `requires` like `z == k` are
  actually satisfied instead of falling back to unchecked inputs;
- **seed-hashed far probes**: each sample includes a few large-magnitude input
  tuples whose values are hashed from the seed (cube-overflow-safe, honoring
  explicit `requires` bounds) — every seed's input envelope differs, so a
  sample-extreme box (`lo <= v <= hi` at observed extremes) fitted on the
  training seeds is unsound on a holdout seed's positives and gets filtered,
  while a true symbolic bound (`x <= n`) is indifferent;
- **seed-hashed tier jitter** (non-edge tiers only; equal-tuples preserved for
  `z == k`-style requires) decorrelates sampled VALUES across seeds, so
  pointwise `v != k` value memorization also fails to transfer to the holdout;
- relation bases are chosen among DENSE positions (full forward trace window
  sampled), so long throttled traces still yield a negative pool far too large
  for clause-budgeted memorizers;
- the many distinct box-escape values per axis make pointwise `v != k` farms
  uneconomical, and relation/bound balance keeps either dimension from
  dominating the reward.

`unknown()` guards/values are supported (an undefined oracle is given a
nondeterministic body; a per-run `srand` explores varied-length traces).

```python
from rl_pipeline.sampler import ExampleSampler
es = ExampleSampler(source, n_runs=12).sample()  # loop only; no assert used
es.pos(0)   # reachable loop-head valuations
es.neg(0)      # witness states of impossible traces
es.groups(0)   # witness-index groups, one per impossible trace
```
CLI: `python -m rl_pipeline.sampler.example_sampler <file.c>`

**Discrimination harness** — `python -m rl_pipeline.eval.discrimination` scores
rollout families of known quality (gold/loose/trivial/unsound + adversarial
disequality farms at 16/64/512-clause budgets, whole-state and chunked
mega-conjunction memorizers, constant-bound and delta-space (`v − \at(v,Pre)`)
overfit boxes, modulus and affine sample-coincidence hacks, a combo attack, and
gold-plus-spray) on 9 benchmark programs.  Threat model: the adversary
generators see the union of every CANONICAL seed's sample; scoring — as
deployed — min-combines the canonical seeds plus a HOLDOUT seed the adversary
never saw.  Fails if a memorizer or overfit box gets within 0.10 of gold
(sample-extreme boxes are exempt only on `box_true` programs, where the
reachable box is input-independent and hence a true invariant), if spray isn't
ranked strictly below the clean set, if junk approaches gold, or if a true
invariant gets filtered (sampler mislabel).

**Mislabel audit** — `python -m rl_pipeline.eval.mislabel_audit` sweeps the FULL
benchmark suite (366 programs) and fails if any sampled negative shows up as a
positive of a larger same-seed sample (a mislabeled negative punishes exactly
the true invariants — the root of every reward hack).

## 2. Reward — `rl_pipeline/reward`

Scores a **group** of rollouts. For each rollout `A`:

- `base[A]`     = negatives rejected by **Houdini(A alone)** — its own kill rate;
- `marginal[A]` = `rejected(Houdini(∪)) − rejected(Houdini(∪ \ A))` — the effect on
  the group's kill rate of removing `A` (ablation);
- `junk[A]`     = fraction of `A`'s emitted invariants that are NOT useful:
  killed by the filter (unsound / out-of-scope / memorization-sized) **or**
  surviving without a UNIQUE rejection — spray that only shadows stronger
  clauses in the same rollout costs the same as filtered garbage, so a clean
  set ranks strictly above the same set padded with riders;
- `reward[A]`   = `max(0, w_base·base[A] + w_marg·marginal[A] − w_junk·junk[A])`
  with **hyperparameters** `w_base` / `w_marg` / `w_junk` (0.5/0.5/0.05);
- `batch_score` = negatives rejected by `Houdini(∪)`.

Anti-hack, three independent layers:

- **per-predicate complexity gate** (>160 chars or >12 atoms dropped) — kills
  the single mega-conjunction of negated sampled states;
- **rollout atom budget** (32 comparison atoms across the whole set; scoring
  uses the emission-order prefix) — kills the SPLIT mega-conjunction: hundreds
  of small gate-compliant clauses (`v != k`, `!(x==a && y==b)`) memorizing the
  negative pool one state at a time.  Honest sets (~3-6 clauses × 1-4 atoms)
  fit with generous headroom;
- **multi-seed + holdout scoring**: rewards are min-combined over `n_seeds`
  (default 2) canonical example sets PLUS `n_holdout` (default 1) freshly-seeded
  ones (random seed per call unless pinned).  A policy can memorize every
  canonical seed it trains against; it cannot memorize a sample it has never
  seen — and thanks to far probes / tier jitter, the holdout's values and
  extremes genuinely differ, so overfit boxes get filtered and memorized
  farms miss.  True invariants are indifferent to the seed.

```python
from rl_pipeline.reward import RewardCalculator
br = RewardCalculator(w_base=0.5, w_marg=0.5, w_junk=0.05,
                      n_seeds=2, n_holdout=1).compute(source, rollouts)
br.to_dict()   # rollout_rewards[], base[], marginal[], batch_score, seeds, should_reroll
```

**HTTP service** (the training interface):
```bash
python -m rl_pipeline.reward.service --host 0.0.0.0 --port 8000
curl -s localhost:8000/reward -H 'content-type: application/json' \
     -d '{"program":"<C src>","rollouts":[{"invariants":["z==x*y","x>=0"]}]}'
```

## 3. Inference — `rl_pipeline/inference` (independent of the reward; does NOT sample)

```python
from rl_pipeline.inference import InferenceFramework, VLLMRolloutProvider
inf = InferenceFramework(source, rollout_provider=VLLMRolloutProvider(model="..."))
res = inf.run()   # generate → union → Houdini → Frama-C verify
res.final_invariants, res.verified
```
- `hide_assert=True` (default, closed-book): the model synthesises invariants from
  the loop, never seeing the assert; `hide_assert=False` shows the full program.
- CLI: `python -m rl_pipeline.inference --model <hf-or-dir> --inputs '<glob>'`.

## Houdini / Frama-C

The reward filter and inference verify use a **cascade**: lite `PositiveFilter`
(pure Python) → real inductive **Houdini** via Frama-C/WP + z3. With `frama-c` on
`PATH`, `filters.auto_filter()` resolves to `cascade(positive->houdini)`; without
it, everything still runs on the lite filter.

---

## Deployment — `deploy/` (Dockerfiles)

| Image | Build (context = repo root) | Runs |
|-------|-----------------------------|------|
| **reward service** | `docker build -f deploy/Dockerfile.reward -t sam2inv-reward .` | `rl_pipeline.reward.service` (gcc + frama-c bundled) |
| **inference** | `docker build -f deploy/Dockerfile.inference -t sam2inv-inference .` | `rl_pipeline.inference` (vLLM + frama-c bundled) |

Both bundle frama-c/z3/why3, so a deployment host needs **no local frama-c**.

## Environment (running natively, no Docker)

- `gcc` (the sampler compiles+runs programs), `z3`, and — for real Houdini/verify
  — `frama-c` + `why3` (e.g. an opam switch: `eval $(opam env --switch=frama-c.27.1)`
  then `why3 config detect`).
- Python deps: `pip install -r deploy/requirements-reward.txt` (fastapi/uvicorn/
  pydantic/numpy); inference additionally needs `vllm`.
- `src/config.py` reads the LLM key from `OPENAI_API_KEY` (never hardcode it).

## Repository structure

```
rl_pipeline/          sampler / reward / inference / common
src/                  reused engine deps (config, llm, houdini_pruner,
                      output_verify, syntax_checker, unified_filter, run_dirs)
                      + prompts/system_prompt.txt + input/ (benchmark C programs)
deploy/               Dockerfiles + requirements
docs/                 reward_pipeline_plan.md
```
