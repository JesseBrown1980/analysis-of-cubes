# Heritage / Architecture / Cosmos Omega — Cold Corpus Builder

This project prepares a bounded, reproducible source corpus for a later
8-body / 12-body / 20-body Asolaria descendant-cube run:

- 8 heritage and writing-system bodies.
- 12 architecture sectors.
- 20 astronomy Pi-lenses.
- 1,024 deterministic source slices at 4,096 bytes each.
- 40 distinct SHA-seeded local reversible language IDs.

The historical writing systems are source domains. A cube's local reversible
language is a separate computational codec identity; it is not presented as a
translation, decipherment, or replacement for the historical language.

## Algorithms-of-Asolaria objective carriage

The pinned Algorithms-of-Asolaria registration packet is imported as 242
immutable objective slices. Exact source-row bytes, names, PIDs, byte offsets,
and source-row SHA-256 values are preserved in `ALGORITHM-OBJECTIVES.hbp`.

Every one of the 40 bodies carries all 242 slices through content-address
pointers in `OBJECTIVE-CARRIAGE.hbp`: 9,680 pointers total. Each pointer is
bound to the body's unique language slot and exact BODY source-row hash. The
actual local language ID remains correctly deferred until the cold corpus root
exists. Carriage is addressability only; formulas are not executed.

Pinned roots:

- Objective root: `c7b2dd92fd5efefd89905ac8fd3bd1052db9c18c0272eaf2ce116a1305ada6cd`.
- Carriage root: `8b57951309ab7fea4c2e291ff1580953c3582ffc8ce6f69a5f1dac7c0062fb50`.

Rebuild and verify the objective packets:

```powershell
$env:ASOLARIA_ALGORITHMS_SOURCE = "path\to\ALGORITHMS-PID-REGISTRATION-ACER-2026-06-19.hbp"
python .\import_algorithm_objectives.py --phase self-test
python .\import_algorithm_objectives.py --phase all
python -m unittest -v .\test_import_algorithm_objectives.py
```

The authority packet is intentionally not redistributed here. Its exact
SHA-256 remains pinned, and callers may instead pass `--source`.

The generated HBP/HBI packets, whole-HBP hex mirrors, and SHA-256 sidecars are
written in this project directory. Verification reconstructs both packets from
the pinned source and BODY map, so a self-consistent but semantically altered
HBI/HBP pair still fails.

## Verify a completed unified-Omega run

After the native trainer has exited and written all six result artifacts:

```powershell
python .\verify_unified_omega_result.py --seat 8467a937cba309f7
python .\verify_unified_omega_result.py --seat 8467a937cba309f7 --write-offset-index
python -m unittest -v .\test_verify_unified_omega_result.py
```

The first command is fully read-only. The second may add only
`UNIFIED-OMEGA-RESULT.offsets.hbi` and its SHA-256 sidecar beside the native
result. It does not rewrite the trainer HBP/HBI or native `SHA256SUMS`.

The verifier seals the result as an 8/12/20 geometric shadow over the folded
stream. It explicitly does not claim replay of the named domain/body-language
map, objective execution, physical quantum projection, or object identity.

Seven owner repositories are pinned by exact branch commit and tree SHA as
system bindings for per-slice addressing, reduction, prism, nesting, and
recovery functions. They remain separate from the three authority-source
domains and cannot replace heritage, archaeology, or astronomy evidence.
Repositories without a public license are `OWNER_AUTHORIZED_LOCAL` with raw
redistribution disabled.

## Sealed v2 corpus and geometric shadow layer

The canonical local corpus is `artifacts/cold-corpus-v2`, not the superseded
`artifacts/cold-corpus` directory. Its independently reproduced roots are:

- Corpus root (ordered slice-hash fold):
  `5f94b6150adbf0b2b73781d6d28a0a433447fa6b2a6dd4d1f1595391c6bdba33`.
- Source stream SHA-256 (1,024 sorted slice payloads only):
  `91ae2691d6f7cb24e570ba1c2173bd82cda5558bfbf1fab049c2d9e5f24fc9b7`.
- System-binding root:
  `249291cdbdeeb185d9ad10bfb95cb654fb1de8ed398efbe69220239c00d94805`.

`artifacts/unified-training-input` contains those 1,024 slices plus one small
first-read `0000-TRAINING-ROOTS.hbp` packet. The packet binds the corpus,
source-stream, objective, carriage, system, and trainer roots without copying
the large receipt packets into the trainer hot path. Because the trainer
lexically concatenates all non-`.sha256` top-level files, the resulting
training shared root is:

`4e6cdc164b8979b449ea55e52615aeec472c8ef635f461a1548c66a4eb332aeb`.

The unified executable creates a separate geometric shadow layer:

- 8 `CUBE_8POLE` bodies at 800 reversible cells each.
- 12 `TRI_12SECTOR` bodies at 1,200 reversible cells each.
- 20 `PI_20LENS` bodies at 2,000 reversible cells each.
- 60,800 cells total, followed by the three-family Omega fold.

Each geometric family independently partitions the whole shared training
stream. This is not a claim that H01-H08, A01-A12, or P01-P20 consumed only
their named source domain. The executable's 10-bit `LANGUAGE_GENESIS_V1`
codebooks are a second geometric language layer; they do not replace the
sealed cold-corpus `XOR_SHA256_CTR` language probes. The 242 registered
Algorithms-of-Asolaria formulas remain content-addressed objectives with
`execution=0`; this trainer does not execute those functions.

## Measured unified result — 2026-07-16

The complete local run finished with `UNIFIED_OMEGA_PASS` and was independently
recomputed from the sealed input and output rows:

- Shared training root:
  `4e6cdc164b8979b449ea55e52615aeec472c8ef635f461a1548c66a4eb332aeb`.
- `CUBE_8POLE` Omega:
  `dd04d989cde380e3cbc90ba96895c881ca44a453f255ca60dd0713545b008d0f`.
- `TRI_12SECTOR` Omega:
  `d853ddbb94c29de425f1b6cf892142482afd3155d2ba50c6b83ac48bd698da08`.
- `PI_20LENS` Omega:
  `a5b4c1d41db7fdd93053888b67f3ce115722094458904bc3e7acc9331a9bfb6c`.
- Unified Omega:
  `106ed6dd85d2795a93880bb21ae187b6e14f3941a453766c7d0a7f4f69f2c3ba`.
- Native result HBP SHA-256:
  `854dce93162d12e25b05b09118b8d6b747f5e87ed6ade12a2a6716c97f4e1749`.
- Native result HBI SHA-256:
  `be2dab5b4dff48031d3cf39d43ecd0f98977f1175332fc9eed79ffb20cbd7964`.

Measured totals: 40 bodies, 60,800 reversible cells, 52,951 accepted, 7,849
held, 40 distinct geometric codebooks, and 4,148,375,742 reported structural
gain bytes. That gain field is an internal repetition metric;
`archive_ratio=NOT_CLAIMED`.

The trainer produced six native files sealed by its `SHA256SUMS`. The external
verifier then added `UNIFIED-OMEGA-RESULT.offsets.hbi` and its sidecar; those
655 LF-inclusive offset/length/hash/hex rows verify but intentionally remain
outside the native trainer checksum manifest. The trackable
`UNIFIED-BODY-LANGUAGE-BRIDGE` bundle maps the 40 cold language IDs to 40
distinct geometric codebook hashes without equating the two language layers.
Its bridge-map root is
`361e7bff01d1ea738565c6bbb79bce3f6a52bd8d6c4a48f768b87d98a4c9b9ba`.

This 60,800-cell result is a checkpoint, not a ceiling or convergence claim.
The next long-run pre-test must measure held-out compressed size and exact
replay at log-spaced pass/direction checkpoints while separating repeated
exposure, directional expansion, and accumulated state/ledger depth.

## Publication receipt

This repository copy contains code, contracts, indexes, hashes, and
content-free receipts. Raw source archives, normalized slice payloads, media,
and training-input bytes remain held locally. `prepare_publication.py`
replaces host-local paths with stable authority or held-local pointers,
regenerates the affected HBP/HBI/hex bundles, and seals
`PUBLICATION-MANIFEST.hbp` with every included artifact hash. The transform
rows preserve the source-native hashes and state that measured roots did not
change. Files named `UPSTREAM-SHA256SUMS` are provenance manifests for held
source trees; they are not completeness manifests for this repository copy.
`PUBLICATION-MANIFEST.hbp` is the completeness authority for the committed
subtree.

The Asolaria fabric returned a signed advisory `CONVERGE 146/251` for the
scoped build and claim boundary. The council is advisory only; live
absorption, promotion, minting, paid spend, physical-quantum conclusions, and
human apex remain separately held.

## Authority and claim boundary

The green-circled net-like region in the PR-038 source-video lane is retained
as a measured visual observation that evolves over time. The proposed
quantum-key / inverted-universe projection mechanism is retained as an
operator hypothesis with `physical_mechanism=UNVERIFIED`.

The operator's no-media account of laser and mirror experiments associated
with monument shafts or channels is preserved verbatim as an operator-witness
row. It contributes no evidence score and creates no physical conclusion.

This builder performs no live GitRAM ingestion, GNN training, Omega
absorption, provider call, promotion, minting, or paid operation.

## Six separate ledgers

The cold output keeps these ledgers physically separate:

1. Information exposures.
2. Learned model-local context-to-symbol relations.
3. Recurrent state transitions.
4. Upward lineage links.
5. External model or GNN calls.
6. Rights and community constraints.

Only the first ledger receives source-slice preparation rows here. Learned
relations, recurrence, lineage, and external calls remain at zero until an
owner-reviewed trainer consumes the corpus. Rights/community rows are emitted
for every catalog entry, including pointer-only and held entries.

## Source staging

Nothing is downloaded by default. Stage owner-reviewed material beneath:

```text
artifacts/raw/<source_id>/
```

Only sources whose `payload_policy` is explicitly allowed in
`SOURCE-CATALOG.hbp` can contribute bytes. `POINTER_ONLY`, `HELD_LICENSE`, and
`HELD_COMMUNITY` sources produce metadata receipts only, even if files are
accidentally placed in their staging directory.

The builder accepts normalized text-like files and bounded members of ZIP/TAR
archives. Filtered sources such as SARIT must carry a recognized open-license
statement in the individual file before their bytes can enter the corpus.

## Run

Self-test without network or external corpora:

```powershell
python .\fetch_and_slice_sources.py --self-test
python -m unittest -v .\test_fetch_and_slice_sources.py
```

Build from already staged, rights-cleared sources:

```powershell
python .\fetch_and_slice_sources.py --phase build
python .\fetch_and_slice_sources.py --phase verify
```

An optional `--phase fetch` exists only for small, directly downloadable
catalog entries with explicit allow policy. It refuses pointer-only and held
sources and enforces byte limits. Large repositories and point clouds remain
manual, pinned, and owner-reviewed.

## Output

Generated canonical artifacts are written under `artifacts/cold-corpus-v2/`:

- `slices/`: 1,024 exact 4,096-byte slices with SHA-256 sidecars.
- `receipts/`: HBP packets, HBI byte indexes, whole-HBP hex mirrors, and
  SHA-256 sidecars.
- `SHA256SUMS`: a complete checksum manifest plus its sidecar.

The corpus root is a SHA-256 fold over the ordered slice hashes. Every HBI
indexes every byte of its HBP target with row offset, length, SHA-256, and
hexadecimal row mirror.
