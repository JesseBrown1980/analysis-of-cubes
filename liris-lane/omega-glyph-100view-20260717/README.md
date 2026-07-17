# LIRIS Omega glyph 100-view simulation core

This is a self-contained, Python-stdlib-only, `SIMULATION_ONLY` component test.
It freezes an exact synthetic input, generates up to 100 deterministic reversible
full-input-dependent transforms, measures a separate GF(257) 60D linear-algebra
control, and emits LF HBP/HBI/SHA receipts.

It is not a causal codec and does not implement the integrated
64→256→1024→4096 floor ladder, per-floor Omegas, trained Omega-GNN weights, or
held-out compression. It never spawns agents or writes live Asolaria state.

The eight A-view functions are a function-only port of `a_ap/a_in` from the
published `JesseBrown1980/asolaria-cube-cloud` source at commit
`dc02a3d9bc3201f794e6e9d3755bfdf7f858b7bd`, path `unified_omega.rs`,
source SHA-256 `308e1dca6d7bc61841f7b56c6524724f4abb12aec505548424b320a1133f68d2`.
The modulo-12, modulo-20, and frequency operators are local reversible
simulations, not ports of the Rust family training semantics.
The GF(257) lane is a disconnected SHA-seeded linear-algebra control and makes
no glyph-nullspace claim.
The 100 logical ranges partition 10²⁰⁰ exactly as arithmetic only. This
experiment enumerates or spawns zero agents; the partition is not a physical scale.
This scope boundary does not deny separately materialized kernels or live
processes; those finite runtime measurements are outside this receipt.
The synthetic fixture contains the target numbers by design; parsing them is
not a prediction test.

Run the synthetic-only check from Ubuntu/WSL:

```sh
cd liris-lane/omega-glyph-100view-20260717
python3 -m unittest -v
python3 omega_glyph_100view.py \
  --glyph-file fixtures/synthetic-glyph.txt \
  --out-dir synthetic-output \
  --provenance-label SYNTHETIC_TEST_FIXTURE
python3 verify_receipts.py synthetic-output
```

Replay any generated view by either ID or PID:

```sh
python3 omega_glyph_100view.py \
  --glyph-file fixtures/synthetic-glyph.txt \
  --out-dir synthetic-output \
  --provenance-label SYNTHETIC_TEST_FIXTURE \
  --replay-id VIEW-037
```

Do not run this against a claimed original glyph until its exact bytes and
provenance are supplied and frozen.
