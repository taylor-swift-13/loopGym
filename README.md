# LoopGym

*(formerly SAM2INV)*

RL pipeline for training a model to generate **ACSL loop invariants** for C
programs, verified with **Frama-C/WP**. It has three independently usable entry
points that share parsing and state modules; reward and inference also share the
Frama-C adapter:

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

- **Training** uses `prompt/generate_prompt.txt` and calls the **reward** HTTP
  service to score each rollout group.
- **Testing** deploys a trained model to **vLLM** and runs **inference**.
- Both are packaged as Docker images with **frama-c bundled** (no host install).

---

## 1. Sampler — `rl_pipeline/sampler` (the core; the reward's quality depends on it)

**The sampler sees ONLY the loop — never the assert/postcondition.** It executes
the loop and works with *traces* (the group of loop-head variable valuations one
run passes through):

- **positive** = a reachable loop-head valuation (a state of a real trace);
- **negative candidate** = a synthetic trace intended to depart from observed
  loop behavior. Each is stored as its *witness states* (where the synthetic
  history departs from sampled behavior, grouped in `neg_groups`): a one-shot perturbation is a
  singleton ("real prefix + this state"); an over-run continuation is one
  group holding its whole past-the-exit segment.  A rollout **rejects** the
  history iff some invariant is false at any witness — and rewards count in
  trace units, so one long fake continuation is one negative, not twenty-four.

The training signal favors invariants that are sound on sampled positives and
exclude many audited negative candidates. The design is deliberately minimal:
three candidate families, conservative construction guards, and no scoring-side
patch layers. Finite execution is not a proof of global unreachability; the real
Frama-C/WP Houdini stage proves candidate invariants, while the audit below
checks the sampled labels for observed collisions.

Three negative families:

- **relation** — small perturbations (±1, ±2) around bases whose next three
  trace coordinates were printed; candidates colliding with any sampled
  reachable valuation are removed;
- **over-run** — the loop body executed past a **genuine** exit: real dynamics
  (preserves every relation, linear *and* nonlinear, e.g. `z==x*y`), out of the
  reachable range;
- **escape** — large ladder steps kept only when they leave the variable's
  sampled range.

Conservative construction guards:

- states observed **reachable** are never negatives;
- states that could be a **fresh loop entry** (params free, `requires`
  satisfiable) are never negatives — they are reachable under other inputs;
- loops whose guard or body depends on `unknown()` produce positives but no
  synthetic negatives: finite oracle runs under-approximate reachability;
- untracked block-local state, pointer/array state, and function calls in the
  loop body likewise disable synthetic negatives;
- capped deterministic runs disable escapes because their sampled range is
  incomplete.

Supporting mechanics: loops run to their real exit (printing is throttled, not
the execution); inputs satisfy the full multi-clause `requires` incl.
param-vs-param constraints (or sampling fails explicitly); unsigned values keep
their C signedness; far input placement is seed-hashed; ACSL predicates use
C-style truncating `/` and `%`.

The supported sampling model is one braced `while` loop over scalar C `int`
parameters, locals, and file-scope variables. Multiple loops, `for` loops, and
pointer/array parameters fail explicitly instead of returning partial samples.

`unknown()` guards/values are supported (an undefined oracle is given a
nondeterministic body; a per-run `srand` explores varied-length traces).

```python
from rl_pipeline.sampler import ExampleSampler
es = ExampleSampler(source, n_runs=12).sample()  # loop only; no assert used
es.pos(0)      # reachable loop-head valuations
es.neg(0)      # witness states of synthetic negative candidates
es.groups(0)   # witness-index groups, one per candidate trace unit
```
CLI: `python -m rl_pipeline.sampler.example_sampler <file.c>`

**Discrimination harness** — `python -m rl_pipeline.eval.discrimination` scores
rollout families of known quality (gold / loose / trivial / guard / post /
unsound) on benchmark programs and fails on ranking violations — e.g. a weaker
family outscoring gold, or a true invariant getting filtered (sampler
mislabel). Quality discrimination is the sampler's job; production soundness
is delegated to the real Houdini cascade in the reward image.

**Mislabel audit** — `python -m rl_pipeline.eval.mislabel_audit` sweeps the FULL
benchmark suite (366 programs) and fails if any sampled negative shows up as a
positive in larger 24-run samples at seed 0 or seed 9. Pair-level collisions
are hard failures; variable-only overlaps with a different `Pre` are reported
as soft diagnostics.

## 2. Reward — `rl_pipeline/reward`

Scores a **group** of rollouts. For each rollout `A` (in candidate-trace
units — one fake continuation is ONE negative, not twenty-four):

- `base[A]`     = candidates rejected by **Houdini(A alone)** — its own kill rate;
- `marginal[A]` = `rejected(Houdini(∪)) − rejected(Houdini(∪ \ A))` — the effect on
  the group's kill rate of removing `A` (ablation);
- `reward[A]`   = `w_base·base[A] + w_marg·marginal[A]` (default 0.5/0.5) —
  **that is the whole formula**: no junk term, no complexity gates, no
  multi-seed min-combining. Soundness is not a scoring patch: when Frama-C is
  available it comes from `PositiveFilter → Frama-C/WP fixpoint`. Unsound
  clauses are pruned; tautologies may survive but reject no negatives and score
  zero;
- `batch_score` = candidates rejected by `Houdini(∪)`.

```python
from rl_pipeline.reward import RewardCalculator
br = RewardCalculator(w_base=0.5, w_marg=0.5).compute(source, rollouts)
br.to_dict()   # rollout_rewards[], base[], marginal[], batch_score, should_reroll
```

**Refine reward** — `rl_pipeline/reward/refine.py` scores a refine group (n
LLM repairs of one merged pool) as each refinement's marginal contribution:
`delta_base[i] = base(Houdini(pool ∪ refined_i)) − base(Houdini(pool))`.
Δ ≥ 0 by construction; trivial / copied / broken refinements score 0 for free.

**HTTP service** (the training interface — see
[docs/training_integration.md](docs/training_integration.md) for the full
turnkey contract):
```bash
python -m rl_pipeline.reward.service --host 0.0.0.0 --port 8000
# generation reward
curl -s localhost:8000/reward -H 'content-type: application/json' \
     -d '{"program":"<C src>","rollouts":[{"invariants":["z==x*y","x>=0"]}]}'
# refine prompt construction (verdict table + assembled prompt, server-side frama-c)
curl -s localhost:8000/refine_feedback -H 'content-type: application/json' \
     -d '{"program":"<C src>","pool":["x >= y","y >= 0"]}'
# refine reward (Δbase per sampled refinement)
curl -s localhost:8000/refine_reward -H 'content-type: application/json' \
     -d '{"program":"<C src>","pool":["x >= y"],"refinements":[["y >= 0","x >= 1"]]}'
```

Offline JSONL/Parquet groups can be scored with
`python -m rl_pipeline.reward.score_file --input <in> --output <out> --runs 12 --seed 0`.
Parquet additionally requires `pandas` and `pyarrow`.

## 3. Inference — `rl_pipeline/inference` (no reward sampling or scoring)

```python
from rl_pipeline.inference import InferenceFramework, VLLMRolloutProvider
inf = InferenceFramework(source, rollout_provider=VLLMRolloutProvider(model="..."),
                         m_refine=2)   # m_refine=0 (default) = plain pipeline
res = inf.run()   # generate → union → m refine rounds → Houdini → Frama-C verify
res.final_invariants, res.verified, res.refine_rounds
```
- `hide_assert=True` (default, closed-book): the model synthesises invariants from
  the loop, never seeing the assert; `hide_assert=False` shows the full program.
- **m-round refine**: each round runs a cheap WP precheck (syntax + at most two
  WP passes, no fixpoint) over the merged pool, renders a per-invariant verdict table
  (`filters.Verdict` — syntax errors quote frama-c, WP failures say whether
  establishment or preservation broke), and asks the model to repair; refined
  candidates JOIN the pool (originals kept — a later companion invariant can
  rescue an earlier reject).  Early stops: nothing rejected / pool fixpoint /
  round budget.  The final full-Houdini + verify gate means refine can never
  make the accepted output worse than `m_refine=0`.
- CLI: `python -m rl_pipeline.inference --model <hf-or-dir> --inputs '<glob>'
  --m-refine 2`.

## 4. Prompts — `prompt/` (single source of truth)

All static LLM prompt templates live in `prompt/`:
`generate_prompt.txt`, `refine_prompt.txt`, `system_prompt.txt`.  Loaded by
`rl_pipeline/common/prompts.py`; both Docker images COPY the directory.  The
refine prompt is **stateless by design** (program + current pool verdicts only,
no round number, no history) so a policy trained on single-round refine groups
transfers to multi-round inference unchanged.  Training and inference format
the SAME template — edit the file, both sides follow.

## Houdini / Frama-C

The reward filter and inference verify use a **cascade**: lite `PositiveFilter`
(pure Python) → real inductive **Houdini** via Frama-C/WP + z3. With `frama-c` on
`PATH`, `filters.auto_filter()` resolves to `cascade(positive->houdini)`; without
it, the lite filter remains useful for development, but results are approximate
and are not Frama-C certified; production reward training should use the image.

---

## Deployment — `deploy/` (Dockerfiles)

| Image | Build (context = repo root) | Runs |
|-------|-----------------------------|------|
| **reward service** | `docker build -f deploy/Dockerfile.reward -t loopgym-reward .` | `rl_pipeline.reward.service` (gcc + frama-c bundled) |
| **inference** | `docker build -f deploy/Dockerfile.inference -t loopgym-inference .` | `rl_pipeline.inference` (vLLM + frama-c bundled) |

Both bundle frama-c/z3/why3, so a deployment host needs **no local frama-c**.

## Environment (running natively, no Docker)

- `gcc` (the sampler compiles+runs programs), `z3`, and — for real Houdini/verify
  — `frama-c` + `why3` (e.g. an opam switch: `eval $(opam env --switch=frama-c.27.1)`
  then `why3 config detect`).
- Python deps: `pip install -r deploy/requirements-reward.txt` (FastAPI, Uvicorn,
  Pydantic, NumPy); inference additionally needs `vllm`. Parquet I/O optionally
  needs `pandas` and `pyarrow` (both are included in `environment.yml`).
- `src/config.py` reads the LLM key from `OPENAI_API_KEY` (never hardcode it).

## Repository structure

```
rl_pipeline/          sampler / reward / inference / common
prompt/               ALL LLM prompts (generate / refine / system) — edit here
src/                  reused engine deps (config, llm, houdini_pruner,
                      output_verify, syntax_checker)
                      + input/ (benchmark C programs)
deploy/               Dockerfiles + requirements
docs/                 training_integration.md, local_model_setup.md
paper/                current method description and reproducible evaluation
tests/                standard-library regression tests
```

## Verification

```bash
python3 -m unittest discover -s tests -v
ruff check rl_pipeline src tests
python3 -m rl_pipeline.eval.discrimination
python3 -m rl_pipeline.eval.mislabel_audit --jobs 8
```

The two evaluation commands use the benchmark suite and are slower than the
unit tests. Put the Frama-C/Why3 binaries on `PATH` to exercise the real cascade.
