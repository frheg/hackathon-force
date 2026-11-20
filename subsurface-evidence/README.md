# Subsurface Evidence

Smeaheia legacy-well review is the default workspace. Select a well to see reported Sognefjord (reservoir) and Draupne (primary seal) intervals, sampled path coverage, cited abandonment evidence and the next check. A missing pick is unknown. A registry P&A status is not a barrier test.

## Run locally

Use the host with the local `data/` directory. From the repository root, run these in two terminals:

```sh
# Backend
cd subsurface-evidence/backend
direnv exec ../.. env -u PYTHONPATH OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  uv run --frozen uvicorn se.api.main:app --host 127.0.0.1 --port 8460
```

```sh
# UI proxy
cd subsurface-evidence/ui
direnv exec ../.. env -u PYTHONPATH BACKEND_URL=http://127.0.0.1:8460 \
  uv --project ../backend run --frozen uvicorn serve:app --host 127.0.0.1 --port 8461
```

Open [Smeaheia](http://127.0.0.1:8461/#screen). The default scene reads one hash-verified receipt, requires no GPU or external chart services, and does not follow the regional active pointer. Examples: `32/2-1` for the dated operations report (PDF p.57); `32/4-1` for MD picks without a sampled path; `32/4-4` for missing picks. The `32/4-1 T2` workbook is not the parent's trajectory.

The queue uses six registry wellheads inside the decimated GN1101/TNE01 convex hulls, plus one separately labelled outside reference. Not a complete survey of all laterals or a containment map. Marker roles: Equinor/Gassnova Smeaheia release, *Statoil internal report on Smeaheia Subsurface 2016, selected extracts*, PDF p.5 ([source and licence](https://doi.org/10.11582/2021.00012)). Source archive members, registry IDs, unit IDs and hashes are in the receipt.

**Rock + pressure scenario:** adapted from [Nature's Plug](https://github.com/jeham3408/natures-plug/blob/3df7c523f9469756aeb8910c2be01456ddda7df8/js/engine.js). Look above an exact Sognefjord pick for 30 adjoining 1 m MD bins with a clay-like measured signature **and** sufficient estimated pressure capacity at the same depths. Our default requires measured sonic, a bracketed mud weight at the top, sampled TVD and two positioned leak-off tests. The UI shows the actual run, the optional-sonic and zero-overbalance comparisons, and separately the total reported Hordaland/Rogaland metres in the pressure window. No nearby verdicts are transferred. The illustrative gas load is not an operating pressure for CO₂, a safety margin or a prediction of sealing. No integrity ground truth or validated accuracy gain.

`31/3-3`: 16 joint metres, longest **13 m**; five other footprint wells have insufficient evidence. Outside reference `31/3-1`: **70 m** longest, not a local candidate. `32/2-1`: one LOT, so the pressure interval is unknown despite measured logs and reported cement placements.

**Optional map colours:** enable **Colour wellheads by rock + pressure rule**. Green `+`: at least 30 continuous qualifying metres. Red `−`: at least 30 continuous metres could be assessed, but no qualifying 30 m run was found. Grey `?`: insufficient evidence. Only wellheads change colour; gold and purple downhole picks still mark formations. The legend counts the six local wells, not the outside reference. The old release has no rule and no toggle.

**Reproduce on the data host:** from the repo root, enter `nix develop`; from `subsurface-evidence/backend`, run `env -u PYTHONPATH OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --frozen python -m se.modeling.smeaheia_screen`. This uses the locked DuckDB reader and writes only a new content-addressed receipt (or verifies the existing one). Release: `50fe1fd2c6ab16d51bc3e1bb7bf4c573d2bcaf65fa5864fa9ad95f442f89eb7c`. The [previous receipt](http://127.0.0.1:8461/#screen/5839/9add38a1df98dadb32bddd5e722b8cca7760f1b6dd9b0f740f16bcc380fa2ecf) remains readable without the interval scenario. Requires the original frozen build and local licensed inputs. A missing release produces an unavailable notice, never a fallback to mutable data.

**First depth experiment:** a fixed nearest-well estimate of top Sognefjord scored **676 m MAE**, vs **604 m** for the training median. Same 20 path-supported wells, five held-out 40 km blocks, 10 km purge and no shared registry well families. No new depth estimate is published. Historical Sognefjord grid nodes can be toggled for context; their model SD is not a site prediction interval.

[Research](http://127.0.0.1:8461/#research) preserves the regional model, seismic inspector, Strata Desk, target builder and other tools. Only the historical regional view follows the active build or legacy data. Start the GPU worker only for GPU jobs.

## All-area well tracks

Open [Well tracks](http://127.0.0.1:8461/#tracks), select an area, or search a name or Sodir ID. No P&A filter by default. From Smeaheia, **Compare formation, cement and test depths** opens the same borehole and pinned track release. Click a depth bar or expand a source row to inspect the evidence.

- **Coverage:** 8,496 boreholes; 2,034 with positioned records, 2,610 with document leads only, 3,852 with neither. Nine reviewed cement placements across six wells, not nine verified barriers. Region boxes, the Smeaheia survey footprints, Sleipner box and Aurora 12 km radius select wellheads, not subsurface crossings.
- **Example:** `32/2-1` plug 2 nominally overlaps 110/110 m of reported Sognefjord MD. The source pages disagree on a depth reference; no current isolation is inferred. `15/9-13` has two equipment-test reports with no tested depth bounds; neither is a test of the later plug. `31/5-7` has a reservoir flow test, not a barrier test.
- **Replay:** from `backend/`, `direnv exec ../.. env -u PYTHONPATH OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --frozen python -m se.modeling.well_tracks`. The index pins 84 event packs, source hashes and the exact Smeaheia scenario receipt. Track release: `d92d14a3bce5e33d44fddec575a7e544ed392cbdb99d2dc39e64746b813bb5ca`.
- **API:** `/api/tracks/receipt` for provenance; `/api/tracks/search?scope=smeaheia&pa=true&limit=10` for a bounded list; `/api/tracks/wells/5839` for the exact-well evidence. Append `version=<track release>` to pin any read. Missing data do not fall back to another release.

## Horda demo build

- **`f46ffd5abca4`** is frozen locally, not deployed. It contains 186,538 model cells, porosity, a nearby legacy-well screen and IRAP/ZMAP+/GRDECL export. Parent probabilities are unchanged.
- The legacy-well layer uses proximity and end depth; it does not prove a well crosses a cell or leaks. CO2 storage and chance-of-success scores are not calibrated probabilities. The export is not simulator-ready.
- Smeaheia has no independently verified time-to-depth ties. Wellhead overlap is not a trace or trajectory tie. See the [control requests](../docs/seismic-data.md#depth-controls-to-request-first).
- The rock-physics template is diagnostic. In the complete measured-sonic cohort (21 wells), adding physics features to the same logs changed held-out porosity RMSE from **7.62 to 7.45 percentage points**; the paired 90% gain interval includes zero (**-0.04 to +0.33**). No probability model was changed.

On the machine that holds the snapshot, inspect or download it by build ID without changing the active build:

```sh
curl -fsS 'http://127.0.0.1:8461/api/earth/snapshot?region=pilot&build=f46ffd5abca4'
curl -fOJ 'http://127.0.0.1:8461/api/earth/export?region=pilot&build=f46ffd5abca4'
```

To rebuild the export and missing display products in scratch, run `uv run --frozen python -m se.earth.demo_bundle 16cbeadce9dd` from `backend/` with the original parent snapshot present. This creates a new immutable build without activating it. The datasets and snapshots are not bundled in Git.

## Development

- [Claude handoff](HANDOFF.md) · [Plan](PLAN.md) · [Append-only decision and experiment log](LOG.md) · [Agent rules](../.github/copilot-instructions.md)
- Backend tests: `cd backend && uv run --frozen pytest -q tests`.
- Read-only release checks: `/selftest.html?screen` and `/selftest.html?tracks`. The older `/selftest.html` suite also builds research targets; run it only against scratch data.
- Add evidence layers under `backend/se/evidence/` and sourced rules under `backend/se/knowledge/rules/`.
