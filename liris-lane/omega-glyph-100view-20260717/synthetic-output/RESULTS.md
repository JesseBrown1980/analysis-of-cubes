# Omega glyph 100-view simulation result

- Status: `MEASURED_SIMULATION` / `PASS`
- Transform class: `FULL_INPUT_DEPENDENT_TRANSFORM`
- Causal codec: `NO`; integrated 64/256/1024/4096 floor ladder: `NOT_IMPLEMENTED`
- Frozen input: `177` bytes, SHA-256 `d8a45de1b5d5809a80af125e036d72d9afc1a4d9712147dca0b60b120c2ac8d0`
- Provenance label: `SYNTHETIC_TEST_FIXTURE`
- Views: `100`; byte-exact inverses: `100`
- Unique canary view digests: `100/100`
- Unique glyph view digests: `100/100` (input-dependent)
- Byte H0: `4.608153843163` bits/byte over declared alphabet 256
- 10-bit glyph H0: `6.596723703920` bits/glyph over declared alphabet 1024
- View marginal glyph H0 range: `6.596723703920..6.913762788488` bits/10-bit glyph
- Residual/archive/model/decoder charge: `NOT_IMPLEMENTED`; no compression score claimed
- GF(257) UNIQUE rank/nullity: `60/0`
- GF(257) DUP rank/nullity: `10/50`
- Joint recovery: UNIQUE `100/100`; SHUFFLE_ORDER `100/100`
- SHUFFLE_BINDING original restores: `0/100`
- Misbound non-abstaining wrong restores: `100`
- Indexed-row, sorted-leaf Omega commitment: `a6ea96d76040ea05b736aee258dc3b8cd622646fc725a7a47177292fb590d0c3`

## Boundaries

The eight A-views are a function-only port of `unified_omega.rs:a_ap/a_in` from
`https://github.com/JesseBrown1980/asolaria-cube-cloud` at commit `dc02a3d9bc3201f794e6e9d3755bfdf7f858b7bd`, path
`unified_omega.rs`, source SHA-256 `308e1dca6d7bc61841f7b56c6524724f4abb12aec505548424b320a1133f68d2`.
The modulo-12, modulo-20, and frequency operators are reversible simulations—not
ports of the Rust 12-sector or 20-lens family training semantics.
The GF(257) rank/recovery lane is a disconnected SHA-seeded linear-algebra control:
it consumes no glyph-view measurements and makes no glyph-nullspace claim.
The transform derives descriptors and seeds from the complete input and requires
the original input for replay; it is not causal and is not a codec.
The `1e200` quantity is an exact address-space partition (`100 * 1e198`).
Partition arithmetic is exact; this experiment enumerates or spawns zero agents,
and the partition is not a physical-scale claim.
This does not deny separately materialized kernels or live processes; those finite
runtime measurements are outside this receipt.
The synthetic fixture contains the numeric targets by design.  Token parsing records
co-occurrence without semantics and is not a prediction test.
This result does not establish the integrated four-floor system, a live
Omega-GNN/OmniBit benefit, physical particles, cosmology, compression, novelty, o
award significance.
Invertibility is not asserted to preserve marginal H0.
