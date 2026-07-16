# Analysis of Cubes

Content-addressed research workspace for cube geometry, projection tests and RELIC Lab evidence.

## Repository lanes

- `main`: shared contracts, source authority, geometry families and interface layers.
- `relic`: RELIC Lab observation and receipt lane.
- `liris`: LIRIS verification and attack-test lane.
- `acer`: ACER origin, source-master and execution-report lane.

The seat branches are separate evidence perspectives. A branch name does not grant authority,
promote a claim to Canon or prove that another machine reproduced a result.

## Geometry families

1. `8-pole`: the eight vertices of the `C2^3` cube and even/odd parity partition.
2. `12-sector`: the twelve cube edges/interfaces, with the `8 visible / 4 occluded` model recorded
   as falsifiable hypothesis C8.
3. `24-direction-pi-sphere`: a planning-only directional family.

Their roots may join a unified Omega only after each family has an exact receipt set and reversible
forward/reverse replay.

## PR-038 source authority

The authority lane distinguishes:

- AARO case `PR-038`, status `Unresolved`;
- official DVIDS asset `DOD_111689051`;
- third-party recodes used only as control lanes.

The official narrative is informational. It is not an analytical judgment, investigative
conclusion or factual determination about the event.

## Artifact policy

- HBP/HBI receipts and SHA-256 sidecars are tracked.
- Source videos, extracted frames, model weights, secrets and paid-provider payloads are excluded.
- Remote hashes remain `REPORTED_REMOTE` until the bytes are present and verified on the current
  seat.
- Rendering a model does not promote it to measured evidence.

## Paid cloud gate

External paid-agent dispatch is held while `max_spend_usd=UNSET`. Logical/local agents are not
counted as provider calls.

Run the local receipt validator:

```powershell
.\scripts\seal-receipts.ps1 -Verify
```
