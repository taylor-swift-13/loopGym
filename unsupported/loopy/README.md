# Unsupported Loopy Floating-Point Inputs

This directory contains exact upstream copies of official Loopy corpus IDs
353, 354, and 355. They require floating-point reasoning and are deliberately
excluded from LoopGym's supported benchmark discovery, sampling, and results.

The Loopy paper includes these programs in its 469-program input corpus but
classifies all three under "ground truth invariant requires floating point
reasoning" in the qualitative analysis of failed benchmarks (Table 2). Keeping
the sources here records the complete upstream corpus without implying that
either Loopy or LoopGym successfully verifies them.

No fixed-point substitute is included. Such a conversion changes C floating-
point rounding and real-valued input semantics, so it would be a different
verification task rather than a normalization of the original benchmark.

`manifest.jsonl` records the official IDs, paths, and exact source hashes.
`UPSTREAM_LICENSE.txt` covers the Loopy artifact; the originating SV-Benchmarks
Apache license is retained under `LICENSES/`.
