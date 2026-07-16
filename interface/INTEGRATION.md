# RELIC Lab interface integration

The interface layer sources are copied from the local Omega observatory implementation:

- `immersion-shell.js`: canonical six-vector core plus 12-sector projected shell.
- `immersion-shell.css`: adaptive HUD and layer controls.
- `official-source-layer.js`: PR-038 authority lanes.

The 12-sector renderer depth-ranks the twelve cube-edge midpoint directions and styles the nearest
eight as exposed and the farthest four as occluded. This is a visualization of hypothesis C8, not
proof that the recorded area of contrast has this geometry.

Keyboard controls:

- `1`: canonical six-vector core;
- `2`: 12-sector shell;
- `3`: evidence layer;
- `4`: causal layer;
- `M`: cycle layers.
