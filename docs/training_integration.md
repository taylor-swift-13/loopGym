# Training Integration Guide — 训练侧开箱即用

The RL trainer (verl / OpenRLHF / custom GRPO) calls the reward HTTP service for
sampling-backed scores and refine feedback. It does not import `rl_pipeline` or
need a local Frama-C installation. The trainer still owns **generation prompt
construction**: load `prompt/generate_prompt.txt`, format its `{program}` field
with the target-free program shown to the policy, and use
`prompt/system_prompt.txt` as the system message where the chat stack supports
one. The service assembles only the refine prompt returned by
`POST /refine_feedback`.

Keep two program forms in the trainer or dataset:

- `visible_program`: the closed-book function used in the generation prompt,
  with `assert`/`ensures` hidden;
- `full_program`: the original function sent to reward endpoints, including its
  contract and assertion.

```
trainer (GPU box)                         reward service (Docker, CPU box)
─────────────────                         ─────────────────────────────────
format generate_prompt + sample rollouts
                                  ──────► POST /reward          → rewards[]
merge pool                       ──────► POST /refine_feedback → refine prompt
sample refine rollouts           ──────► POST /refine_reward   → delta_base[]
```

---

## 1. Start the service

**Docker (recommended — frama-c/z3/why3 bundled, nothing to install):**

```bash
docker build -f deploy/Dockerfile.reward -t loopgym-reward .   # context = repo root
docker run -p 8000:8000 loopgym-reward
curl -s localhost:8000/health
# {"status":"ok","filter_mode":"cascade(positive->houdini)","cached_programs":0}
```

`filter_mode` MUST read `cascade(positive->houdini)`. If it says `positive`,
frama-c is missing and every reward is computed without the real Houdini
cascade — abort and fix the image/PATH.

**Native:** install the Python service dependencies, activate an environment in
which `gcc`, `frama-c`, `why3`, and `z3` are on `PATH`, then start the service
from the repository root:

```bash
python3 -m pip install -r deploy/requirements-reward.txt
gcc --version
why3 config detect
python3 -m rl_pipeline.reward.service --host 0.0.0.0 --port 8000
```

## 2. Endpoints

### 2.1 `POST /reward` — score one generation group

One call per prompt-group (the n rollouts sampled from one program's prompt).

```jsonc
// request
{
  "program":  "<full C source, with requires/loop/assert>",   // REQUIRED
  "rollouts": [
    {"invariants": ["x >= y", "y >= 0"]},   // or {"code": "<annotated C>"}
    "<raw LLM text — loop invariant lines are extracted>"
  ],
  "w_base": 0.5, "w_marg": 0.5,             // optional, reward weights
  "sampler": {"n_runs": 12, "seed": 0}      // optional; keep fixed per sweep
}
// response (order-aligned with rollouts)
{
  "rollout_rewards": [0.41, 0.17],          // ← the GRPO group rewards
  "base": [...], "marginal": [...],
  "batch_score": 0.83, "should_reroll": false,
  "n_negatives": 118, "filter_mode": "cascade(positive->houdini)",
  "rollouts": [{"index":0,"reward":...,"survivors":[...],"rejected":...}, ...]
}
```

Semantics: `base[A]` = fraction of sampled negative-candidate traces rejected by the
Houdini survivors of A alone; `marginal[A]` = A's irreplaceable contribution to
the group union (ablation); `reward = w_base·base + w_marg·marginal`. Negatives
derive from the program's loop only (never the assert), so scoring stays
closed-book. The example set is sampled once per (program, sampler-config) and
cached in-process.

### 2.2 `POST /refine_feedback` — build a refine group's prompt

Call after scoring a generation group: merge that group's rollouts into `pool`
and let the service verdict it (syntax scrub + at most two WP rounds, no
fixpoint). The first WP round checks the full pool. A second round runs only
when establishment failures were removed, so preservation is not masked by
inconsistent hypotheses.

```jsonc
// request
{ "program": "<C source>", "pool": ["x >= y", "x >= == 1", "y >= 0"] }
// response
{
  "pool": ["x >= y", "x >= == 1", "y >= 0"],   // normalized+deduped — SAVE THIS
  "n_rejected": 2,                              // 0 → nothing to refine, skip group
  "verdicts": [
    {"invariant":"x >= == 1","kept":false,"stage":"syntax",
     "reason":"frama-c: unexpected token '=='"},
    {"invariant":"y >= 0","kept":true,"stage":"wp","reason":"passing so far"},
    {"invariant":"x >= y","kept":false,"stage":"wp",
     "reason":"fails preservation: one loop iteration does not maintain it (even assuming the whole pool) — adjust it to the loop's step, or add a companion invariant that supports it"}
  ],
  "feedback": "<the rendered verdict table>",
  "prompt": "<the COMPLETE refine prompt — feed this string to the policy as-is>"
}
```

This endpoint requires the real Houdini stage. If Frama-C is unavailable,
`filters.auto_filter()` has no WP precheck stage and the endpoint responds with
HTTP 503:

```json
{"detail":"no WP precheck stage (frama-c unavailable)"}
```

Treat this as a deployment error for refine training; do not retry the same
request until the service environment is fixed.

Every rejected invariant carries its specific WHY: `syntax` quotes frama-c's
actual parse error, `wp` distinguishes *fails establishment* (false at loop
entry) from *fails preservation* (needs a companion invariant / bound fix),
`scope` lists the unknown identifiers. Reasons are target-free (never mention
the assert), so the prompt stays closed-book. The prompt text itself lives in
`prompt/refine_prompt.txt` — the same file inference uses, so training and
deployment distributions match by construction.

### 2.3 `POST /refine_reward` — score one refine group

```jsonc
// request — pool MUST be the "pool" echoed by /refine_feedback
{
  "program": "<C source>",
  "pool": ["x >= y", "x >= == 1", "y >= 0"],
  "refinements": [ ["y >= 0", "x >= 1"], [], ... ]   // one list per sampled response
}
// response (order-aligned with refinements)
{
  "delta_base": [0.0090, 0.0],   // ← the GRPO group rewards
  "base_before": 0.0, "base_after": [0.0090, 0.0], "pool_size": 3
}
```

`delta_base[i] = base(Houdini(pool ∪ refined_i)) − base(Houdini(pool))` — the
refinement's marginal contribution to the merged pool. Properties the trainer
can rely on:

- **Δ ≥ 0 always** (the pool only grows; originals are kept). An all-zero group
  has zero variance → no gradient; expected early in training, not an error.
- **Anti-hack for free**: trivially-true invariants survive Houdini but reject
  no new negatives (Δ≈0); copying a pool member changes nothing (Δ=0); broken
  output is pruned (Δ=0).
- Under GRPO group normalization the shared `base_before` is absorbed, so Δ and
  the absolute score are gradient-equivalent; the Δ form is for monitoring
  ("how much discrimination each refinement recovered").
- `base_before` is shared across the group. Identical invariant sets are
  memoized, but trainers should still budget for multiple Frama-C runs per
  refine group.

### 2.4 `POST /sample` (debug) and `GET /health`

`/sample {program}` shows the sampled positives/negatives; `/health` reports
the filter mode and cache size.

## 3. The mixed GRPO recipe (生成 + refine 混训)

```
each RL step:
  1. generation groups: trainer loads prompt/generate_prompt.txt,
       formats {program}=visible_program, and samples n rollouts
       → POST /reward with full_program → rewards       (single-turn)
  2. harvest: for each generation group,
       pool = union of its n rollouts
       → POST /refine_feedback
       → if n_rejected == 0: skip; else keep (prompt, pool)
  3. refine groups: for each kept prompt, sample n responses from the SAME
       policy → POST /refine_reward → delta_base       (single-turn again)
  4. mix both group types into one GRPO batch; update.
```

Design rules (的重要性顺序):

1. **The refine prompt is stateless** — program + current pool verdicts only,
   no round number, no history. This is what makes "train one round, infer
   many rounds" valid: at inference `InferenceFramework(m_refine=k)` iterates
   the same prompt format k times.
2. **Cap refine groups at ~20–30% of the batch.** Early training fails a lot;
   without a cap refine prompts flood the batch and the headline metric
   (single-shot closed-book accuracy) starves.
3. **Do NOT replace failed generation rollouts with refined ones.** Generation
   groups keep their own (low) rewards — that negative signal is what trains
   first-shot quality. Refine is a separate task with separate prompts
   (this is the SCoRe-collapse avoidance, structurally).
4. Refine prompts are harvested from the previous step's policy — one step
   stale, which is standard and fine. No static failure pool to maintain.

## 4. Inference-side m-round refine (deployment / eval)

```python
from rl_pipeline.inference import InferenceFramework
inf = InferenceFramework(source, m_refine=2)   # m_refine=0 → plain pipeline
res = inf.run()
res.final_invariants, res.verified, res.refine_rounds
```

Loop per attempt: generate n rollouts → merge → up to `m_refine` rounds of
(syntax scrub + at most two WP rounds → verdict feedback → LLM refine → refined
candidates JOIN the pool, originals kept) → full Houdini fixpoint → Frama-C
verify. Early stops: nothing rejected / pool fixpoint / round budget.

## 5. Offline batch path (no HTTP)

`rl_pipeline/reward/io.py` reads JSONL/Parquet rollout batches (grouped or
flat layout) and writes one reward row per rollout — for offline scoring runs.
`rl_pipeline/reward/score_file.py` is the CLI wrapper. Refine scoring offline:
`rl_pipeline.reward.refine.refine_group_delta_base(program, pool, refinements)`.

The scorer's sampler interface is intentionally limited to the canonical run
count and seed:

```bash
python3 -m rl_pipeline.reward.score_file \
  --input rollouts.jsonl \
  --output rewards.jsonl \
  --runs 12 \
  --seed 0
```

JSONL uses the reward service dependencies. Parquet is optional and additionally
requires both `pandas` and `pyarrow`:

```bash
python3 -m pip install pandas pyarrow
```

## 6. Gotchas

- **Frama-C PATH**: `filter_mode: "positive"` in `/health` means the service is
  using the lite fallback. `/reward` can still respond, but production rewards
  are not proof-filtered and `/refine_feedback` returns HTTP 503. Fix the
  service environment before training.
- **Prompts are files, not code**: the trainer formats
  `prompt/generate_prompt.txt`; the service formats `prompt/refine_prompt.txt`;
  both sides use `prompt/system_prompt.txt`. Do not maintain divergent inline
  copies.
- Send the normalized `pool` echoed by `/refine_feedback` unchanged to
  `/refine_reward`. The reward is meaningful only against the pool the policy
  actually saw.
- Keep `sampler.seed`/`n_runs` fixed within a training sweep so the example-set
  cache hits and rewards are comparable across steps.
