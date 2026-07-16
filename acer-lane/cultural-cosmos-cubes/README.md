# ACER cultural and cosmos cube lane

This lane builds independent, byte-reversible 8/12/pi cube sets from
traceable cultural-heritage and astronomy corpora.

The build starts from zero for every corpus:

1. acquire bytes from the authority named in the source manifest;
2. preserve the raw bytes and their SHA-256 digest;
3. normalize only through a declared, deterministic derivative;
4. run the unified trainer against that corpus alone;
5. verify byte-exact restore and distinct per-body codebooks;
6. seal HBP, HBI, SHA-256 sidecars, and a batch index.

## Important meaning of “one language per cube”

The trainer's language is a deterministic, SHA-seeded bijection over the
1024 glyph symbols. It is a reversible formal codebook. It is not a claim
that the cube understands, translates, or reconstructs the semantics of an
ancient human language.

Historical languages and writing systems remain distinct:

- Sanskrit is a language represented in several scripts.
- Sumerian is a language commonly written in cuneiform.
- Proto-cuneiform is an early writing system and accounting tradition.
- Khipu is an Andean information-recording system, not an Inca
  hieroglyphic script.
- Teotihuacan and Mexica/Aztec material are separate cultural families.
- Nasca geoglyph geometry is separate from any astronomical interpretation.

## Claims states

Every source and derivative must use one of these states:

- `MEASURED_PUBLISHED`
- `MEASURED_REPRODUCED`
- `MODEL_RECONSTRUCTION`
- `INTERPRETIVE_HYPOTHESIS`
- `OPERATOR_OBSERVED_UNDOCUMENTED`
- `KNOWN_CAPTURE_NOT_OPENLY_ACQUIRED`
- `PLANNED_DOWNLOAD`
- `UNVERIFIED`

Geometry can pass its measurement gates while intent, function, astronomical
alignment, causal mechanism, and extraordinary interpretation remain held.
`claims_final_apex=0` remains binding.

## Initial floors

The first bounded build targets:

- Unicode/UCD inventories for Egyptian, cuneiform, early cuneiform,
  Anatolian hieroglyphs, Maya numerals, and Sanskrit-associated scripts;
- archaeological source manifests for Giza shafts/channels, ScanPyramids,
  Maya, Mexica, Teotihuacan, Andean, khipu, and Nasca material;
- NASA Exoplanet Archive plus a deterministic Gaia subset;
- the 242-formula Algorithms of Asolaria registry and metatagging contracts.

Large imagery, LiDAR, all-sky maps, and billion-row catalogs are later,
license- and resource-gated floors.

## Layout

```text
contracts/       schemas and claims gates
manifests/       sources, corpus definitions, and objective bindings
operator/        operator testimony, never promoted to measured evidence
scripts/         deterministic acquisition/build helpers
corpora/         acquired raw and normalized corpus bytes
results/         generated HBP/HBI/SHA receipts (not hand-edited)
```

## Build

```powershell
.\scripts\validate-corpus-manifest.ps1
.\scripts\build-unicode-corpora.ps1 -UnicodeData path\to\UnicodeData.txt
.\scripts\build-corpus-batches.ps1
```

The batch script invokes the existing dependency-free Rust unified trainer.
It does not launch cloud agents, promote a GNN, or make physics claims.
