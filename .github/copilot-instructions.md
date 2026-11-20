# Instructions for coding agents in this repo

Main project: `subsurface-evidence/` (NCS earth model with targets and confidence). Start with `subsurface-evidence/PLAN.md`, then the latest entries in `subsurface-evidence/LOG.md`.

## How to work

- Pick one open task in `PLAN.md`, mark it `[~]`, finish it, mark it `[x]` with its LOG id.
- Never guess. Measure, cite a source, or ask the owner. If unsure, ask before building.
- Log every decision and finding in `LOG.md` (append-only, next `L###`): Why, Method (exact command), Found (numbers), Decision, Tests. Wrong turns stay, marked `[wrong, kept]`.
- Hide nothing: show counts, intervals, baselines, exclusions and failures, in the app and in the log.
- Validate on held-out data: blocked spatial folds (40 km, EPSG:3035) and whole-well grouping, with a baseline and a 90 percent interval from resampling wells. A component is used only if it beats its baseline.
- Assumptions are explicit rules with a source and a data test (`se/knowledge/rules/*.yaml`), registered in `se/modeling/relations.py`.
- Every output artefact gets a manifest (inputs, SHA-256, parameters, code version).

## Style

- Docs and comments: brief, single-line where possible, plain words. No em-dashes, no filler.
- Match the surrounding code. Tests for every new module (`backend/tests`), browser checks in `ui/static/selftest.html` with unique variable names.

## Limits

- Only the owner commits and pushes. Do not run git commit or git push.
- One LLM on the GPU at a time; get the GPU through gpuctl and release it. Small models (<10B) may run on CPU.
- Do not read the FORCE 2020 hidden-test labels. Do not treat a benchmark's gold answers as search results or truth.
- Licences: credit Equinor and Gassnova wherever Smeaheia or Sleipner data is shown; no reselling.
- In `hackathon-force`, use the flake dev shell; never run `nix ... path:.` (it copies the 125 GB data folder into the store).
- Cluster changes (applying manifests) need the owner's go-ahead; restarting the `subsurface-evidence` pods to load new code is allowed.
