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
