# PLAN: Smeaheia legacy-well evidence screen

Current question: **which Smeaheia wells have evidence of a reservoir or primary-seal encounter, and what still needs checking?**
This file is the working plan. Any agent (Claude, Copilot, a person) can pick up one task, do it, log it in `LOG.md`, tick it here.
Rules for working are in `../.github/copilot-instructions.md`. Read both before starting.

## Focus release (2026-11-20)

- [x] Open on an exact-borehole review queue for the GN1101 and TNE01 indexed wellhead footprints. Outside reference separate. Registry MD, sampled positions and sourced operational claims remain distinct (L084).
- [x] Test top Sognefjord against a well-only baseline on held-out wells. No gain, no new estimate published (L085).
- [x] Keep regional models and tools under Research. Verify the pinned receipt, browser interactions, unavailable-data path and existing Earth route without activating a build (L086).
- [x] Adapt Nature's Plug's interval rules to the exact Sognefjord borehole. Show measured support, pressure assumptions, continuous runs, formation context and missing inputs separately. No integrity prediction or neighbour transfer (L088).
- [x] Make every registry borehole searchable across all areas. Compare exact-well formation, placement and test records on depth tracks; keep Smeaheia as home (L089).
- [x] Add an optional exact-well rock + pressure overlay. Keep insufficient evidence and outside references explicit. Never colour by claimed integrity (L090).

Next evidence, not release requirements: obtain the exact `32/4-4` formation picks, directional surveys spanning the missing top depths, and interval-specific barrier-test records. Independent local seismic time-depth controls are still missing. Sleipner tie QC and wider regional model selection remain separate research.

## Historical regional plan (research, preserved): decisions from 2026-11-19, LOG L053

- **Model:** a 3D earth model of the NCS built from all extractable information, including assumptions from relations between data types. Every assumption explicit, sourced, tested.
- **Output per cell:** for each target, a calibrated **probability** and a **support** score (how much data, how close, how many independent sources agree). Two numbers, never one.
- **Area:** pilot first, then scale. Pilot = Horda Platform / northern Viking Graben, lat 59.5–61.5 N, lon 1.5–4.5 E.
- **Grid:** stratigraphic. Layers follow formation surfaces; each cell belongs to one formation.
- **Depth:** true vertical depth below sea level (TVDSS, metres, positive down). Measured depth only as an input.
- **Targets:** hydrocarbons, reservoir quality, overpressure / drilling hazard, CO2 storage suitability, green clay, calcareous clay, sandy delta.
- **Prior work kept:** everything through LOG L052 (GPT-6.2 via Copilot) is the base: one-assignment stratigraphy, EPSG:3035 distances, nested calibration, provenance catalog, source relations, log-to-core proof, GN1101 velocity model, seismic coverage audit, Strata Desk.

## 1. What the pilot holds (measured 2026-11-19, not estimates)

| Source | In pilot | Use |
|---|---|---|
| Wellbores (FactPages) | 3,932 (712 exploration, 3,220 development); 3,581 with TVD at TD | positions, datums, trajectories |
| Formation tops | 14,276 in 661 wellbores | structure |
| FORCE 2020 logs | 60 of 98 wells; X, Y, Z (TVDSS) per sample | true paths, lithology, properties |
| RealPore core | 148,711 rows, 461 wells | porosity, permeability truth |
| FactPages cores | 3,564 rows, 667 wells | where core exists |
| DST | 459 tests, 197 wells | fluids, pressure, temperature |
| Mud weights | 11,393, 598 wells | pore pressure upper bound |
| Casing + LOT | 2,627, 615 wells | fracture gradient |
| Report description lines | 57,993, 1,771 wells | lithology words, minerals, facies |
| Seismic | Smeaheia GN1101 + TNE01 (3 + 2 of our wells inside) | structure where tied |

Most-picked formations: Lista, Balder, Heather, Utsira, Sele, Draupne, Drake, Våle, Kyrre, Ness, Jorsalfare, Etive. Brent delta (Etive, Ness) and seals (Heather, Draupne) are well sampled.

## 2. Architecture

```
frame        true positions: trajectories, datums, tops in TVDSS            se/earth/frame.py
structure    stratigraphic column, surfaces + uncertainty, grid             se/earth/column.py, surfaces.py, grid.py
properties   lithology, porosity, permeability, pressure, temperature,     se/earth/props/*.py
             fluids, seal thickness: trend + spatial residual + sigma
relations    assumptions as tested rules (physics, correlations, facies)   se/knowledge/rules/earth.yaml
facts        report facts extracted by the local LLM, with page + quote    se/earth/facts.py
targets      definitions (YAML) -> probability + support per cell          se/earth/targets.py, targets/*.yaml
realisations Monte Carlo over surfaces and properties (GPU)                se/earth/mc.py
validation   blocked spatial CV, held-out wells, calibration               se/earth/validate.py
api + 3D     cells, isosurfaces, evidence chain per cell                   se/api/earth.py, ui/static/app.js
```

- Outputs: `data/subsurface-evidence/earth/pilot/` (git-ignored). Each artefact has a `.manifest.json`: inputs, SHA-256, code version, parameters, time.
- New package `se/earth/`. Reuse: `se/evidence/spatial.py` (EPSG:3035 km), `se/validate/cv.py` (blocked folds, deviance gain, bootstrap), `se/provenance/catalog.py`, `se/modeling/relations.py` (add every new relation there), `se/jobs/map_job.py` (GPU distance kernels).
- Pilot bounds go in `se/config.py` as `PILOT = {"lat": (59.5, 61.5), "lon": (1.5, 4.5)}`.

## 3. Shared protocol (every task)

- **Validate on held-out data.** Blocked spatial folds (40 km, EPSG:3035) and whole-well grouping. Report the metric, its 90 percent interval from resampling whole wells, and a baseline (constant, trend only, or formation mean).
- **A component goes into the model only if it beats its baseline** on held-out data. Otherwise keep it as context and say so.
- **Uncertainty is part of the output.** Every surface and property has a sigma; check that 90 percent intervals cover about 90 percent of held-out values (accept 85–95).
- **Assumptions are rules.** Add to `se/knowledge/rules/earth.yaml` with source, status (sourced / sourced_unverified / inferred) and a data test. Show the verdict.
- **Log it.** One `LOG.md` entry per finished task: Why, Method (exact command), Found (numbers), Decision, Tests.
- **GPU:** one LLM on the GPU at a time. Ask gpuctl (`gpuctl acquire <consumer>`); release after. Non-LLM GPU jobs go through the worker.

## 4. Phases and tasks

Status: `[ ]` open, `[~]` in progress, `[x]` done (with LOG id). Do phases in order; tasks inside a phase can run in parallel unless marked.

### P0 Housekeeping
- [x] **P0.1** Commit GPT-6.2's work (owner committed: hackathon-force 69d602d, homelab dae501a; L073). Browser test fixed (L054): 79 checks pass.
- [x] **P0.2** Restart the pod backend so it serves the corrected 2,286-unit artefacts (L047, L051). Verified in the pod: 2,286 units, 27,025 rows (L054).
- [x] **P0.3** Add `PILOT` to `se/config.py`; helper `in_pilot(lat, lon)`; test. (L055)

### P1 Frame: true geometry
- [x] **P1.1 Trajectories.** (L055) `se/earth/frame.py`: `trajectory(wellbore) -> MD -> (x, y, TVDSS, lateral_sigma)`.
  - Order of sources: FORCE 2020 X/Y/Z per sample (exact) > deviation surveys from reports (P5, later) > FactPages approximation.
  - FactPages approximation: vertical to kick-off point (development) or to the top of the well; below it TVD rises linearly to TVD at TD; azimuth unknown, so lateral position stays at the wellhead with `lateral_sigma = sqrt(dMD^2 - dTVD^2)`.
  - No TVD at TD: assume vertical, flag `vertical_assumed`, inflate sigma by a measured factor (from FORCE wells).
  - Accept: on the 60 FORCE pilot wells, predict TVDSS from the FactPages-only approximation and compare to FORCE Z; report RMSE and the 90 percent interval coverage of the sigma.
- [x] **P1.2 Datums.** (L055) TVDSS = TVD - KB elevation; seabed = water depth. Check per well: shallowest top vs seabed (L030 found 0.0 m median). Flag inconsistent wells; keep them visible.
- [x] **P1.3 Tops in TVDSS.** (L055) Convert all pilot tops (14,276) with sigma. Output `earth/pilot/tops.parquet` (+ manifest).
  - Accept: zero tops lost silently (diagnostics count every row); FORCE-well tops agree with FORCE Z within the stated sigma.

### P2 Structure
- [x] **P2.1 Column.** (L056) `se/earth/column.py`: ordered groups and formations for the pilot from FactPages `strat_litho_overview` and the NPD/Sodir lithostratigraphic lexicon (cite URLs). Allow absence (pinch-out, erosion). Output `column.json`.
- [x] **P2.2 Surfaces.** (L056, L057) `se/earth/surfaces.py`: one top surface per horizon on a 1 km lattice (EPSG:3035), by kriging / Gaussian process with a regional trend; model thin units as thickness (isochore) from the surface above; enforce order (no crossing). GPU for the GP solve where it helps (torch). Output depth + sigma per node.
  - Accept: blocked CV of held-out tops beats the trend-only baseline; 90 percent coverage 85–95 percent; zero order violations after conformance.
- [x] **P2.3 Seismic horizons (tied only).** (L058) Convert Smeaheia GN1101 interpreted horizons to depth with the L050 velocity model; add as soft data near the survey; compare CV with and without. Keep only if it helps held-out picks; otherwise context. Never use a surface derived from the same controls as an independent test (L049).
- [x] **P2.4 Grid.** (L059) `se/earth/grid.py`: stratigraphic grid, layers about 10 m thick (proportional between top and base), cell id (i, j, k, formation). Store as zarr or npz with coordinates.
  - Accept: no gaps or overlaps; per-formation volume reported; a cell round-trips to its formation.

### P3 Properties (trend + spatial residual + sigma, per formation)
- [x] **P3.1 Lithology.** (L063) FORCE expert lithofacies (train labels) per sample; a tree classifier from logs for unlabelled log wells; report-word lithology (`descriptions_text.parquet`) as a third, weaker source. Upscale to cell fractions.
  - Accept: held-out-well accuracy vs majority-class baseline; FORCE competition penalty matrix score reported. Never read the hidden test labels.
- [x] **P3.2 Porosity and permeability.** (L064) Apply the L046 tree (wins over MLP) to all log wells; density porosity as a physics baseline; compaction trend phi(z) = phi0 * exp(-c z) per lithology (rule, compared to Sclater & Christie 1980). Krige residuals.
  - Accept: held-out RealPore wells; beat both the formation mean and the compaction-only trend.
- [x] **P3.3 Pressure.** (L060) Hydrostatic reference (seawater gradient, sourced); DST pressures as direct pore pressure; mud weight as an upper bound (overbalance); LOT as fracture gradient. Map overpressure (excess over hydrostatic).
  - Accept: predict held-out DST pressures from mud-weight trends; report bias and spread.
- [x] **P3.4 Temperature.** (L062) DST temperatures (+ report BHT from P5 when available); geothermal gradient map with sigma.
- [x] **P3.5 Fluids.** (L065) Observations: DST oil/gas flow, FactPages well content and `wlbFormationWithHc1..3`, report shows (P5). One table of fluid observations per well and formation, with source.
- [x] **P3.6 Seal.** (L065) Seal thickness for Heather, Draupne and other shale-dominated formations from isochores and lithology fractions.

### P4 Relations as tested rules
- [x] **P4.1** (L066) `se/knowledge/rules/earth.yaml`: compaction (Athy), density-porosity, Gardner velocity-density, hydrostatic gradient, geothermal gradient range, Brent as a deltaic system (Etive, Ness), Draupne as source rock and seal, CO2 supercritical depth window, seal criteria. Each: source URL, status, data test, verdict. Register each in `se/modeling/relations.py` with a misuse guard.

### P5 Report facts (local LLM, GPU)
- [x] **P5.1 Cost first.** (L068, L072) Prefilter pilot pages by cheap rules (numbers with units near keywords). Run the extractor on 200 pages; measure tokens and time; log; decide the full run.
- [x] **P5.2 Extract.** (L072: run twice on the same pages, free JSON and schema-constrained; hand-checked precision 0.17 and 0.03; not adopted) Schema: wellbore, page, quote, fact type (show, porosity, permeability, lithology, pressure, temperature, deviation station, facies word), value, unit, depth, datum, confidence. One LLM at a time; Naija-Petro 8B extract profile is set up for bulk extraction.
- [x] **P5.3 Check.** (L072: precision measured on 100 hand-checked facts, 0.17; facts not adopted, as the acceptance requires) Hand-check 100 facts for precision; cross-check against FactPages (DST, cores) and FORCE logs. Facts enter the model only with a measured precision.

### P6 Targets and confidence
- [x] **P6.1 Definitions.** (L069) `se/earth/targets/*.yaml`, each a function of cell properties and observations:
  - hydrocarbons: fluid observations + reservoir quality + trap geometry (local closure on the reservoir top) + seal + source (Draupne) nearby.
  - reservoir quality: P(porosity > 15 % and permeability > 10 mD); cut-offs are parameters, logged.
  - overpressure: P(pore pressure gradient above hydrostatic by a set margin); also drilling window (fracture minus pore).
  - CO2 storage: depth in the supercritical window, reservoir quality, seal thickness, distance to wells; Smeaheia and Sleipner as real checks.
  - green clay, calcareous clay: report-text mention rates (existing targets) + lithology fraction (clay) per cell.
  - sandy delta: deltaic formations (rule) + sand fraction + report facies words (deltaic, delta front, mouth bar, distributary).
- [x] **P6.2 Realisations.** (L069) `se/earth/mc.py`: N realisations (start 100) of surfaces and properties from their sigmas; evaluate targets per realisation; probability = share. GPU (torch) for the per-cell evaluation.
- [x] **P6.3 Support score.** (L069) Per cell: data density within a radius, number of independent sources that speak, their agreement, distance to nearest well, held-out skill of each component. Defined in one function, documented, tested.
- [x] **P6.4 Calibration.** (L069) Held-out wells: reliability table per target; Platt or isotonic if it helps; state when a target has too few observations to calibrate.

### P7 3D and API
- [x] **P7.1 API.** (L070) `se/api/earth.py`: cells in a region, a target's probability and support, an isosurface, the evidence chain for one cell (observations, rules, distances, sources, realisation spread).
- [x] **P7.2 3D.** (L071) True well paths; stratigraphic grid; per target an isosurface at a chosen probability, opacity by support; click a cell for its evidence chain; seismic in depth only where tied. Keep the settings-left, information-right layout.
- [x] **P7.3 Tests.** (L071) Backend tests per module; browser checks in `ui/static/selftest.html` (unique variable names).

### P8 Scale
- [x] **P8.1** (L074) Repeat P1–P6 per region (North Sea south, Norwegian Sea, Barents); compare skill per region; never pool validation across regions without saying so.

### P9 Missing factors (owner, 2026-11-20)
Each factor is a rule in `earth.yaml` with a data test, and enters a model only if it beats the model without it on held-out wells (all four regions).
- [x] **P9.1 Source maturity (charge).** (L075) Depth and temperature of the source rocks (Draupne, Spekk, Hekkingen, Mandal, Tau) per column; share in the oil or gas window (T >= 100 C); distance from each cell to the nearest mature source. Feature for hydrocarbons.
- [x] **P9.2 Burial and quartz cement (reservoir).** (L075) Temperature above 70 C as a porosity driver (Walderhaug 1996); per-well net exhumation from the porosity-depth offset, mapped between wells, as effective burial. Compare held-out porosity error.
- [x] **P9.3 Old wells through the seal (CO2).** (L075) Count of wellbores penetrating each cell's unit within 2 km; a layer and part of the CO2 evidence.
- [x] **P9.4 Seabed temperature by water depth.** (L075) Replace the fixed 7 C (shallow cells only) by a water-depth relation.
- [x] **P9.5 Traps.** (L075) Distance to the nearest mapped fault (Sodir FactMaps, `data/sodir/factmaps`) and closure height on the unit's top surface (spill analysis). Features for hydrocarbons.
- [ ] **P9.6 Volve.** (L075: blocked, needs the owner: Databricks Marketplace account and the Equinor Open Data Licence) Second seismic tie in North Sea south from the Equinor Volve release (licence is the owner's decision).
- [x] **P9.7 Salt.** (L075) Zechstein thickness from the grid (North Sea south); test as a temperature and a hydrocarbon feature.
- [x] **P9.8 Oil or gas.** (L075) Split hydrocarbons into oil and gas targets (FactPages well content, DST rates).
- [x] **P9.9 Drilling bias.** (L075) State in the UI and report that probabilities are conditional on where wells are drilled.
- [x] **P9.10 Test forward in time.** (L075) Train on wells completed before 2005, test on later wells; per target and region.
- [x] **P9.11 Leakage guard.** (L075) Discovery and field outlines never enter features; a test enforces it.

### P10 Learn from Petrel, RMS, PetroMod, Trinity (owner, 2026-11-20)
- [x] **P10.1 Code review.** (L076) Read the earth modules for logic, architecture and speed; fix what is wrong; log what was found.
- [x] **P10.2 Fill-and-spill migration.** (L076) Per unit top: priority-flood drainage tree, oil from mature kitchen columns follows it up-dip, fills closures and spills on; charge reaching each cell (present and maximum burial). Candidate feature; must pass the held-out and forward-in-time tests.
- [x] **P10.3 Correlated realisations.** (L076) Monte Carlo draws as spatially correlated Gaussian fields (correlation length per input), not independent per cell; GPU (torch FFT) when free.
- [x] **P10.4 Porosity and CO2 capacity.** (L076) Porosity per cell (adopted P3.2 model); capacity = cell volume x sand share x porosity x CO2 density (NIST Span-Wagner table at the cell's T and P) x storage efficiency (NETL P10/P50/P90), summed per unit per realisation. Check against the Sodir CO2 Storage Atlas (`data/sodir/co2_atlas`).
- [x] **P10.5 Chance of success.** (L076) P(reservoir) x P(seal) x P(charge) x P(trap) per cell, the limiting element, and a held-out check against hydrocarbons; shown on the Earth page.
- [x] **P10.6 Other model families.** (L076) Logistic vs gradient boosting vs spline logistic (GAM-like) on the same folds and the forward-in-time test; a family is used only if it wins on both.
- [x] **P10.7 Export.** (L076) Surfaces as IRAP classic ASCII and ZMAP+; a zone-level corner-point grid (GRDECL) with target probabilities as properties; download from the API.
- [x] **P10.8 Docs.** (L076) Architecture notes and charts (docs/architecture.md, the Architecture page) updated for P9 and P10.
- [x] **P10.9 Depth without TVD.** (L076) Owner question (25/1-14 G drawn 10 km deep): 1,032 wellbores have no TVD in FactPages; sidetracks take their parent's TVD (median difference -58 m over 1,798 pairs), others the TVD/MD ratio of their class; sigma from the calibration spread. All regions rebuilt.
- [x] **P10.10 Strata Desk as an assistant.** (L076) The assistant reads the model's own evidence (method and skill, the selected cell, tested rules, a named well's depth source, a named unit's observations) and answers in sections: sources, model, reasoning with assumptions, uncertainty, checks. Works on the model page (scene accepted).
- [x] **P10.11 One subsurface model page.** (L076) Earth model and 3D merged as "Subsurface model": seismic sections and the inspector, tied horizons, what each well found at vertical depth, formation tops, map layers, all regions side by side, presets and remembered settings. The Target builder's saved-target sheets stay as a sub-view (depth along the hole).
- [ ] **P10.12 Saved targets at vertical depth.** Convert the saved-target sheets and sticks to TVDSS with the frame, then fold them into the model page as a layer and retire the sub-view.
- [ ] **P10.13 Cleaner filters on the other pages.** The model page sidebar is revamped (sections, descriptions, swatches, presets); Targets, Units and Validation still have their older controls.

### P11 Rock physics (owner, 2026-11-20)
- [x] **P11.1 Rock physics template on the FORCE wells.** (L077) Friable sand and contact cement with Gassmann brine, oil, gas; cement index and fluid signal per sample; tests R-RPT-CEMENT (agrees, pooled) and R-RPT-FLUID (not testable); view under Subsurface model.
- [ ] **P11.2 Shear velocity where missing (deferred).** Greenberg-Castagna Vs could extend display coverage if validated against measured shear logs. It adds no independent fluid or cement labels; do not use it to rescue the fluid test.
- [x] **P11.3 Test physics against measured core.** L081 compares fixed density porosity, raw logs and the same logs plus physics on held-out blocks. No reliable incremental gain; retain the template as a diagnostic only.

### P12 Close the gaps an expert would raise (owner, 2026-11-20)
- [x] **P12.1 Sensitivity of untested constants.** (L089) Each constant without a data test (kernel lengths, shrinkage counts, selection margin, oil-window temperature, trap floor, NTG and thickness sigmas, storage efficiency, support constants, correlation lengths) set low and high; what moves: held-out gain, published form, CoS test, CO2 totals, support. A tornado table per region.
- [x] **P12.2 Physical inputs refitted inside each fold.** (L089) Temperature, porosity trend, burial and the maturity factors fitted without the held-out wells; gain compared with the shared fit. Surface-based features: show whether any published model uses them.
- [x] **P12.3 Coefficient uncertainty.** (L089) Cluster-bootstrap refits (whole wells) combined with the input Monte Carlo; how much wider the 90 percent ranges get.
- [x] **P12.4 Versioned artefacts.** Freeze an idle regional build, verify dependencies and cell order, then switch one pointer. The 3D view, cell lookups, export and Strata Desk use the same snapshot. Legacy regions remain mutable; Horda activation is a separate release step. See L078.
- [x] **P12.5 Verify sources.** (L089) Every sourced_unverified reference resolved (Crossref for DOIs, the page for URLs): title, authors and year checked; status raised to sourced only with a quote read from the source.
- [x] **P12.6 Complete the frozen Horda demo locally.** L082 restores porosity, the legacy-well screen and versioned export in `f46ffd5abca4` without changing probability arrays. Activation is a separate release step.
- [x] **P12.7 Audit Smeaheia by borehole and measured depth.** L080 inventories local curves, plugs, bounded core–log pairs and report/pick references; missing controls remain explicit in 3D.
- [ ] **P12.8 Verify independent Smeaheia ties (external controls required).** Obtain original checkshots/VSP, directional surveys and processing datums; resolve the T2 and TNE01 identities and depth/time references. Reserve independent holdouts before fitting. See the [acquisition list](../docs/seismic-data.md#depth-controls-to-request-first).

## 5. Done for the pilot

- Frame, structure and at least three properties pass their acceptance tests.
- All seven targets have probability + support per cell, with calibration tables (or a stated reason why not).
- Every number in the 3D view traces to sources and rules; every assumption has a verdict.
- `LOG.md` has one entry per task; tests pass; the pod serves the result.

## 6. How to run (reference)

- Backend tests: `cd subsurface-evidence/backend && uv run --frozen pytest tests -q`
- Local servers: `ROLE=backend ./run.sh` (8460), `ROLE=ui ./run.sh` (8461)
- Browser test: `chromium --headless --dump-dom --virtual-time-budget=1500000 http://127.0.0.1:8461/selftest.html`
- GPU work: `nix develop ..#gpu` (from `hackathon-force/`), then `uv run --frozen --extra gpu ...`
- Pod: namespace `subsurface-evidence`; code is read from disk; `kubectl -n subsurface-evidence rollout restart deploy/backend` reloads Python.

### P13 Nature's Plug in the model (owner, 2026-11-20)
- [x] **P13.1 Run Jeham's engine unchanged and join it.** (L091) Green Clay surface on our surfaces tested at his 29 sites; his formation-level and nearest-well verdicts by region; his barrier cases; page #jeham.
- [ ] **P13.2 Green Clay held out.** Refit his relation leaving a field out on our surfaces, with a datum correction from each well's rig floor, before using it as an input anywhere.
