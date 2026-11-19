# Subsurface Evidence

Evidence engine: layers of data -> log-odds -> a calibrated, explained estimate. First target: green clay in NCS clay rows.

- **Decisions + numbers:** `LOG.md` (append-only, also in the UI).
- **Run local:** `ROLE=backend ./run.sh` (8460), `ROLE=ui ./run.sh` (8461), GPU: `nix develop ..#gpu`, `ROLE=worker ./run.sh`.
- **Rebuild data:** `cd backend && uv run python -m se.ingest.units && uv run python -m se.ingest.logs && uv run python -m se.validate.cv`.
- **Tests:** `cd backend && uv run pytest tests`.
- **Add a data type:** write a Layer (`se/evidence/base.py`), register it in `se/evidence/__init__.py`.
- **Add a rule:** `backend/se/knowledge/rules/*.yaml` (source + status mandatory).
- **Deploy:** `deploy/subsurface-evidence.yaml` is a DRAFT, not applied.
