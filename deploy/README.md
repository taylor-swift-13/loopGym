# Reward scoring service (Docker)

Wraps `rl_pipeline.reward` as an HTTP microservice for RL training: send a
**group of rollouts** for a program, get back **a score for each rollout**.

## Build & run

```bash
# from repo root
docker build -f deploy/Dockerfile.reward -t sam2inv-reward .
docker run --rm -p 8000:8000 sam2inv-reward
# or:
docker compose -f deploy/docker-compose.yml up --build
```

## API

### `POST /reward`
Request:
```json
{
  "program": "/*@ requires n>=0; ... */ void foo(int n){ int x=0,y=n; while(x<n){x++;y--;} /*@ assert x==n; */ }",
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
    {"index": 0, "reward": 0.83, "base": 0.83, "marginal": 0.0, "rejected": 287},
    {"index": 1, "reward": 0.41, "base": 0.10, "marginal": 0.31, "rejected": 34}
  ]
}
```
- `base[A]`     — negatives rejected by `Houdini(A)` alone
- `marginal[A]` — extra negatives the batch union rejects thanks to `A`
- `reward[A]`   — `w_base*base + w_marg*marginal` (the per-rollout RL reward)
- `batch_score` — negatives rejected by `Houdini(union)`

The example set (positives/negatives) is sampled once per `(program, sampler-cfg)`
and cached, so repeated batches for the same program are cheap.

### `GET /health`
```json
{"status": "ok", "filter_mode": "positive", "cached_programs": 3}
```

## Notes
- **No frama-c / torch needed.** The service uses the Houdini-lite `PositiveFilter`
  (drop invariants unsound on reachable positives, then count negatives rejected).
  Install frama-c in the image to enable real inductive `Houdini` (`filter_mode`
  becomes `cascade`).
- Scoring needs the `program` alongside the rollouts — the reward is defined by how
  many spec-derived **negative** valuations each invariant set excludes, which is a
  property of the program's guard/postcondition, not of the rollout text alone.
