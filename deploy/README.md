# Reward scoring service (Docker)

Wraps `rl_pipeline.reward` as an HTTP microservice for RL training (e.g. **verl**):
send a **group of rollouts** for a program, get back **a score for each rollout**.

**Self-contained real Houdini.** The image bundles `frama-c` + `z3` + `why3`, so the
reward filter runs the full cascade — **lite `PositiveFilter` (preprocessing) → real
inductive Houdini via Frama-C/WP+z3**. A deployment host (your verl RL server) needs
**no local frama-c**; it only calls the HTTP endpoint.

## Build & run

```bash
# from repo root (build context = repo root)
docker build -f deploy/Dockerfile.reward -t sam2inv-reward .
docker run --rm -p 8000:8000 sam2inv-reward
# or:
docker compose -f deploy/docker-compose.yml up --build
```
The image is large (~1 GB) because it carries the frama-c/WP toolchain. The build
runs `why3 config detect` and a wiring check that fails fast if `frama-c` isn't
found or the filter doesn't resolve to `cascade(...)`.

## Verify (on the docker host)
```bash
curl -s localhost:8000/health          # -> {"status":"ok","filter_mode":"cascade(positive->houdini)"}
curl -s localhost:8000/reward -H 'content-type: application/json' -d '{
  "program": "<C source with requires / loop / assert>",
  "rollouts": [ {"invariants":["x + y == n","x >= 0"]}, {"invariants":["x + y == n"]} ]
}'
```
`filter_mode = cascade(positive->houdini)` confirms real Houdini is active. If it says
`positive`, frama-c was not detected in the image (build failed silently → rebuild).

## API

### `POST /reward`
Request:
```json
{
  "program": "/*@ requires n>=0; */ void foo(int n){ int x=0,y=n; while(x<n){x++;y--;} /*@ assert x==n; */ }",
  "rollouts": [
    {"invariants": ["x + y == n", "x >= 0"]},
    {"invariants": ["x + y == n", "x == 999"]}
  ],
  "w_base": 0.5,
  "w_marg": 0.5,
  "sampler": {"n_runs": 16, "n_random": 3000, "max_loop_mutants": 20, "seed": 0}
}
```
Each rollout may be `{"invariants": [...]}` or `{"code": "<annotated C>"}`.

Response (per-rollout scores + batch):
```json
{
  "batch_score": 1.0,
  "should_reroll": false,
  "rollout_rewards": [0.83, 0.41],
  "base":            [0.83, 0.10],
  "marginal":        [0.00, 0.31],
  "rollouts": [
    {"index": 0, "reward": 0.83, "base": 0.83, "marginal": 0.0, "rejected": 287, "survivors": ["x + y == n","x >= 0"]},
    {"index": 1, "reward": 0.41, "base": 0.10, "marginal": 0.31, "rejected": 34,  "survivors": ["x + y == n"]}
  ]
}
```
- `base[A]`     — negatives rejected by the cascade (lite→**Houdini**) run on rollout `A` alone
- `marginal[A]` — extra negatives the batch union rejects thanks to `A` (ablation)
- `reward[A]`   — `w_base*base + w_marg*marginal` (the per-rollout RL reward)
- `batch_score` — negatives rejected by Houdini(union of all rollouts)

The example set (positives/negatives) is sampled once per `(program, sampler-cfg)` and
cached, so repeated batches for the same program are cheap.

### `GET /health`
```json
{"status": "ok", "filter_mode": "cascade(positive->houdini)", "cached_programs": 3}
```

## verl integration
In your verl reward function, POST the rollout group for each program to `/reward`
and read `rollout_rewards[i]` as the reward for rollout `i`. Scoring needs the
`program` alongside the rollouts — the reward is defined by how many spec-derived
**negative** valuations each invariant set excludes (a property of the program's
guard/postcondition), not of the rollout text alone.

**Throughput note.** Real Houdini calls Frama-C/WP per rollout group (seconds each);
the lite `PositiveFilter` preprocessing shrinks the invariant set first to cut WP
goals. For high-concurrency RL, run several replicas behind a load balancer and/or
raise the sampler cache hit rate by reusing programs.
