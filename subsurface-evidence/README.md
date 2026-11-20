# Subsurface Evidence

A 3D evidence model for the Norwegian Continental Shelf. Horda Platform is the current pilot; Smeaheia is the demo focus. Select a well, horizon or cell to see the source and depth reference. **Strata Desk** uses the selected build and evidence in its answers.

## Run locally

Use the host with the local `data/` directory. From the repository root, run these in two terminals:

```sh
# Backend
cd subsurface-evidence/backend
uv run --frozen uvicorn se.api.main:app --host 127.0.0.1 --port 8460
```

```sh
# UI proxy
cd subsurface-evidence/ui
BACKEND_URL=http://127.0.0.1:8460 uv --project ../backend run --frozen \
  uvicorn serve:app --host 127.0.0.1 --port 8461
```

Open [Subsurface model](http://127.0.0.1:8461/#earth) and select **Explore Smeaheia**. The UI follows the active local build, or the legacy data when no build is active. Start the GPU worker only for GPU jobs (`nix develop .#gpu` from the repo root, then `ROLE=worker ./run.sh` from `subsurface-evidence/`).

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

- [Plan](PLAN.md) · [Append-only decision and experiment log](LOG.md) · [Agent rules](../.github/copilot-instructions.md)
- Backend tests: `cd backend && uv run --frozen pytest -q tests`.
- Browser checks: open `/selftest.html` through the local UI with the required data and receipts present.
- Add evidence layers under `backend/se/evidence/` and sourced rules under `backend/se/knowledge/rules/`.
