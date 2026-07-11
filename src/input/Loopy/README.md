# Loopy Loop-Invariant Inputs

This directory contains the 466 integer, single-method, single-loop programs
from the 469-program corpus used by *Finding Inductive Loop Invariants using
Large Language Models*. They are normalized for LoopGym instead of being stored
as a second raw corpus.

## Provenance

- Upstream: `microsoft/loop-invariant-gen-experiments`
- Commit: `91fe89245a0894ec8ad3741d85ae91ce3b552b2e`
- Source archive SHA-256:
  `3e8ebeebeac780a8c7aa89a3d6b36dc77553e8f481ca37bf50c9e0978715a51e`
- Imported subset: `dataset/loop_invariants`

`manifest.jsonl` maps each numeric filename to its original path and records
both source and normalized SHA-256 hashes. `sources.txt` is the source list from
the upstream archive. `UPSTREAM_LICENSE.txt` covers the Loopy artifact itself;
third-party notices are retained under `LICENSES/` and take precedence for the
corresponding source programs.

## Normalization

The normalization preserves each assertion at its original control-flow location
and applies these source-level changes:

- 53 `for` loops and one `do ... while` are lowered to a single braced `while`;
- loop-entry nondeterministic or uninitialized scalar values become function
  parameters;
- dominating pre-loop path guards become ACSL `requires` clauses;
- per-iteration nondeterministic calls remain calls and receive typed sampler
  stubs;
- `_Bool` inputs become integers constrained to 0 or 1;
- `unsigned char` and `unsigned short` inputs become bounded `unsigned int`;
- the one bounded `unsigned long long` accumulator becomes `unsigned int` (its
  maximum value is below `2^32` in that fixed program);
- all functions use unique `loopy_<id>` names and contain exactly one braced
  `while` loop.

Official IDs 353--355 require floating-point reasoning, which neither LoopGym's
sampler nor its predicate evaluator supports. Their exact upstream sources are
kept in [`unsupported/loopy/`](../../../unsupported/loopy/) and are excluded
from this manifest, suite discovery, sampling, and reported LoopGym results.
IDs are intentionally not renumbered so every remaining filename still matches
the official Loopy order.

## Scope

This corpus overlaps the existing `linear` suite through Code2Inv, SyGuS, and
SV-COMP sources. It is a comparison corpus, not a disjoint held-out set, and it
is not included in the previously reported 366-program mislabel audit.
