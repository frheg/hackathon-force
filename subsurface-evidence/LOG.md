# Subsurface Evidence: research and decision log

Append only. Newest last. One entry per step. Every number here can be rebuilt with the command in its `Run:` line.
Format: **Q** question, **Did** what, **Found** result, **Decision** what we chose, **Why** reason, **Refs** sources.
Status tags: `[done]` `[open]` `[wrong]` (kept, never deleted: a wrong turn is data too).

---

## L001 Goal and scope [done]
- **Q** Can one tool combine all our data types, known rock rules and geological history into a probability with reasons?
- **Decision** Build it. First slice: *green clay* (glauconite, chlorite, nontronite, celadonite, green clay) in North Sea wells. Everything else plugs into the same frame.
- **Why** Green clay has a text label set we already extracted (`docs/greenclay.md`), known log physics (K, Fe), a named stratigraphic marker, and drilling and log-interpretation value.
- **Not claimed** "All known knowledge" cannot be encoded. We encode only sourced, testable rules, and let data decide the rest.

## L002 Name [done]
- **Decision** `subsurface-evidence`. Literal: it turns subsurface evidence into a probability.
- **Why** User asked for a literal, descriptive name without branding.

## L003 Architecture [done]
- **Decision** Pipeline of swappable modules: `ingest` (data to tables) > `evidence` (one module per data type, each returns a log-likelihood ratio) > `knowledge` (sourced rules, checked against data) > `infer` (combine and calibrate, per-layer contributions kept) > `validate` (blocked folds, ablation) > `api` > `ui`. A new data type or target is a new module or a new rules file, not a rewrite.
- **Why** Needs to grow to seismic, SAR and other targets. Additive log-odds keeps every contribution visible ("hide nothing").
- **Rejected** One end-to-end network (no per-source reasons, weak labels, few wells); a hand-written expert system (brittle: the 1980s lesson).

## L004 Hosting and GPU [done]
- **Facts** (homelab docs/gpu-arbiter.md) One GPU holder at a time. A GPU workload is a `gpuctl` consumer; while it holds, the LLM is scaled to 0. Existing hackathon pod: runtime image, repo mounted from disk, namespace per app.
- **Decision (user, 2026-11-19)** CPU API and UI always on. A separate GPU worker Deployment, a gpuctl consumer, scaled to 0 and started only for heavy jobs. Pods use the disk-mounted runtime, like the hackathon pod.
- **Why** The LLM stays up except during a job. Live edits during the event. No image digests to maintain.
- **Open** Applying manifests to the cluster is an infra change: drafted in `deploy/homelab/`, not applied until the user says so.

## L005 Prior art [done]
- **Q** Is this already done?
- **Found** Pieces exist apart: physics-informed ML reviews (Sun 2021; Latrach 2024), play fairway / common risk segment maps (reservoir, seal, source overlay; scoring is often subjective), Bayesian neural nets with confidence for a geothermal fairway (Nevada), LLM-built geoscience knowledge graphs (2025; a 2025 review says efforts stay separate), multi-mineral log solvers, geostatistics. No open system found that gives one probability from many data types with reasons and contradiction checks.
- **Decision** Our contribution is the combination plus visible reasons plus tested rules, not any single method.
- **Caveat** Search snippets only; absence of a paper in one search is not proof it does not exist.
- **Refs** arxiv.org/abs/2104.04764; arxiv.org/abs/2308.04457; exprodat.com/?p=27561; pubs.usgs.gov/publication/70241433; mdpi.com/2624-795X/7/2/40

## L006 Knowledge sourcing [done]
- **Q** What do we know, with a source, about green clay in logs?
- **Found (sourced, direction only)** Glauconite is a K-bearing mica, so spectral K and gamma ray rise; chlorite has no radioactive elements, so it is gamma-quiet, Fe-rich, with high neutron response and low resistivity; iron-rich greensand clays disturb conventional log models (paramagnetic, conductive); PEF follows mean atomic number, so Fe shifts it (inferred from physics, no number found). Balder is "grey, green and buff tuffs"; Lista starts at "green-grey bioturbated mudstones" (Norwegian lexicon).
- **Found (not available)** Numeric matrix values (density, PEF, neutron, K%) for glauconite and chlorite: Crain's tables are behind a paid login; snippets gave none. The informal North Sea unit "Green Clay" was not confirmed in a source, although our reports show "Top Green Clay" picks in 573 wells.
- **Decision** Rules file holds only directions with sources; numeric effects are *learned* from data, then compared with the direction. Disagreement is shown in the UI, never hidden. Missing numbers are marked `needs_source`.
- **Why** Never guess a number. Testing a rule against data is a result in itself.
- **Refs** spec2000.net (login), mdpi.com/2075-163X/15/12/1280, nhm2.uio.no/norges/litho/{balder,sele}.php, en.wikipedia.org/wiki/{Glauconite,Chlorite_group,Nontronite,Celadonite}

## L007 Target definition [done]
- **Decision** Target = "a report says green clay family is present in this unit" (a *reported* presence), not true presence. Family = glauconite, green clay, chlorite, nontronite, celadonite (editable per run).
- **Why** Labels are text mentions. Treating them as truth would hide the noise. The model estimates P(reported); the gap to truth is stated on every screen.

## L008 Unit of analysis [done]
- **Decision** Unit = wellbore x formation interval (FactPages tops, measured depth). Label from description rows whose depth falls inside it.
- **Why** Text depths are measured depth and sparse; a formation interval is geologically meaningful, holds many rows, and joins to logs (same depth axis) and maps (well position).
- **Rejected** Per-metre labels (too noisy and sparse); per-well labels (loses the stratigraphy).

## L009 Negatives [done]
- **Decision** Negative = unit with at least 3 description rows (rock description with a depth) inside it and no green-clay mention. Fewer rows = unlabelled, not negative.
- **Why** Absence of a mention means nothing where nobody described the rock. Coverage makes "no mention" informative. Known cost: fewer negatives.

## L010 Unit table built [done]
- **Run:** `cd backend && uv run python -m se.ingest.units`
- **Found** 41,354 formation/group intervals in 2,054 wellbores (FactPages tops, measured depth, inside the well). Labelled 12,976 units (16.9 % positive) in 1,342 wellbores. Coverage rows: 203,763 rock-description rows in 4,118 wellbores (extractor `app/sketches/greenclay.py`, 3.4 % of rows name a green mineral).
- **Sanity (knowledge vs data)** Positive rate by unit: Hordaland Gp 28 % (n 887), Shetland Gp 23 %, Cromer Knoll Gp 19 %, Lista Fm 18 %, Rogaland Gp 17 %, Nordland Gp 15 %, Heather Fm 8 %, Viking Gp 9 %, Brent Gp 2 % (n 198). Marine, condensed Paleogene highest; non-marine Brent lowest: as expected geologically. Not a proof; it is a check that the labels are not random.
- **Depth fix:** description rows have no unit; a depth beyond the well's total depth is read as feet (/3.28), else dropped.

## L011 Spatial test reused [done]
- **Decision** Same method as the earlier depth test: blocked folds of 40 km (hide a block, predict it), not random folds.
- **Why** Wells cluster in fields; random folds flatter the score (measured earlier: Utsira top error 46 m random vs 62 m blocked).

## L012 Log features [done]
- **Run:** `uv run python -m se.ingest.logs`
- **Found** Only 2,142 units in 106 wellbores have logs; labelled: 908 units (13.1 % positive) in 93 wellbores = 7 % of the labelled set. Logs are a *small-sample* layer. Median positive vs negative unit: GR 69.5 vs 73.7 (lower, opposite to the K rule), DTC 109 vs 95 us/ft (slower), RDEP 0.12 vs 0.26 log10 ohm.m (lower), RHOB 2.35 vs 2.39, PEF 4.3 vs 4.4.
- **Reading** Slow sonic, low resistivity, low density in positives is what shallow, less compacted rock looks like. Green clay sits shallow, so raw log values mostly measure *depth*, not mineral. **Confounding.**
- **Decision** The log layer uses anomalies against the formation's own typical value (training medians, robust scale), so burial depth and formation are removed before looking for a mineral signal. Raw values would give a good score for the wrong reason.
- **Assumption** Density-neutron separation uses matrix 2.65 g/cc, fluid 1.0 g/cc (sandstone, fresh water). A shale-rich unit is not a sandstone: the number is an index, not porosity.

## L013 First validation, v0 target "any mention in the unit" [wrong, kept]
- **Run:** `cd backend && uv run python -m se.validate.cv` (43 s; blocked 40 km folds, 5 folds, whole-well bootstrap)
- **Found** AUC (12,976 labelled units): formation only 0.625; + spatial 0.636 (gain +0.011, 90 % CI 0.001..0.022); logs: on the 908 units with logs formation-only 0.633, + logs 0.593 (**logs hurt**, -0.039, CI -0.081..0.001). Raw probabilities overconfident: Platt slope 0.49 (top decile predicted 0.40, observed 0.27).
- **Found** Spatial gain depends on distance to the nearest same-formation training unit: 0-5 km AUC 0.71 (vs 0.68 formation only), 5-15 km 0.66, 15-40 km 0.62, 40-100 km 0.54, >100 km 0.52. The neighbours inform within about 15 km and nothing beyond 40 km.
- **Found** Within a formation the model barely ranks units (Heather 0.36, Naust 0.41, Lista 0.46, Hordaland 0.60).
- **Found (the big one)** Positive rate by description rows in the unit: 3-4 rows 5.6 %, 5-7 10 %, 8-12 14 %, 13-25 22 %, 26-60 33 %, >60 70 %. **The label measures how much was described, not only the geology.** A unit with 60 described rows has far more chances to name a green mineral than one with 3. Any model scored on this label is partly scored on reporting effort.
- **Decision** Change the target from "any mention" to a *rate*: green rows out of described rows (a binomial: each described row is a trial). Effort is then the number of trials, not a hidden driver. Score with held-out binomial deviance and with AUC *inside* coverage bins, not pooled. See L015.
- **Why** Same logic as occupancy models in ecology (presence vs detection effort; MacKenzie 2002). Cheaper and more honest than guessing a detection curve.

## L014 Sweeps on v0 (before the change) [done]
- Spatial length ell 5/10/20/40/80 km: AUC 0.633/0.631/0.636/0.636/0.632: flat. Formation smoothing a 2/10/30: 0.624/0.625/0.623: flat.
- **Reading** The result is not sensitive to these two knobs. Defaults 20 km and 10 stay. Re-run under the rate target (L015) before trusting them.

## L015 Target v1: rate of green rows among described rows [done]
- **Run:** `uv run python -m se.validate.cv` (37 s). Binomial: each described row is a trial; metrics = held-out binomial deviance gain and AUC *inside* coverage bins.
- **Found** Effort is out of the score. Formation only: deviance gain 2.3 %, AUC in coverage bins 0.628; + spatial: 3.0 %, 0.643 (spatial gain +0.0067, 90 % CI 0.0018..0.0118, significant). Logs on the 908-unit subset: -0.006 (CI -0.033..0.021, not significant). By distance to the nearest same-formation training unit: gain 0-5 km 0.129 (formation-only 0.077), 5-15 km 0.050 (0.034), 15-40 km 0.012 (0.017), 40-100 km 0.018, >100 km 0. Spatial evidence helps within about 15 km and not beyond.
- **Found** Raw rates are overconfident: Platt slopes 0.48-0.61 (rows of one rock are not independent trials; expected). Calibration is part of the pipeline, not optional.

## L016 Hyperparameters by measurement [done]
- Sweeps, each a full blocked CV: spatial ell 5/10/20/40/80 km: gain 0.0275/0.0296/0.0298/0.0277/0.026 -> **20 km**. Formation smoothing a 10/30/100/300/1000 rows: 0.0215/0.0232/0.0246/0.0250/0.0234 -> **300**. Neighbour weight k 3/10/30/100 rows: 0.0268/0.0299/0.0311/0.0308 -> **30**. All flat near the optimum: the result does not hinge on them.
- **Logs got a fair trial:** regularisation C 0.01..1: delta vs formation-only -0.0003/-0.0021/-0.0046/-0.0061/-0.0067, every CI spans 0. No setting helps. At the strongest shrink (C 0.01) the layer is switched off, which is the best it can do.
- **Caveat** Sweeps were chosen on the same folds that report the score: optimistic by a small amount; the plateau suggests it is small.

## L017 Spatial layer fades with distance [done]
- **Reading** The layer adds nothing beyond ~15-40 km, and at 15-40 km it is slightly worse than formation-only. Use: show the nearest-neighbour distance next to every spatial effect so a user can discount it. A distance-aware weight (instead of one ell) is a candidate improvement, not yet tested.

## L018 Do logs see green at the row level? [done]
- **Run:** `cd backend && PYTHONPATH=. uv run python ../scripts/exp_row_logs.py`
- **Q** The unit layer found no log effect: is the signal diluted by taking one median over a whole formation?
- **Found** 4,767 description rows with logs in 95 wells; 144 name a green mineral (3.0 %). Univariate AUC of the formation-relative anomaly: GR 0.62 (higher in green rows, as the K rule says), PEF 0.37 (**lower**; the inferred Fe-raises-PEF rule is NOT supported), RDEP 0.43 (lower: matches the low-resistivity note), NPHI 0.46, RHOB 0.53, DTC 0.49. Leave-wells-out AUC: formation 0.54, depth 0.59, **log anomalies 0.65**, gradient boosting on raw logs 0.65. So logs carry a row-level signal that the unit median hid.
- **Suspicion** Green mentions sit mostly in claystone rows, and claystone is high-GR, low-PEF anyway. The signal may be *lithology*, not *mineral*. Needs a within-claystone test (L019, L020).

## L019 Lithology confound and the clay target [done]
- **Found** 54 % of "description rows" were not rock descriptions (`other`: core and sample headers; 0.3 % green). Among real rows: clay 8.5 % name a green mineral, sand 5.7 %, carbonate 4.2 %. Mixing lithologies makes the label partly a lithology label.
- **Decision** Target = share of described **clay** rows (claystone, shale, mudstone, marl) that name a green mineral. Rows of other lithologies are not trials. Lithology is out of the label by design (`TARGET["lith"]` in `se/config.py`; set `("sand",)` for glauconitic sand).
- **Effect** Labelled units 12,976 -> 3,762 (752 wellbores); 49,961 clay rows, 3,032 green (6.1 %). Units with logs and a label: 230 in 45 wells. Smaller, cleaner.
- **Rejected** Keeping all lithologies and adding lithology as a feature: lithology is read from the same report text, so it is not independent of the label.

## L020 Row-level logs within one lithology [done]
- **Run:** `cd backend && PYTHONPATH=. uv run python ../scripts/exp_row_logs.py clay` (and `sand`)
- **Found** Within claystone rows (988 rows, 73 wells, 58 green): leave-wells-out AUC formation 0.566, depth 0.502, **log anomalies 0.482 [0.404, 0.649]**, gradient boosting on raw logs + depth 0.629 [0.561, 0.712]. Logs minus formation: -0.085 [-0.139, 0.082]. Within sand rows (890 rows, 59 green): anomalies 0.480 [0.317, 0.670]; boosting 0.622 [0.495, 0.701]. Univariate GR AUC 0.585 (clay), 0.570 (sand): higher in green rows, as the K rule says, but small. PEF 0.52 (clay), 0.40 (sand): the Fe-raises-PEF rule is not supported.
- **Reading** The earlier row-level 0.65 (L018) was mostly lithology (a claystone row is likely to be described green). Inside one lithology the linear anomaly model has no detectable skill. A boosting model on raw values reaches 0.63 with a lower bound above 0.5 in clay: some nonlinear or depth-linked signal may exist; it cannot be separated from depth and formation with 58 positives.
- **Decision** Keep the log layer in the frame, report it as **not shown to help**, and let the UI say so. Do not switch it on in the combined probability unless blocked CV shows a gain with an interval above 0.
- **Needs** Spectral gamma (K, Th, U) and more wells with both description rows and logs. FORCE logs have 106 wells; most description rows lie in wells without open logs.

## L021 Sweep bug [wrong, fixed]
- **What** The spatial-weight sweep passed `k=`, which `oof()` also used as the number of folds: the sweep ran 3/10/30/100 folds, not pseudo-rows. A mismatch between the sweep point (gain 0.0200) and the default ablation (0.016) exposed it.
- **Fix** Fold parameter renamed `n_folds`. The invalid numbers were never used for a decision.
- **Lesson** Re-run the same configuration two ways before trusting a table.

## L022 Results on the clay target (current) [done]
- **Run:** `cd backend && uv run python -m se.validate.cv` (42 s). 3,762 labelled units, 752 wellbores, 49,961 clay rows, 6.1 % name a green mineral. Blocked 40 km folds.
- **Found** Formation only: deviance gain 1.4 %, AUC in coverage bins 0.603. + spatial: 1.6 %, 0.598; spatial vs formation +0.0014 [-0.002, 0.0041] **no evidence of help**. Logs on the 230 units that have them: -0.036 [-0.077, -0.013] **hurts**, and at the strongest shrink (C 0.01) still -0.0135 [-0.026, 0.000]. Sweeps are flat: ell 5..320 km gain 0.013-0.016; a 3..300 rows 0.013-0.014; k 3..100 rows 0.0153-0.0157. Platt slopes 0.44-0.71: raw rates overconfident about 2x.
- **Reading** With lithology removed from the label, what remains predictable is small: formation tells a little, neighbours and logs tell nothing measurable *yet*. Earlier, larger numbers (L013, L015) were partly lithology and effort. The honest headline: **the frame works and measures itself; this target has weak signal in the data we hold.**
- **Decision (P1, layer policy)** A layer is ON in the served estimate unless blocked CV shows it significantly hurts (interval entirely below 0). Status is always shown: `helps` / `no evidence` / `hurts`. The user can switch any layer on or off and see the change. Now: formation ON (helps), spatial ON (no evidence), logs OFF (hurts), seismic OFF (not built).
- **Defaults kept** a 30 rows, k 30 rows, ell 20 km: inside the flat plateaus, so the choice does not matter; stated, not tuned.

## L023 What would make it better [open]
- More labelled units with logs (spectral gamma: K, Th, U), a second independent source of mineral evidence (cores, XRD), seismic, and the named *Green Clay* marker as a second target (573 wells, 630 labels with a top depth). Each is an evidence module or a target, not a rewrite.
- A hierarchical model (formation x area random effects) instead of separate layers, if the layers stay near zero.

## L024 Knowledge base checked against data [done]
- **Run:** `cd backend && PYTHONPATH=. uv run python ../scripts/exp_row_logs.py clay|sand` then `uv run python -c "from se.knowledge import kb; print(kb.check())"`
- **Found (AUC of the formation-relative anomaly, green vs not, 90 % CI resampling whole wells)**
  - K-GR (sourced): clay 0.58 [0.50, 0.70], sand 0.57 [0.47, 0.63] -> **agrees**, weakly (interval touches 0.5).
  - Fe-RDEP (sourced): sand 0.40 [0.33, 0.45] -> **agrees** (iron-rich clays are conductive: lower resistivity); clay 0.50 [0.40, 0.56].
  - Fe-PEF (*inferred*, no source): sand 0.40 [0.34, 0.50], clay 0.52 [0.44, 0.62] -> **disagrees** with "raises PEF": green rows have lower PEF in sand. The inference is withdrawn as a prior; kept in the file with its verdict.
  - Chl-NPHI (sourced_unverified): clay 0.40 [0.32, 0.55] -> inconclusive.
  - Strat-Lista-Sele (sourced): Lista 8.7 % [5.8, 11.7] (114 wells) vs Sele 8.0 % [3.9, 12.4] (76 wells) -> inconclusive.
  - Strat-Balder (sourced): Balder 4.8 % [3.0, 6.8] vs overall 6.1 % -> inconclusive (not higher).
- **Caveat** Seven checks per lithology, 90 % intervals: about one false hit is expected by chance. 58-59 green rows per lithology. These are leads, not laws.
- **Why this matters** The rules came from literature and physics; the data agree on two, contradict one, and are silent on the rest. That is the point of keeping the knowledge base separate from the model: knowledge is tested, not trusted.

## L025 GPU map job [done]
- **Run:** `nix develop .#gpu`, then `cd backend && uv run python <test>`: same grid on cpu (numpy) and cuda (torch 2.11 cu128, RTX 5060 Ti, 33 MiB peak).
- **Found (bug, fixed)** First cuda run differed from cpu by up to 0.43 logit. Cause: float32 distances at about 6,600 km from the equator, plus torch's matrix-multiply shortcut for `cdist`. Fix: centre coordinates on the units and use exact distances. After: max diff 1.3e-6 (to 1.3e-2 at 4.2 M cells, float32 sum order).
- **Speed (HORDALAND GP, 351 units)** 0.02 deg: cpu 3.7 s, cuda 0.39 s. 0.01 deg: 14.7 s vs 1.56 s. 0.005 deg: 65 s vs 6.3 s. About 10x.
- **Reading** The GPU worker is worth it only for fine maps; the coarse map runs fine on CPU. The worker stays on-demand (L004).

## L026 Scaffold complete, local only [done]
- **Built** backend API (`se/api`), GPU worker, UI (`ui/`, own server + /api proxy), knowledge base, tests (7 pass incl. cpu==cuda), `run.sh`, docs.
- **Checked** UI pages screenshotted in headless Chromium; the map overlay bug (added before the map had a view) found and fixed.
- **Not done** Cluster deploy: `deploy/subsurface-evidence.yaml` is a draft. Open: GPU image with torch, gpuproxy, NetworkPolicy for backend->worker, profctl/panel tile. Needs the owner's go-ahead.
- **Ports** 8300/8301 are in use on kratos; this project uses 8460/8461/8462.

## L027 Scope widened: supertool [decided by user]
- **Ask** (user): "more interactive, not only green clay specific ... a supertool squeezing out all information from all data we have" and "run me through what the data is".
- **Choices (user, via question)** Direction: target builder + explorer. Data to squeeze, all four: report text (all facts), FactPages (all tables), seismic as a layer, DiskosQA search.
- **Inventory (measured 2026-11-19)** Completion reports 4,462 PDFs, 112 GB, text 5.7 GB (used: green words only). FactPages 22 tables (used: tops + positions). FORCE 2020 logs 106 wells, 28 cols (used: log layer, hurt). Seismic F3, Penobscot, Parihaka, FaultSeg3D, ADELE 8.6 GB (unused, no cube over our wells). DiskosQA 12 MB (unused). RealPore, KSAT, Volve: unused.
- **Plan (phases, each logged and tested)**
  1. Data catalog + table explorer with cross-filter (this entry). Structured, no model.
  2. Target builder on structured data: pick a table + condition -> per-unit counts -> same engine, validation and explanations.
  3. Report text facts: keep the TEXT of description rows (descriptions.parquet has only flags now), so any keyword or fact is a target. Needs a re-extraction; the one used for green clay did not store text.
  4. Seismic layer: only for wells inside a cube. None of ours are (F3 is Dutch sector); decision needed on which cube/area.
  5. DiskosQA search next to the evidence.
- **Constraint** The engine models a share (successes / trials) per unit. Continuous targets (porosity, mud weight) need another likelihood: a new Target type, not a rewrite.

## L028 UI redesign, 3D explorer, hotspots, data explorer [done, phase 1 of L027]
- **UI** Rebuilt: design tokens, dark/light, icon rail, a "what you are looking at" box on every page, Plotly charts instead of JSON (validation, evidence waterfall, layer weights).
- **3D explorer** Wells as vertical segments (MD, not TVD), per-formation estimate sheets (kernel-smoothed depth, masked beyond 60 km), hotspot boxes, region filter (the shelf spans 58 to 74 N, so all-shelf is unreadable).
- **Hotspots** 20 km windows vs formation rate. Plain binomial gave p about 1e-20 (rows in one unit are correlated): scaled by Pearson dispersion phi (1 to 5.5) and Bonferroni over windows. Result: 4 of 16 survive (adj p < 0.05); several are on wells described 1.5 to 2x more than average (reporting effort), and the text says so. Exploratory, not a prediction (the spatial layer showed no out-of-sample gain, L022).
- **Data explorer** Catalog with origin of every dataset; any FactPages table: columns profile, rows, chart (click bar = filter), map.
- **Not tested in a browser** Explorer clicks (table pick, bar-click filter); the API calls behind them were tested with curl. Fine-map button against a live GPU worker.
- **Bug** Plotly cdnjs URL 404 (wrong path); moved to jsdelivr `plotly.js-dist-min@2.35.2`.

## L029 Target builder (phase 2) [done]
- **Design** A target is a recipe (table, population filters, success filters, mode well|interval) that builds the SAME unit table the engine already reads (trials -> `coverage`, successes -> `n_green`; names kept so layers and validation run unchanged). Mode well: one unit per wellbore, group column plays "formation". Mode interval: rows of DST, mud, core or casing tables fall into well x formation intervals by depth. Same recipe, same id (title not part of it).
- **Guard** Refuses with fewer than 200 labelled units, 20 successes or 40 wells (tested). Validation is `cv.run(quick=True)`: no sweeps, no log layer (its columns are empty, so it stays silent). Coverage bins for the in-bin AUC are adapted per mode.
- **Results (held-out 40 km blocks, 90 % ranges from resampling wells)**
  - Wildcat well found oil or gas: 1,436 wells, 45.7 % base. Area prior +0.0171 [0.0077, 0.0272] helps; neighbours -0.0011 [-0.0149, 0.0112] no evidence.
  - DST flowed oil: 1,430 units, 2,356 tests, 69.7 %. Formation +0.0240 [0.0077, 0.0369] helps; neighbours +0.0019 [-0.0004, 0.0044] no evidence.
  - Heavy mud (> 1.6 sg): 18,235 units, 63,704 measurements, 26.3 %. Formation +0.1926 [0.1687, 0.2105]; neighbours +0.1149 [0.0988, 0.1293]. Large, but mud weight mostly follows depth and the pressure regime, so the formation largely stands in for depth: a strong score, not a geological discovery.
- **Reading** The engine generalises; the green-clay result (small skill) is a property of that target, not of the engine. Targets with a physical driver (mud weight, depth) score high.
- **Open** Continuous targets (porosity, mud weight as a number) need another likelihood. Seismic and report-text facts (phases 3 to 5) are not started.

## L030 Depth reference and map bugs [done]
- **Depth** Formation tops are measured depth along the well from the rig floor (KB, median 25 m above sea level). Checked on 2,054 wells: shallowest top minus (KB + water depth) = 0.0 m median (p10..p90 0.0..0.5). So seabed = KB + water depth, the water column is empty above it. The 3D view now has a switch: rig floor, sea level (minus KB), seabed (minus KB and water depth). Still MD, not TVD (no deviation surveys loaded).
- **Bug: map shading drifted from the dots** The grid is linear in latitude, Leaflet stretches an image linearly in Web Mercator: drift up to 63 km (Hordaland) and 172 km (Nordland). Fixed by sampling rows evenly in Mercator y.
- **Bug: "missing API key"** I had switched the basemap to a provider that requires a key; back to OpenStreetMap tiles (no key), darkened by CSS in dark mode.
- **Panes** Floating panes sat behind Leaflet's own stacking layers on the map page: fixed (`.fill` creates its own stacking context).

## L031 GPU use [partly done, honest]
- **What the GPU is good for here** Cells x units distance matrices: maps and the 3D estimate surfaces. About 10x on the CPU at fine resolution (L025). Everything else is small: validation is scikit-learn fits and resampling of a few thousand rows, hotspot scans touch a few hundred units.
- **Done** The 3D surfaces now go to the GPU worker when one is configured (the proxy wakes it), CPU fallback otherwise; the header shows where the last heavy job ran. Fine maps already did.
- **Not claimed** Making idle components use the GPU would not make anything faster. Real GPU load comes with phase 3 (a local LLM reading the 112 GB of reports) and phase 4 (seismic attributes), both GPU-bound. One LLM at a time on the GPU applies.

## L032 Browser self-test found three bugs [done]
- **Run** `ui/static/selftest.html` drives the real UI in headless Chromium: Data explorer (pick table, chart, bar click filter, rows, map, remove filter), Target builder (preset, add/remove condition, mode switch, build, open), then validation, units, unit, map and 3D on the new target. 18 checks, all PASS after the fixes.
- **Bug 1** The UI proxy (`ui/serve.py`) forwarded no request body and allowed no DELETE: building or deleting a target could never work through the UI (the API tests did not catch it: they call the backend directly). Fixed.
- **Bug 2** The build error showed `[object Object]` (validation errors are a list). Now readable.
- **Bug 3** Well-level targets had no rig-floor / water-depth columns, so the 3D page returned 500 for them. Builder now keeps them; the scene tolerates older saved targets (empty, never guessed). Test added.
- **Lesson** Test through the UI proxy, not only the backend; API tests passed while the UI path was broken.

## L033 Saved targets in the pod [done]
- **Problem** The pod mounts the repo read-only, so a build could not save. Fix in code: the store writes to the first writable of `$SE_TARGETS`, the repo data dir, `$HOME/se-targets`, and reads from both that and the repo copy (test added). The homelab manifest also sets `SE_TARGETS=/srv/hackathon/se/targets` (pushed and applied by Flux, 2026-11-19).
- **Verified in the pod** Build through the UI proxy: 1,436 units in 38 s, written to `/srv/hackathon/se/targets`; delete through the proxy works; backend, UI, worker and gpuproxy Running.

## L034 Phase 3 scoping: report text [scoped, not started]
- **Source facts (read, not guessed)** The green-clay scan read 5,326 report JSONs (`sketches.atlas.read_report`: per page OCR markdown), 648,520 pages, 14 processes. `describe_page` returns `(depth_from, depth_to, has_green, lith)` per rock-description line and drops the line text, so only the green flag survives. Page text also exists as CSV (`data/official/text/Norway - Diskos reports.csv`: filename, page, content, wellbore name), not yet inspected in full.
- **3a keyword targets (CPU, no model)** Re-run the scan keeping each description line's text and page id (`descriptions_text.parquet`). Then a "report text" recipe in the builder: keywords or regex plus an optional lithology filter -> per-unit successes/trials -> same engine, validation, explanations. Reporting-effort bias stays visible (trials = described rows).
- **3b fact extraction (GPU, local LLM)** Pull structured facts (porosity, shows, pressures, losses, test results) from pages. Honest cost check first: 648k pages at about 1k tokens each is about 650M tokens, tens of hours on an 8B model even batched, so pages must be pre-filtered by cheap rules to candidates, and quality measured on a hand-checked sample and against FactPages (e.g. DST oil flow, cores) before any fact becomes a target. One LLM at a time on the GPU: the arbiter must grant it, and the evidence worker yields.
- **Decision needed from the user** after the commit: start with 3a (days of value, no model) and decide 3b after measuring token volume on a sample. Recommended.

## L035 Open seismic over our wells: Smeaheia and Sleipner [downloading]
- **Why these** Open (licence click-through) seismic that lies over wells we score. Smeaheia: Horda Platform (about 60.3 N, 3.4 E), 61 of our wells in 59.9 to 60.8 N / 3.0 to 4.2 E, but only 54 scored units (232 clay rows): context, thin for statistics. Sleipner: Utsira (about 58.4 N, 1.9 E), 145 wells, 470 scored units, 5,974 clay rows: enough to test a seismic layer. The cubes in the repo (F3, Penobscot, Parihaka, FaultSeg3D, ADELE) are not over our wells (L027).
- **Not found** No other open NCS 3D survey: Sodir's Diskos seismic is access by ownership or sale. Not searched beyond one pass; Sodir's contact is the next step.
- **Licence** co2datashare.org, CC BY 4.0 based (Gassnova and Equinor): credit them, no reselling. Asked the owner; accepted on their behalf on 2026-11-19, with country Norway and affiliation "Student (MSc thesis)" (their answers; the site asks for both before each download). Recorded in `data/seismic/*/LICENCE.txt`. Attribution must appear in the app wherever the data is shown.
- **Fetch** `fetch_data.py smeaheia|sleipner`: per resource POST (CSRF) -> modal -> POST /multiple_download -> 302 -> file; skips files already there. Smeaheia 11 resources (4.7 GB: 3D 1.7 GB zip = 11 GB SEG-Y, 2D, horizons, surfaces, velocity maps, well logs for 32/2-1 and 32/4-1, reports). Sleipner 12 resources (ten 4D vintages 94p01..10p11, about 24 GB).
- **CRS** ED50 / UTM 31N (EPSG:23031) from the .crsmeta.xml. FactPages positions are ED50 geographic: treated as WGS84, error under 150 m, small against 20 km windows.

## L036 UI interaction pass [done]
- **Done** Camera kept across refreshes (3D `uirevision`, only a new region resets it); the map is created once and a refresh swaps its overlay layers, so the view stays; unusual areas numbered (#1..) in the list and as labels in 3D, hover either one and both light up (others fade); panes resizable (corner), draggable, size and position remembered, double-click header to fit content, "reset layout"; the right pane starts below the 3D toolbar; every request shown in the header with elapsed seconds, a bar under the header, and a notice on stages.
- **Bug found by the browser test** `/api/map` returned NaN (invalid JSON) when the neighbour layer was switched off: the reach mask is now always computed (test added).
- **Tests** 33 checks in `ui/static/selftest.html`, all PASS; 13 backend tests pass.

## L037 Phase 3a report-text targets [done]
- **Re-scan** `GREENCLAY_OUT=reporttext WORKERS=8 python -m sketches.greenclay` (83 s). New tables identical to the published ones (209,707 description rows, 32,586 mentions: `equals` True), plus `descriptions_text.parquet` (text, file, page per line).
- **Builder mode "text"** Keywords (word-start, case-insensitive) over description lines of chosen rock types; unit = well x formation; same engine and validation. Preview shows matches with well, file and page before anything is built.
- **Results** Calcareous clay rows: 8,729 units, 1,192 wells, 21.8 % of 56,330 lines; formation +0.0083 [0.0042, 0.0126] helps, neighbours +0.0023 [-0.0023, 0.0086] no evidence. Pyrite in described rows: 14,333 units, 5.1 % of 99,799 lines; formation +0.0016 [0.0005, 0.0027], neighbours +0.0032 [0.0002, 0.0061] both small but above zero.
- **Caveat** Trials count lines in both group and formation intervals (a line is in each interval that contains it), as in the green-clay target. "other" lines are mostly operations text.
- **Open (3b)** LLM fact extraction: not started; token volume still to be measured on a sample.

## L038 Seismic: indexed, shown as context, not (yet) evidence [done]
- **Downloaded and indexed** Smeaheia (all 11 resources, 4.7 GB) and Sleipner 4D (all 12 vintages, 25 GB): `fetch_data.py smeaheia|sleipner`, then `python -m se.seismic.index` / `python -m se.seismic.sleipner`. 14 surveys: decimated copy (every 6th or 3rd line, 8 or 4 ms), footprint, geometry (`data/subsurface-evidence/seismic/<id>/`). SEG-Y read with numpy (IEEE float for Smeaheia, IBM float and CDP coordinate words for Sleipner; both decoders tested on synthetic files).
- **Coordinates checked** Both Smeaheia wells (32/2-1, 32/4-1) fall inside the GN1101 footprint after ED50 UTM 31N -> WGS84: the projection and scalar handling are right.
- **Time-lapse sanity check (Sleipner)** RMS of the difference at 850 to 1100 ms (Utsira level) vs above and below: 2008-1994 1.76x, 2006-1994 1.75x, control (the same 1994 data in two processings) 1.06x. The CO2 plume signal is where physics says. Caveat: simple RMS on a few lines; processing differences not removed; the control is not a clean repeatability test.
- **Why it stays context** Wells inside footprints: GN1101 3, TNE01 2, Sleipner 1 (0 scored units). A seismic evidence layer cannot be validated on that. It also needs a per-well time-depth relation; the depth shown in 3D is two-way time x an adjustable velocity / 2 (default 2.0 km/s), labelled illustrative (about 15 percent). The `seismic` layer remains "not built". What would change it: open 3D seismic over many NCS wells (Diskos 3D is by ownership or sale) plus checkshots.
- **Not found** Other open NCS 3D surveys: one search pass only; Sodir's contact is the next step.

## L039 Performance and the Map page [done]
- **Measured** (real clock, headless Chromium over CDP, this machine, software WebGL, so drawing is slower than on a GPU): a 3D style change took 280 to 340 ms, of which 115 to 170 ms waiting on the server; a 10-tick slider drag made 10 full redraws with server time growing 181 -> 851 ms as requests queued. Building traces in JS: 2 to 7 ms (not the problem). First page load: one 1.7 to 1.9 s main-thread task (Plotly bundle 3.6 MB, coast topology).
- **Fixed** The scene is fetched only when the request changes (target, formations, region, neighbour switch, detail), a newer redraw cancels an older one, sliders are debounced (90 ms), hover restyles only on change, the backend caches scene answers per state (280 -> 41 ms), gzip on backend and UI server (162 -> 25 KB). After: style change about 90 to 130 ms with no server call; a drag is 1 redraw.
- **Not done** Lazy-loading Plotly per page (about 1.5 s on first load), a smaller 3D-only bundle, thinning the grey "too few" sticks (about 85 percent of segments), server-side image rendering. Each is a further step if lag remains.
- **Map page removed (user confirmed)** It overlapped 3D. Its unique parts moved to 3D: neighbour-evidence switch with its tested status, estimate detail (normal 0.15 deg or fine 0.05 deg on the GPU worker), Top view and Reset view. The basemap tiles are not in 3D (coast, borders and a lat/lon grid are). `#map` redirects to 3D. The `/api/map` and `/api/jobs/map` endpoints remain.
- **Bugs found on the way** A comment inserted mid-line had disabled the "no formation selected" guard; a long colour-bar title broke the 3D layout in narrower windows; the depth-stretch floor (0.1) made every stretch below about x18 look identical (removed); every slider tick refetched the scene.

## L040 Colours, sticks and hover wording [done]
- **Colour picker** Four palettes (soft blue, high-contrast viridis, warm, grey) and a colour range (default 20 percent) for sheets and sticks; stick classes are fractions of that range (10, 40, 100 percent). The key pane explains: a stick is one well's interval inside one formation (a "pipe"), its colour is the observed share, grey means too few records, neighbouring sticks differ because they are different wells. Sheets are the model estimate, boxes the 20 km areas above or below the formation average.
- **Hover texts** Every hover states its number's meaning in the target's words (observed N of M = share; model estimate smoothed from wells within 60 km, not an observation; area vs formation average).

## L041 Seismic inspector [done]
- **What** "Inspect seismic" in the seismic pane opens a side pane. 2D: an inline section, crossline section or time slice (heatmap, hover gives inline, crossline, time or depth, amplitude, position along the line, lat/lon), our wells marked (dotted line on sections, cross on the slice). 3D: the two sections and the time slice through a transparent survey box, with our wells, depth or time on the vertical axis. Controls: line and time sliders, gain, blue-white-red or grey, depth toggle (illustrative, uses the velocity in the seismic pane), time-lapse difference against another vintage of the same processing. The chosen inline or crossline is drawn in the big 3D scene too. A summary table lists survey, traces, sampling, lines, amplitude scale, our wells (distance to the nearest trace) and the credit.
- **Backend** `/api/seismic/slice` (time slice on the inline x crossline grid, null where traces were not kept), `/api/seismic/wells` (our wells inside, nearest trace and distance), curtain now carries inline, crossline, distance and amplitude scale. Amplitude shown = int8 / 127 x the survey's 99th percentile (decimated copy, not the raw SEG-Y).
- **Check on real data** Sleipner 2008 minus 1994 time slice at 1000 ms shows the CO2 plume as a localised red and blue lobe next to well 15/9-13. Wells sit 13 to 58 m from their nearest trace (Smeaheia): positions are right.
- **Limits** Decimated data (every 3rd or 6th line, 4 to 8 ms): good for context, not for fine interpretation. Depth is two-way time x velocity / 2.
- **Tests** 60 browser checks, 17 backend tests pass.

## L042 Layout, colour range and 3D jitter [done]
- **Layout** The 3D page had six floating panes. Now two docked sidebars around the plot: settings (left: Data, Display, Seismic, inspector controls) and information (right: colour key, unusual areas, guide, inspector views). Sections fold, each sidebar collapses to a strip, widths and states are remembered (localStorage), the inspector widens the right bar while open. Small corner radius (6 px controls, 10 px panels) throughout.
- **Colour range** From a low to a high value (default 0 to 20 percent), not only 0 to x. Sheets, stick classes (10, 40 and 100 percent of the range above the low end) and the key follow; the low end can never reach the high end.
- **Jitter, causes found** (1) Axis ranges were automatic, so toggling the coast, seismic or sheets changed the data bounds and rescaled the whole scene; now fixed from the chosen formations. (2) A redraw could reset or snap the camera; now the live camera is read back and passed again, only a new region starts from the default. (3) A second redraw fired right after load (resize observer's first call); skipped. (4) Plotly's resize of a WebGL scene threw "axis scaling" and left a stale canvas; 3D scenes are now redrawn at an explicit container size instead of resized. (5) A hidden (folded) plot is not touched.
- **Verified in real time** (DevTools protocol, 13 interaction steps: inspector, sliders, folding, collapsing both sidebars, colour range, views): 0 exceptions, plot width follows its container. The virtual-time test harness still logs a few Plotly "axis scaling" lines, which are an artefact of its clock; none occur in the real-time probe.
- **Tests** 68 browser checks (all PASS), 17 backend tests.

## L043 Colour key as a filter [done]
- **Why** With thousands of sticks in a few colours, a class is hard to find on the map. The key now filters.
- **What** Each stick class row has a checkbox (show or hide that class), an "only" link (isolate it; again restores all), and "all" / "none". Hovering a row fades the other classes so the hovered one stands out. The higher (orange) and lower (purple) area colours have checkboxes too; unticking one removes those boxes and their list entries (numbering stays consistent). Counts in the key do not change when a class is hidden.
- **How** Stick traces carry their class (`meta.cls`); show, hide and fade use `Plotly.restyle` (no redraw, no scene change, camera untouched). Class visibility is kept across redraws.
- **Tests** 77 browser checks, all PASS (11 new for the key).

## L044 One-assignment stratigraphy, projected distance and nested calibration [done]
- **Why** A description depth inside overlapping formation and group intervals was previously counted in every interval. Spatial comparisons also used a 60-degree longitude approximation, and reported Platt scores were fitted on the same outer OOF predictions they evaluated.
- **What** Interval assignment now chooses a formation first; groups are fallback only. Overlapping candidates are ordered by narrowest interval, shallower top, bottom and name; every source row is accounted for in diagnostics rather than silently hidden. Unit IDs include level and measured-depth bounds, and each unit carries group metadata. EPSG:3035 km coordinates drive spatial neighbours, blocked folds and hotspot windows while the UI display frame remains separate. Validation metrics, sweeps and bootstrap intervals now use inner-OOF calibration from each outer training fold; deployed Platt parameters still use stacked OOF. Layers default on only after a `helps` verdict.
- **Found** Rebuild assigned 31,277 of 50,640 clay rows once (23,833 formation, 7,444 group fallback); 801 rows had competing candidates, and 19,363 rows were unassigned or dropped by depth/well normalization. The 41,354 units have zero duplicate IDs. Labelled units changed 3,762 -> 2,286 and labelled rows 49,961 -> 27,025; this is the removal of duplicate stratigraphic membership, not lost source data. Formation gain 0.01425 -> 0.00714, spatial gain 0.01562 -> 0.00919, and spatial-over-formation delta 0.00136 -> 0.00204 with 90 percent interval [-0.0030, 0.0067]. Logs remain harmful on their subset (delta -0.0253, 90 percent interval [-0.0749, -0.0029]). Validation took 90 s.
- **Decision** Retain all source/conflict diagnostics in `unit_diagnostics.json` and keep formation/group overlaps visible. The deterministic winner is an explicit modelling rule, not a claim that the competing stratigraphic picks are incorrect.
- **Tests** 23 backend tests pass, 1 GPU-dependent test skipped. Focused tests cover one assignment, unique IDs, EPSG:3035 at 75 N, nested calibration without outer labels, disabled no-evidence layers and API operation.

## L045 Honest full-haystack retrieval [done]
- **Why** The prior DISKOS-QA corpus contained 1,690 passages, all obtained from the benchmark's own gold contexts. A high rank in that pool measured recovery of a known support set, not search through the available report archive.
- **What** The search corpus now keeps all 1,690 gold passages and adds 5,000 deterministic natural-language OCR pages streamed from the 5.7 GB Norwegian Diskos corpus. Duplicate/near-identical text is excluded, sampling is document-stratified, and `chunks.manifest.json` records source counts, seed, SHA, exclusions and build time. Scorecard output now records citation precision, evidence traces and the corpus manifest. A query still retrieves gold context from the same larger pool; it receives no privileged index or score.
- **Found** The rebuilt corpus has 6,690 passages; 938 supported and 89 excluded QA questions. The old 1,690-passage recall@5 was 0.756 vector, 0.883 hybrid and 0.925 entity-filtered hybrid. New recall was not run because building the public Qdrant collection would be a state-changing service action; the new corpus tests and deterministic manifest pass.
- **Decision** Do not call this a “first public baseline” until the expanded Qdrant collection is rebuilt and the scorecard rerun. Gold-only retrieval remains reproducible in the manifest/evaluation history, but is not the headline score.
- **Tests** Full app suite: 69 passed. Focused corpus tests: 5 passed.

## L046 Cross-modal GPU proof and traceable catalog [done]
- **Q** Does the available GPU find a useful relation when directly joining FORCE 2020 wireline logs to measured RealPore core plugs, and does “neural” improve an explainable baseline?
- **What** Added a limited masked MLP with whole-well grouped 5-fold cross-validation, 40 km spatial blocks and train-only normalization. `force2020/train.csv` and `realpore.parquet` are the only labels/features; the labelled hidden-test file is never read. A train-only HistGradientBoosting regressor and fold median are explicit baselines. Outputs include OOF rows, source SHA-256, fold membership, matched-depth distance, model/device and limitations. Dataset/artefact APIs expose lineage, licence, source truth status and limits. The Subsurface UI now links the ten specialist Studio workflows from one evidence shell and shows the cross-modal proof next to lineage.
- **Found** 69 overlapping wells, 23,081 log/core matches at mean 0.038 m and max 0.442 m. CUDA training took 23.0 s. Porosity RMSE/R²: median 10.08/-0.10, tree 6.83/0.495, MLP 8.11/0.287. Log10 permeability RMSE/R²: median 1.72/-0.05, tree 1.27/0.428, MLP 1.44/0.264.
- **Decision** The neural model is retained as a reproducible proof and architectural baseline, not accepted as the production layer: the shallow tree wins on both held-out targets. Future encoders must beat a non-neural ablation, pass spatial/well validation and retain source masks/uncertainty before default activation. This proof is limited to 69 selected/core-sampled wells and does not use reports or seismic yet.
- **Tests** 24 backend tests pass, 1 CUDA agreement test skipped under the normal environment. Proof itself ran on CUDA sm_120 through the repository GPU venv. GPU reservation was released to `llm` immediately after training.

## L047 3D workspace and Strata Desk [done]
- **Why** Start in 3D, then follow an interval to evidence rather than searching an unrelated chat. The old assistant mixed scene metadata into the search question, and its self-check did not verify FactPages claims. The 3D neighbour toggle was also hard-coded on despite its `no_evidence` result.
- **Decision** Use a bounded, separate question and scene payload; a selected wellbore focuses retrieval unless the question names another. Use lexical retrieval over the local report corpus and explicit FactPages excerpts, then one Naija-Petro 32B IQ3 completion. This does not depend on re-indexing Qdrant and is not a new retrieval benchmark. Display exact returned excerpts behind Markdown citation links; a link is not proof of entailment. Raw model HTML and image loads are excluded. The deployed endpoint returned a cited FactPages answer for 9/2-1 with the 32B alias.
- **3D** The plot opens first; select a stick to see recorded trial counts, open its interval or ask about it. Default neighbour evidence requires `helps`. Sheet colour is a target estimate, sheet geometry is a smoothed interval mid-depth, and displayed seismic is not a predictor. A source excerpt or a displayed count cannot establish mineral prevalence. Keep these distinctions in the primary surface, not only in documentation.
- **Deployment finding** The live 3D backend still served the old 3,762-unit / 49,961-row artifact in memory while the corrected 2,286-unit / 27,025-row artifacts were on disk. A backend reload is needed before demoing corrected numbers. No service restart or re-index was performed.

## L048 Seismic acquisition with a target and a tie [research]
- **Found** [PANGAEA MSM98/2](https://doi.org/10.1594/PANGAEA.973650) has migrated 2D SEG-Y for the Norwegian Sea; [UiT DataverseNO](https://doi.org/10.18710/DWOUPL) has unrestricted but unprocessed 2D SEG-Y for the mid-Norwegian shelf and Lofoten margin. [Diskos](https://www.sodir.no/en/facts/data-and-analyses/release-of-data/access-to-released-data/) is the more promising 3D route; access may require ordering. The SINTEF Johansen dataset is model output, not raw seismic amplitudes. Formats, licences, access and intended use are in `docs/seismic-data.md`.
- **Decision** Prioritise a well-tied pilot over more visual coverage: calibrate depth vs time with checkshots/velocity and use measured logs or core at tied wells. Compare formation-only, logs/core and added seismic at held-out wells or surveys; mask unsupported areas. Treat 2D lines as sections and never infer petrography from a reflector alone. No new binaries downloaded.

## L049 Seismic vertical reference audit [calibration pending]
- **Checked** Original trace headers (41 sampled traces each): Smeaheia GN1101 starts at 0 ms; TNE01 at -2 ms. The delay field is a recording/sample origin, not a seabed pick. Published GN1101 seabed time near 32/2-1 is about 481 ms TWT; the separately published depth surface is about 356 m below sea level. The archive's negative surface Z values are positive magnitudes here. No survey-wide processing datum was certified by the sampled header fields.
- **Found** `well_reports.zip` contains `Smeaheia well picks Feasibility phase.xlsx`: four picks each for 32/2-1 and 32/4-1 T2 with MD, TVD, TVDSS, TWT and XY. The 32/2-1 top-unit pick is 984.76 ms at 873.98 m subsea. At the UI's 2.0 km/s, the sea-level preview is 984.76 m, about 111 m too deep at that pick. This is a spot comparison, not a survey error bound. Gassnova's Troll Kystnær report, section 4.2, describes a checkshot-calibrated sonic tie for TNE01 and a three-well layer-cake depth conversion. Those controls are not used in the live overlay.
- **Decision** Keep the original survey time visible; remove the unsupported +/-15% bound. Do not shift the curtain to seabed zero. For a regional pilot, verify the survey datum and horizon versions, tie directional well TVDSS and checkshots, then compare water + rock interval velocities with the constant preview. Log each tie's source, range, residual and uncertainty. Do not evaluate against a depth surface derived from the same fitted controls as if it were independent.

## L050 GN1101 leave-site-out depth conversion [research only]
- **Method** `cd subsurface-evidence/backend && uv run --frozen python -m se.modeling.smeaheia_velocity`. Link the four common published feasibility horizon picks at each of 32/2-1 and 32/4-1 T2 to the ED50 UTM 31N interpreted seabed time grid (480.87 / 425.75 ms near the sites). Anchor depth with FactPages water depths (351 / 312 m), not the already converted Petrel depth surface. Hold out each whole site. Its water depth, seabed time and horizon times are inputs; its pick depths are references only. The workbook, archive members, grid samples, FactPages IDs 5839 / 2918, worksheets and row numbers are in `data/subsurface-evidence/velocity/gn1101.json`.
- **Result** RMSE in metres: constant 2 km/s preview **73.22**; seabed + fixed rock velocity **68.17**; seabed + one fitted rock velocity **24.44**; seabed + fitted layer velocities **15.85** (site RMSE 13.41 / 17.95 m; max absolute residual 30.10 m). Eight picks, two correlated well-site groups, one survey; test references are publisher picks, not independent checkshots. No prediction interval or map-wide error estimate.
- **Unresolved** LAS OWT × 2 at 32/2-1 is 58.05–58.51 ms later than the workbook TWT. Sonic interval differences agree much more closely; no absolute shift is applied. Workbook T2 picks imply 23 m RKB versus 24 m at the FactPages parent site; this is a site link, not proof of the same trajectory. The original 32/2-1 end-of-well report §11.7 names a deviation survey; numeric stations did not appear in text extraction. Raw checkshots, matched borehole trajectories, GN1101 processing datum and independent validation are still required. Keep calibrated rendering disabled.

## L051 NCS source roles and seismic wellhead screen [audit]
- **Method** `cd subsurface-evidence/backend && uv run --frozen python -m se.modeling.seismic_coverage`. Screen FactPages wellheads with explicit ED50 UTM metadata against each index's decimated XY trace hull. RealPore candidates must match NPDID and name; report and FORCE-training flags require an unambiguous registry name. Register source grain, keys, role and misuse guard in `se/modeling/relations.py`. Contracts cover all 20 catalogued roots; this is not full ingest or validation.
- **Result** Screened 8,442 of 8,496 registry wellheads (54 excluded for unresolved coordinate metadata). Seven distinct wellheads in 14 local index products: GN1101 four, TNE01 two, and the same 15/9-13 in twelve Sleipner vintages or processing variants. TNE01 31/3-3 has FORCE logs, 587 RealPore rows and one labelled report interval. GN1101 has FORCE training at 32/2-1 and RealPore rows at 31/6-6, not both at one wellhead. Hull holes, well trajectories, seismic illumination, geologic intervals and times are not resolved by these counts.
- **Product** Lineage shows pilot and audit with source receipts. Chromium verified rendering, receipt URLs and behavior if the model artifact is missing, on an isolated local backend. The live k3s backend was not reloaded and still served the old 3,762-unit result when checked; the isolated backend served 2,286.

## L052 Sleipner holdout against interpreted porosity [research only]
- **Failure fixed** The old transfer assumed an external test while 15/9-13 was in FORCE train and had RealPore cores. Its released PHIF is entirely null (13,124 LAS rows). Exclude block 15/9 and named Sleipner fields by FactPages NPDID before fitting. Treat an absent curve as unscorable. Keep the prior GPU proof historical; this run neither validates nor overwrites it.
- **Method** `cd subsurface-evidence/backend && OMP_NUM_THREADS=2 uv run --frozen python -m se.modeling.sleipner_transfer`. Align lab porosity with FORCE GR, RHOB and NPHI by checked NPDID/name plus MD within 0.5 m, with no sampling outside log bounds or at duplicate log depths. Keep original row positions and offsets. Weight multiple core rows that share a log sample so they do not increase that sample's weight. Use 19,751 complete rows from 61 wells. LAS headers declare PHIF and NPHI in volume fraction; convert to percent for scoring. Do not assume RT and FORCE RDEP are functionally equivalent or transfer absolute MD as a feature.
- **Result** Only 15/9-A-16 was scorable: 12,818 matched PHIF and log samples, MD 1,750.01–3,731.51 m. RMSE in porosity percentage points on identical rows: training median 18.99, tree 8.84, neutron proxy 7.91, fixed sandstone/brine density transform 1.06. The simple density relation agrees best with PHIF here; PHIF may already use RHOB and is not core truth. This is one correlated well profile, not 12,818 independent tests, not verified Utsira formation attribution, and not a general material map. Training links, LAS line numbers, predictions and source hashes are in `data/subsurface-evidence/sleipner_transfer_v2/`.

## L053 Plan: NCS earth model with targets and confidence [decided by owner]
- **Ask** (owner): use all information that can be extracted, including assumptions from relations between data types, to build a realistic 3D model that says where to find each target, with a confidence score and the information behind it. Write the plan so another agent (Copilot) can continue.
- **Decisions (owner)** 3D earth model; all four realism pieces (true depth and well paths, formation surfaces, rock and fluid properties, seismic tied to wells); pilot area first (Horda Platform / northern Viking Graben, 59.5–61.5 N, 1.5–4.5 E), then scale; stratigraphic grid; targets: hydrocarbons, reservoir quality, overpressure, CO2 storage, green clay, calcareous clay, sandy delta; keep and build on L044–L052; pod restarts allowed.
- **Measured for the plan** FORCE 2020: 98 wells, X/Y/Z (TVDSS, -111 to -5,396 m) on 99 % of samples, median horizontal drift 40 m, 9 wells over 0.5 km. FactPages: 1,863 of 2,201 exploration wells have TVD at TD (mean TVD/MD 0.958); development wells have kick-off point but no azimuth. Pilot: 3,932 wellbores, 14,276 tops in 661 wellbores, 60 FORCE log wells, RealPore 148,711 rows in 461 wells, 459 DST, 11,393 mud weights, 2,627 casing/LOT, 3,564 cores, 57,993 report description lines in 1,771 wells.
- **Design choice** Two numbers per cell and target: calibrated probability and support (data density, independent sources, agreement, held-out skill). Uncertainty is carried by Monte Carlo realisations of surfaces and properties. A component is used only if it beats its baseline on held-out wells. Wells without azimuth get a lateral uncertainty radius instead of a guessed path.
- **Files** `PLAN.md` (phases P0–P8, tasks with acceptance tests) and `../.github/copilot-instructions.md` (working rules for any agent).
- **Fixed** The browser test stopped on a duplicate `sticks` variable added in the L047 work; renamed.

## L054 Housekeeping after the L044–L052 work [done]
- **Browser test** Three test-side issues from the added checks, none in the app: a duplicate `sticks` declaration (stopped the script), `new F().KeyboardEvent` (precedence: `F` is an arrow function; now `new (F().KeyboardEvent)`), and the neighbour-switch check assumed the layer starts on (it now starts off unless its status is `helps`, L047). After the fixes: 79 browser checks pass, 31 backend tests pass (1 GPU test skipped).
- **Pod** Backend restarted; it now serves 2,286 labelled units and 27,025 rows (was 3,762 / 49,961 in memory).

## L055 P0.3 + P1 Frame: true positions and tops in TVDSS [done]
- **Method** `cd backend && uv run --frozen python -m se.earth.frame && uv run --frozen python -m se.earth.tops`. Artefacts in `data/subsurface-evidence/earth/pilot/` with manifests.
- **Checked first** FORCE X/Y are ED50 / UTM 31N: median 6 m from FactPages wellheads read as ED50 (158 m if read as WGS84). FORCE Z = -TVDSS: MD + Z equals FactPages KB (median 0.0 m, p90 2.2 m). So TVDSS = TVD below rig floor - KB. Earth-model coordinates come from ED50 (EPSG:4230 / 23031) to EPSG:3035; the older layers treat ED50 lat/lon as WGS84 (about 150 m offset), noted, not changed here.
- **Depth model for wells without a true path** Compared on 87 FORCE wells with TVD at TD: constant inclination from surface ("ratio") vs vertical. Per-well RMSE median / p90: ratio 0.48 / 80 m, vertical 0.59 / 140 m. Chosen: ratio. Development wells use vertical to the kick-off point then straight (true by the definition of the kick-off point below it is an assumption; untestable: no development wells with true paths). Azimuth unknown: position stays at the wellhead, the implied offset becomes a lateral uncertainty radius (contains 99.8 percent of true FORCE positions).
- **Sigma** sigma_z = s (1 + a h), h = implied horizontal offset; fitted with whole-well 5-fold CV: held-out 90 percent coverage 92.3 percent (all FORCE wells), 93.9 percent (pilot wells). Accepted (85 to 95).
- **Pilot frame** 3,932 wellbores: 60 FORCE paths, 3,524 FactPages approximation, 348 vertical assumed (no TVD at TD; sigma from the 90th percentile of (MD - TVD) / MD on FORCE wells = 2.8 percent).
- **Datums** 642 pilot wells consistent (shallowest top = KB + water depth within 5 m), 19 inconsistent (kept, flagged in `datums.parquet`), 3,271 without tops.
- **Tops** All 14,276 pilot tops converted (0 lost): 1,547 FORCE, 11,911 FactPages, 818 vertical. One negative thickness flagged. Acceptance at real FORCE tops with their true path hidden: 57 wells, 1,476 tops, median error 0.43 m, RMSE 65.7 m (a few deviated wells), 90 percent coverage 94.4 percent.
- **Tests** `tests/test_earth.py`: pilot box, manifest, depth models, FORCE path exactness, datum status.

## L056 P2.1 + P2.2 Column and surfaces [done]
- **Method** `cd backend && uv run --frozen python -m se.earth.column && uv run --frozen python -m se.earth.surfaces` (GPU shell for the hybrids, L057). 2 km lattice over the pilot, 9,187 nodes inside.
- **Column** FactPages has names, levels, parents and URLs but no age order. Order from the wells: Copeland ranking of which top is shallower. 12 groups: Nordland, Hordaland, Rogaland, Shetland, Cromer Knoll, Viking, Brent, Vestland, Dunlin, Statfjord, Hegre, Basement; 99.89 percent of group pairs agree. Inside groups 94.6 (Viking: Heather and Sognefjord interfinger) to 100 percent. 55 horizons with >= 30 pilot wells modelled.
- **QC** 203 picks above the seabed excluded (mostly Nordland tops a few metres above it in 25/2 wells), listed in `surfaces_report.json`.
- **First run [wrong, kept]** Every horizon fitted alone with GP + linear trend. Deep surfaces did worse than a constant (Brent 727 m vs 714 m) and under-covered (72-82 percent); formations clamped to their group bounds at 80-98 percent of nodes.
- **Why** Deep Jurassic surfaces correlate over 6-15 km (fault blocks; depth about 2 km on the Horda Platform, 4-5 km in the graben); held-out 40 km blocks are beyond that. Shallow Cenozoic surfaces correlate over 32-35 km.
- **Fix** (1) Shallowest group top = seabed (definition; 642 wells confirm). (2) Per horizon, the model (constant, trend, GP with constant or linear mean) is chosen by blocked CV; sigma inflated by a factor fitted on the other folds (nested). (3) Formations as a fraction of their group interval plus a presence probability (indicator kriging); order inside a group is decided per column.
- **Found (held-out 40 km blocks; near = 10 km blocks)** Seabed GP 27 m (const 119); Hordaland 172 m; Rogaland 187 m (const 428); Shetland 210 m (434); Cromer Knoll 424 m (deep-kernel GP, L057; const 729); Viking 596 m (749), near 360 m. Brent, Vestland, Dunlin, Statfjord, Hegre: constant wins (714-762 m), even near (690-750 m): no spatial skill from wells alone. Nested 90 percent coverage 0.88-0.92 for every group. Formation depth end to end (group surfaces + fraction, all without the held-out block) beats a direct per-formation fit for 33 of 43 (e.g. Heather 383 vs 710 m, Rødby 258 vs 471 m); coverage 0.63-0.98, under 0.85 for 16 formations (worst Johansen 0.63, Burton 0.70).
- **Acceptance** Zero group-order violations and zero formations outside their group on the lattice. Shallow and middle surfaces beat their baselines; deep ones use the best baseline with calibrated sigma (stated, not hidden). The 16 under-covering formations are flagged for P6 (their sigma is inflated there by their own CV factor).
- **Tests** `test_earth.py`: GP surface recovery, interval coverage and posterior samples.

## L057 Sophisticated candidates: ML-kriging hybrid and deep-kernel GP [done]
- **Why** Owner asked for regression kriging, ML-kriging hybrids and non-linear methods. Run as competing candidates under the same test, so complexity has to earn its place.
- **Method** `se/earth/hybrid.py`. rk_gbm: gradient-boosted trees on x, y and the predicted depths of the seabed and every shallower group at that point, then a GP on out-of-fold residuals. dkl: deep-kernel GP (2-layer network to 4 features, RBF kernel, exact marginal likelihood, Adam, 300 steps) on cuda (RTX 5060 Ti). Shared 40 km block folds; covariates at held-out points come from shallower surfaces refitted without that fold.
- **Found** dkl wins for Cromer Knoll: 424 m vs 615 m (-31 percent), nested coverage 0.908. Brent 703 vs 705 and Vestland 735 vs 743 (under 2 percent, sigma inflation about 3.8). Elsewhere both lose. rk_gbm never wins (overfits with about 400 wells).
- **Decision** Adopt a candidate only if held-out RMSE falls by at least 5 percent and nested 90 percent coverage stays within 0.85-0.95. Adopted: dkl for Cromer Knoll only. Co-kriging across horizons is the next candidate if a deep surface needs it; seismic (P2.3) is the physical fix for fault blocks where it exists.
- **Doc** `docs/architecture.md`: mermaid charts of sources, join keys, methods and results (owner request).

## L058 P2.3 Seismic horizons tied to wells [done]
- **Source** Smeaheia `Key_Horizons_2010` (Equinor, Gassnova): PointZ shapefiles in ED50 UTM 31N, about 100 x 200 km over Troll and the Horda Platform. Seabed, Top Shetland, Draupne, Sognefjord, Fensfjord, Johansen, Dunlin, Statfjord. Domain says "Unknown"; Z is two-way time: seabed Z / water depth = 1.32 (water about 1,500 m/s), deeper Z / pick depth 1.05-1.13.
- **Method** `cd backend && uv run --frozen python -m se.earth.seismic`. Tie wells with a pick and horizon points within 250 m: 54 ties. Depth = vw t_sb / 2 + dt (a + b dt) (average velocity linear in one-way rock time) plus a GP on the tie residuals of each horizon (kriging with an external drift). Fitted: water 1,530 m/s, a 1,441 m/s, b 1,069 m/s per s; tie residual sd 82 m.
- **Test** Held-out 40 km blocks; every pick in a held-out block withheld from the velocity and residual fits. First sigma (the GP's own variance from 6-12 ties) covered only 0.43-0.78 [wrong, replaced]. Sigma now = q x (depth - water), q from held-out errors of the other horizons: q = 0.105.
- **Found (tied wells, held-out)** Shetland 88 m vs wells-only GP 330 m, constant 881 m (cover 0.917); Sognefjord 90 vs 200 / 493 (0.909); Fensfjord 150 vs 296 / 418 (0.889). Draupne 149 vs 540 but covers 0.714; Johansen 243 vs 373, cover 0.833; Statfjord 215 vs 723, cover 1.0; Dunlin 3 ties only.
- **Decision** Adopt where RMSE falls by at least 5 percent and coverage stays in 0.85-0.97: Shetland, Sognefjord, Fensfjord. Blended into the surfaces inside the interpreted area, weight falling to zero over 6 km at its edge. Draupne, Johansen and Statfjord are 2-4 times more accurate but their sigma does not hold, so they stay context (shown in the inspector). Caveat: the interpreter tied these horizons to wells, so held-out picks are not fully independent (L049). Small samples: 6-12 ties per horizon.

## L059 P2.4 Isochores and stratigraphic grid [done]
- **Failure found** The first grid collapsed Vestland and Statfjord to 1 layer: a constant deep surface carries no thickness, so under a varying surface it pinches out.
- **Fix** Isochore candidate per group: top = group above + kriged thickness (wells with both tops; absent groups give zero thickness), scored on shared 40 km block folds with chained predictions. Adopted where RMSE falls by at least 5 percent with nested coverage 0.85-0.95, or, for a constant direct surface, if at most 10 percent worse (stated trade-off: consistent thickness vs a flat constant). The deep-kernel winner (Cromer Knoll, L057) is kept. Adopted: Brent (675 vs 705 m), Vestland (712 vs 743), Dunlin (711 vs 749), Hegre. Statfjord stays constant.
- **Grid** `uv run --frozen python -m se.earth.grid`. 2 km columns, 9,187 inside the pilot; zones = groups with proportional layers (nk = ceil(p90 thickness / 10 m)); 715 layers, 8.2 M cells, median layer 5.9 m. Formations are cell labels (deepest present top above the cell centre), so interfingering is per column.
- **Checks** 0 gaps or overlaps; 0 of 1,302 sampled cells fail the round trip cell -> formation -> depth interval. Volumes per formation in `grid_report.json`.

## L060 P3.3 Pressure [done, coverage slightly low]
- **Method** `uv run --frozen python -m se.earth.pressure`. Pilot FactPages: DST bottom-hole (else final shut-in) pressure, mud weight, LOT/FIT EMW; MD -> TVDSS by the frame. Hydrostatic = 1.03 g/cm3 brine from sea level.
- **QC** 58 of 167 DST values are physically impossible as reservoir pressures (EMW outside 0.95-2.3 g/cm3): 52 below hydrostatic (likely wellhead readings), 6 above overburden (likely bar entered as MPa). Excluded and listed, never rescaled. Normally pressured DSTs give EMW 1.025 (supports the 1.03 assumption).
- **Found** 70.6 percent of valid DSTs are over 1 MPa above hydrostatic. Pore / mud pressure ratio 0.88 (fold values 0.85-0.89). Held-out DST from mud weight at the same depth: bias -0.18 MPa, RMSE 5.5 MPa, vs hydrostatic bias -8.5, RMSE 11.3 (92 pairs, 50 wells). 3D GP of excess EMW (DST + mud-derived soft data), held-out blocks: RMSE 0.253 g/cm3 vs hydrostatic 0.430 and depth trend 0.328; nested 90 percent coverage 0.826 (109 DSTs: slightly under; P6 uses the inflation 1.88). Fracture EMW median 1.71.

## L061 UI: inspector, enrichment, tabs, architecture [done]
- **Tabs** 13 -> 7 (owner choice): 3D, Targets, Units, Validation (+ Layers, Geology rules), Data (+ Lineage, Other tools), Architecture (+ Overview and terms), Log. Secondary pages are a sub-navigation; old links still work.
- **Architecture** `docs/architecture.md` rendered with mermaid; wheel zoom, drag, fit, full screen.
- **Seismic inspector** Takes over the main view (2D section or 3D cube; side by side removed at owner request). Gain and time slice worked but were too small to see in the side pane. See-through option: near-zero amplitudes transparent (2D colour scale alpha, 3D opacity scale, big scene too). A replay animation was built and removed at owner request (a gimmick).
- **Enrich** `/api/seismic/enrich`: interpreted horizons along the line (Smeaheia surveys, native time), gamma ray (FORCE train or Smeaheia LAS) and Sodir formation tops in survey time. Depth to time: the L058 tie for Smeaheia surveys, else the stated preview velocity. At 32/2-1 the tie puts top Sognefjord at 1,054 ms vs the published pick 985 ms: about 70 m, inside the 82 m tie sd, visible as an offset between the horizon line and the top.
- **Wells** saturated green in the inspector (contrast to blue-white-red); gamma ray purple.
- **Tests** 88 browser checks pass; pods restarted, the pod serves enrich.

## L062 P3.4 Temperature [done]
- **Method** `uv run --frozen python -m se.earth.temperature`. 91 DST temperatures (45 pilot wells, one per well and 10 m), 1.0-4.8 km below the seabed. T = T0 + g (z - water depth); lateral g by a GP; reading error 3 deg C.
- **Found** Gradient 27.4 deg C per km. T0 = 31.6 deg C is an intercept, not the seabed: a fixed seabed temperature of 4-10 deg C fits worse on held-out blocks (12.7-13.6 vs 11.3 deg C), because the shallow, shale-rich section has a steeper gradient. Above 1 km the profile is linear from 7 deg C at the seabed (assumption, outside the data). Held-out RMSE: GP 10.7 vs constant gradient 11.3 deg C; nested 90 percent coverage 0.912.

## L063 P3.1 Lithology [done]
- **Method** `uv run --frozen python -m se.earth.lithology`. FORCE expert lithofacies, training wells only: 60 pilot wells, 749,882 samples, 55 units. FORCE spells Sodir names in ASCII (ROEDBY FM.); mapped back to Sodir spelling so units join the tops. Estimate: the unit's class shares updated by nearby wells (Gaussian weights, ell) and shrunk to the unit mean (K).
- **Found (held-out 40 km blocks)** Per-sample accuracy: model 0.663, unit mean 0.654, majority class (shale) 0.623. FORCE penalty-matrix score -0.951 vs -0.980 vs -1.110. Brier 0.162 vs 0.175. Best ell 25 km, K 300. Report-text lithology words (9,814 rows) lower the Brier score slightly (0.160) but not the penalty score: left out.
- **Note** In the pilot the Utsira Formation is 68 percent shale in FORCE wells (the lexicon: "marine sandstones and claystones"); it counts as shale-dominated here.

## L064 P3.2 Porosity and permeability [done]
- **Method** `uv run --frozen python -m se.earth.poroperm`. RealPore plugs in the pilot: 95,024 with a unit and depth, 264 wells, averaged to 678 well-unit values.
- **Found (held-out 40 km blocks, porosity points / log10 mD)** Unit mean 7.18 / 1.22; Athy compaction only 5.69 / 1.02; unit offset on the Athy curve + neighbours 4.90 / 0.97. Fitted phi0 38.5 percent, c 0.295 per km (Sclater and Christie 1980 sandstone 0.27). Permeability from porosity per unit (log10 k = a + b phi) + neighbour residual.
- **Guard** Cores sample reservoirs; the porosity model describes cored rock, mostly sandstone.

## L065 P3.5 Fluids and P3.6 Seal [done]
- **Fluids** `uv run --frozen python -m se.earth.fluids`. 12,908 rows in 636 wells: FactPages HC formations (642, strong), DST flow (112) and no flow (12), DRY wells (2,278, medium), units not listed as HC in HC wells (8,787, weak), SHOWS (1,077, not counted). Most HC units: Brent Gp 122, Tarbert 94, Sognefjord 72, Ness 55, Statfjord 50, Frigg 41. Blank FactPages formation names (632) dropped.
- **Seal** Per grid layer: contiguous thickness of shale-dominated units directly above (shale + half heterolithic >= 0.6 in FORCE wells). Median 166 m inside the pilot.

## L066 P4.1 Rules tested on our data [done]
- **Method** `se/knowledge/rules/earth.yaml` (9 rules, sources and guards) and `uv run --frozen python -m se.earth.rules` -> `earth_rules_report.json`. Lexicon quotes (Sodir, in ncs.duckdb) are "sourced"; standard references not re-read this session are "sourced_unverified".
- **Agrees** Athy (c 0.295 vs 0.27 per km); density porosity vs core (17,230 pairs, 44 wells, r 0.64, bias -1.2 points); Gardner (645,074 samples, median error -0.04 g/cm3, r 0.81); hydrostatic (normal DST EMW 1.025); gradient 27.4 in 25-40; Brent delta (coal share highest in Ness 0.10, sand highest in Etive 0.71); Draupne (median GR 134 vs Heather 95 API, difference 39 [27, 55] by well bootstrap, 91 percent shale).
- **CO2** Supercritical from about 470 m below the seabed at 300 m water (770 m below sea level), 660 m with 90 percent confidence on temperature. A threshold, used in P6.
- **Disagrees: R-SEAL** HC units have less contiguous shale directly above them in the grid than dry units (41 vs 74 m, difference -32 [-57, -4]). The rule is not wrong in geology; the grid's 2 km seal measure does not capture it: HC sits in Brent and Sognefjord under thin Heather and Draupne, while dry units are often deep in thick shale. The seal term enters P6 only as tested: it must earn its place by held-out skill.

## L067 UI: camera, formation cap, full seismic block, memory [done]
- **Camera** The inspector cube now reads its live camera before each redraw (it was reset on every slider move). Big scene: double-click reset off, camera tracked while dragging. A probe (drag, double click, wheel, palette, wells, depth stretch) keeps the view. Script and style links carry a version, so browsers load the new code.
- **Formations** The 3D view showed at most 8 formations (a draw-time guard from L021); now 30, all formations listed.
- **Full block** `/api/seismic/cube` and a "full block" view: the whole survey as a transparent volume (inline x crossline x time, thinned to about 350,000 values), interpreted horizons as surfaces (Smeaheia), wells and gamma ray.
- **Backend pod** memory limit 3 -> 8 GiB, request 512 Mi -> 1 Gi (owner request); patched live and in both manifests (`~/homelab/apps/subsurface-evidence`, `deploy/`). Flux reconciles from git: commit the homelab change or it reverts.

## L068 P5.1 Report facts: prefilter and cost run [in progress]
- **Prefilter** `se/earth/reports.py`: 240,000 pages of 1,765 pilot wellbores read in 81 s; 51,222 candidate pages (show 27,429, pressure 21,618, deviation 5,656, temperature 1,040, porosity 854, permeability 498). The OCR JSON already ships page tags and a page summary.
- **Extraction** Naija-Petro 8B extract profile through the cluster llm service (`kubectl -n llm port-forward svc/llm 18080:80`), 4 parallel slots, JSON with a verbatim quote; a fact is kept only if its quote and number are in the page. The first single-page test returned truncated JSON (fixed: complete objects kept, page counted as a parse error). The 200-page cost run was still running at handoff: results go to `earth/pilot/report_sample_stats.json` and `report_facts_sample.parquet`. Next: read the stats, decide the full run (P5.1), hand-check 100 facts (P5.3).

## L069 P6 Targets with probability and support [done for six targets; CO2 composite]
- **Method** `uv run --frozen python -m se.earth.targets`. Cells = unit x 2 km column from the grid: 208,432 inside the pilot. Per target a logistic model on features computed from training wells only (unit prior, same-unit neighbours within 25 km, sand or shale share, Athy porosity, depth), blocked 40 km CV, Platt cross-fitted, Monte Carlo (100 draws) over feature uncertainty for a 90 percent range, support = data x nearness x held-out skill.
- **Failure fixed** Training rows saw their own label in the neighbour term, so the model over-trusted it (reservoir -0.14, calcareous -0.13 on held-out wells). Each training row now leaves its own well out of its prior and neighbours.
- **Found (deviance gain over the base rate, held-out wells)** Hydrocarbons 0.424 (unit prior alone 0.394); reservoir 0.130 (unit prior -0.011); overpressure 0.232 (0.002); sandy delta 0.757 (0.736); green clay 0.017 (unit prior 0.019: the unit prior is published); calcareous clay -0.039 (base rate published: no skill). Rule: publish the simplest form that is not worse.
- **CO2** P(T > 31.1 C) x P(P > 7.38 MPa) x P(reservoir) x P(seal >= 50 m) x (1 - P(overpressure)); not calibratable (no well observes stored CO2). Checks: Smeaheia Sognefjord 0.40-0.50 and Fensfjord 0.40-0.45 (pilot p95 0.37); Aurora Johansen 0.28, Cook 0.31 (pilot median 0.19).
- **Seal redefined** Contiguous shale directly above gave Johansen at Aurora 0 (Cook sand lies between it and the Drake caprock). Now shale-dominated thickness within 300 m above. R-SEAL then agrees: HC units have 12 m more [3.5, 27.6] than dry units (was a disagreement under the old measure, L066).

## L070 P7.1 Earth API [done, UI page next]
- `se/api/earth.py`: `/api/earth/meta`, `/surfaces` (top and sd per horizon; a unit's thickness is the next surface down), `/target` (cells over a probability and support threshold), `/wells` (FORCE paths, else FactPages heads), `/cell` (evidence chain: depths and sd, p with range, support, held-out skill, nearest same-unit observations, rules with verdicts).
- **Next (P7.2)** An "Earth model" page (stage2 layout): group tops as surfaces with thickness, target cells as markers coloured by p and faded by support, wells, click a cell for `/api/earth/cell`. Then the full-block interpolation and a tied-horizon layer in the world view (owner requests), gamma-ray property volume by kriging in stratigraphic coordinates (owner question).

## L071 P7.2 Earth model page, gamma ray between wells, tied horizons in 3D [done]
- **Earth model page** (first tab): group tops as surfaces with their sd and nearest pick on hover; a group fills the space down to the next top, so thickness is visible. Target cells as dots, coloured by probability and faded by support (three bins); wells on their paths (magenta, away from the viridis greens). Click a cell for its evidence chain from `/api/earth/cell`: depth interval and sd, probability with its 90 percent range, support, how the target was published and its held-out gain, the nearest observations of the same unit, and the rules with verdicts. The evidence-engine target picker is hidden on this page (it does not apply).
- **Gamma ray between wells** `uv run --frozen python -m se.earth.gamma`. FORCE GR (train only) averaged per well and unit: 835 well-units, 60 wells, 52 units. Per cell: unit mean updated by nearby wells (20 km), shrunk to the unit mean. Held-out 40 km blocks: RMSE 24.8 gAPI vs unit mean 25.8 and pilot mean 32.1. A small gain: most of what wells say about GR is the unit itself; within a unit a log varies by about 11 gAPI (median sd). On the page: "colour cells by gamma ray". Seismic attributes as a secondary variable (co-kriging) would be the next step where the seismic is tied.
- **Tied seismic horizons in the 3D scene** `/api/earth/tied`: Shetland, Sognefjord and Fensfjord from the L058 tie, in depth, placed by lat/lon; a switch in the Seismic section.
- **Full block** Detail selector (350 k / 900 k / 1.8 M values: smoother, heavier). Holes inside the survey are filled from the nearest kept trace within 2 nodes (none in GN1101; TNE01 and Sleipner have irregular edges).
- **Tests** 45 backend tests (new `tests/test_earth_model.py`: velocity fit, own-well exclusion, fact grounding, rules file, pressure QC, grid order, target arrays, API cell). Browser self-test passes including the earth page (draw, cell evidence, threshold, gamma ray). The probability is the mean over realisations; with a skewed spread it can lie above the 95th percentile (sandy delta: 17 percent of cells), so the test checks p05 <= p95 instead.

## L072 P5 Report facts: measured, not adopted [done, negative]
- **Cost (P5.1)** 200 random candidate pages, Naija-Petro 8B extract profile, 4 slots: 521 pages per hour, 1,410 prompt and 1,589 completion tokens per page (near the 2,000 cap: 156 pages truncated, 44 request errors). All 51,222 candidates would take about 98 GPU hours. Full run: not started.
- **Facts (P5.2)** 3,197 facts; 1,637 (51 percent) grounded (quote and number on the page). The model invented about 60 fact types beyond the 6 asked for (depth, start_date, slurry_volume ...).
- **Check (P5.3)** Automatic: porosity facts vs RealPore plugs in the same well within 20 m: 15 pairs, median difference 9.1 points, 33 percent within 5 points; no temperature fact matched a DST. Hand check of 100 grounded facts of the six types (`earth/pilot/report_handcheck.parquet`, one judgment each): 17 correct, 11 unverifiable (a bare table number), 72 wrong: precision 0.17 (0.28 if every unverifiable one were right). Pressure 2 of 28 (equipment and casing tests, drawdown, mud weight); shows 7 of 40 (drilling notes); porosity 1 of 12 (axis labels, mud weight); permeability 3 of 6 (mobility mD/cP); temperature 1 of 7 (gas percent, circulating); deviation 3 of 7 (4 unverifiable).
- **Decision** Report facts do not enter the earth model (measured precision 0.17-0.28; the plan requires a measured precision first). What would change it: a JSON-schema grammar that allows only the six types, one prompt per fact type with negative examples (test pressures, mobility, gas percent), page selection by the shipped page tags, and the 32B model for the rare porosity and temperature pages (2,400 pages, a few hours). Shows remain available from FactPages (wlbContent SHOWS) and the existing report-text descriptions.
- **P5.2 v2 [code ready, not measured]** `reports.llm(..., v2=True)`: the output is constrained by a JSON schema (the six fact types only, at most 12 facts, 200-character quotes) and the prompt lists what is not a fact (equipment pressure tests, drawdown, mud weight, mobility, gas percent, circulating temperature, drilling operations, axis labels). The re-run on 80 of the same pages could not start: at 23:35 the GPU arbiter kept `llm` as the holder with no lease while the llm deployment stayed at 0 replicas (proxy: connection refused). Re-run with `sample_run(..., v2=True)` once the llm service answers, then hand-check again; facts enter the model only if precision clears the bar.
- **P5.2 v2 run and check [done, negative]** The llm service came back after the stale hold cleared (00:15). Same 80 pages: 0 request and 0 parse errors (was 44 and 156 of 200), only the six types, 941 facts, 70.5 percent grounded (was 51), 988 completion tokens per page, 655 pages per hour. Hand check of 96 grounded facts (`report_handcheck_v2.parquet`): 3 correct, 7 unverifiable, 86 wrong: precision 0.03 (0.10 if every unverifiable one were right), lower than v1 (0.17). Constrained decoding makes the model fill the six types even when a page has none: drilling operations become "shows" (2 of 40 real), equipment and pump pressures become "pressure" (1 of 40), axis labels become porosity (0 of 7), test pressures and contact depths become temperature (0 of 9). Prompt exclusions were ignored.
- **P5 verdict** Measured twice, on the same pages, with a hand check each time: the 8B extractor is not fit to feed the earth model (precision 0.03-0.17). Report facts stay out. The earth model uses report text only through the existing description rows (lithology words, L063), where it was also tested and left out. A next attempt would need a stronger model per fact type on pages selected by the shipped page tags, and a hand check before any use.
