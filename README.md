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
- **negative** = a loop-head valuation **no trace can produce** (an *unreachable*
  state), decided purely by execution.

The strongest invariant is the **tightest characterization of the reachable set**:
sound on every positive, rejecting as many unreachable states as possible. Hard
negatives sit just off the reachable frontier and come from two general (no
program-type special-casing) mechanisms:

- **frontier** — perturb each reachable state's modified variables off the
  reachable set (single-axis leaves any manifold; joint pairwise leaves the
  reachable segment of a linear one);
- **over-run** — run the loop **body past the exit** (`_OVERRUN_STEPS`), continuing
  the real dynamics so every relation is preserved (linear *and* nonlinear, e.g.
  `z==x*y`) while going out of bounds — the hard "law holds but bound violated"
  negatives.

`unknown()` guards/values are supported (an undefined oracle is given a
nondeterministic body; a per-run `srand` explores varied-length traces).

```python
from rl_pipeline.sampler import ExampleSampler
es = ExampleSampler(source, n_runs=8).sample()   # loop only; no assert used
es.pos(0)   # reachable loop-head valuations
es.neg(0)   # unreachable loop-head valuations
```
CLI: `python -m rl_pipeline.sampler.example_sampler <file.c>`

## 2. Reward — `rl_pipeline/reward`

Scores a **group** of rollouts. For each rollout `A`:

- `base[A]`     = negatives rejected by **Houdini(A alone)** — its own kill rate;
- `marginal[A]` = `rejected(Houdini(∪)) − rejected(Houdini(∪ \ A))` — the effect on
  the group's kill rate of removing `A` (ablation);
- `reward[A]`   = `w_base·base[A] + w_marg·marginal[A]` — the two joined by the
  **hyperparameters** `w_base` / `w_marg`;
- `batch_score` = negatives rejected by `Houdini(∪)`.

```python
from rl_pipeline.reward import RewardCalculator
br = RewardCalculator(w_base=0.5, w_marg=0.5).compute(source, rollouts)
br.to_dict()   # rollout_rewards[], base[], marginal[], batch_score, should_reroll
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
