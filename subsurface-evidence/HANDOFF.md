# Claude handoff: Smeaheia and all-area well tracks

**Resume here on `kratos`: `/home/v1s/Documents/hackathon-force/subsurface-evidence/HANDOFF.md`.** The local release is finished and verified. It is not committed or deployed. Smeaheia is the decision view; the rest of the shelf is searchable evidence, not 8,496 integrity predictions.

## First five minutes

1. Work in `/home/v1s/Documents/hackathon-force`, not `/home/v1s` (a different checkout). Start with `git status --short --branch`; baseline at handoff: `main`, `e923fb2`. New files are untracked: `git diff` alone misses them. Preserve the existing `backend/se/modeling/well_tie.py` and `backend/se/api/provenance.py` research changes.
2. Read [agent rules](../.github/copilot-instructions.md), the [focus plan](PLAN.md) and [decision log](LOG.md), especially L084–L090. Use the [local run guide](README.md#run-locally). Test with localhost services, not live pods. `kratos` runs a shared k3s cluster; the owner connects from `atlas` over Tailscale. Deployment config is `/home/v1s/homelab`.
3. Give short updates. The owner performs **all Git mutations and sudo**. No pod reload, deployment, active-pointer change, bulk data scan or deletion of findings without explicit approval. Do not read FORCE hidden labels or access Volve credentials. Use the cached flake via `direnv`; do not run `nix ... path:.` over the data checkout.

## What to open

| View | Case to try | What it establishes |
|---|---|---|
| `#screen` (home) | `32/2-1`, **Compare formation, cement and test depths** | Plug 2 nominally overlaps 110/110 m of the Sognefjord MD interval. Physical PDF pp.8, 39 and 57 matter; the TD datum labels disagree. Not tested isolation. |
| `#screen`, **Colour wellheads by rock + pressure rule** | `31/3-3`, then outside reference `31/3-1` | Six local heads: zero green, one red, five grey. Longest joint run 13 m at `31/3-3`. The outside reference has 70 m and is not transferred. |
| `#tracks` | `15/9-13` (45), then `31/5-7` (8951) | Sleipner: two unpositioned equipment-test outcomes predate the later plug, PDF p.123. Aurora: one reservoir DST, with the structured and narrative top depths both shown. Neither is a plug test. |
| `#tracks` | `32/4-4` (10166) | No positioned record or reviewed placement in these sources. Missing is not failed. |
| `#research` | Frozen Horda build `f46ffd5abca4` | Preserved regional model and prior findings. CO₂ scores, reservoir probabilities and report mentions are not integrity probabilities. |

**Coverage:** all four configured regional boxes and all three named sites; every exploration/development borehole searchable, P&A optional. Of 8,496 wells, 2,034 have positioned records, 2,610 only catalogue/document leads, and 3,852 neither. Nine curated cement placements in six wells. Site counts overlap regional counts; scope is based on wellheads, not trajectories.

## What implements what

Paths below are relative to `subsurface-evidence/`.

| Responsibility | Entry points |
|---|---|
| Smeaheia membership, marker/trajectory evidence, held-out top experiment | `backend/se/modeling/{smeaheia_screen,screen_validation}.py`, `backend/se/api/screen.py`, `ui/static/screen.js` |
| Jeham-derived rule | `backend/se/knowledge/rules/smeaheia_interval.yaml` → `backend/se/modeling/interval_screen.py` → strict state in the Smeaheia receipt → `strictRuleStyle` in `ui/static/screen.js`. The toggle is display only. |
| Exact-well track release | `backend/se/knowledge/rules/well_tracks.yaml` → `backend/se/modeling/well_tracks.py` → hash-addressed index and packs → `backend/se/api/tracks.py` → `ui/static/tracks.js`. `TRACK_FOR_SCREEN` pins the companion track release. |
| Verification | `backend/tests/test_{interval_screen,smeaheia_screen,well_tracks}.py`, `ui/static/selftest.html?screen` and `?tracks` (the query strings are for the running UI). |

[Jeham's engine](https://github.com/jeham3408/natures-plug/blob/6499e399fc64e33b8c008ab279a56c8801c5eff3/js/engine.js) checks a clay-like log signature **and** estimated pressure capacity at the same depths, then run length. It allows missing sonic by default and can colour development wells from the nearest assessed control within 10 km. **We do neither in the strict result.** We screen above a reported Sognefjord top on the exact borehole, require co-measured GR >40 API, deep resistivity <1.3 Ω·m and sonic >135 µs/ft, and interpolate capacity only between positioned LOT shoes using supported vertical depths. Green requires 30 consecutive qualifying along-hole metres; red requires 30 consecutive assessable metres but no qualifying run; otherwise grey. Pressure is a gas-load proxy, not a measurement, CO₂ forecast or proof of creep. Optional-sonic, zero-overbalance and formation-group comparisons do not control the colours.

## Reproduce without touching the cluster

From `subsurface-evidence/backend` on the data host:

```sh
direnv exec ../.. env -u PYTHONPATH OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --frozen pytest -q -rs tests
direnv exec ../.. env -u PYTHONPATH OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --frozen python -m se.modeling.well_tracks
```

The second command requires the focused receipt and original local inputs. It verifies or writes immutable files under `data/subsurface-evidence/screen/well_tracks/`, not Git. Do not change pins just to make a run pass. If an input hash differs, identify the changed source first.

| Receipt | SHA-256 |
|---|---|
| All-area track index, 84 packs | `d92d14a3bce5e33d44fddec575a7e544ed392cbdb99d2dc39e64746b813bb5ca` |
| Smeaheia strict scenario (schema 2) | `50fe1fd2c6ab16d51bc3e1bb7bf4c573d2bcaf65fa5864fa9ad95f442f89eb7c` |
| Historical Smeaheia (schema 1, no scenario) | `9add38a1df98dadb32bddd5e722b8cca7760f1b6dd9b0f740f16bcc380fa2ecf` |

Verified locally: **81 backend tests passed, one skipped (no CUDA in the test environment); 22 screen and 16 track browser checks passed.** The default `/selftest.html` without a query can build research targets; do not use it against shared outputs. The historical active Earth build and running pods were left alone. Local verification does not establish what is live in k3s.

## Best next task

**Start with `32/2-1`, not another model.** Find an original, interval-specific test of one of the four reported cement plugs. Use the released end-of-well report and exact well record. Record the report hash, physical PDF page, equipment or plug tested, date, depth bounds/datum, applied pressure, acceptance criterion and observed outcome. If the source omits a field, record it as unknown. Do not repurpose the 835 m LOT or the abandonment *objective*. If no such report is available, log the sources/pages checked and the document to request; do not change the colour or integrity status.

Next evidence gaps are exact-borehole formation picks for `32/4-4`, directional stations at missing top depths, and independent local checkshots/VSP with processing datums. Never fill these from a sidetrack or nearest well. Any new prediction needs independent outcomes and a held-out baseline comparison, not agreement with this rule. Append the next decision after L090; keep historical receipts readable.
