# Subsurface Evidence / Subsurface Studio

**Subsurface Evidence** answers one screening question: which Smeaheia legacy wells report a reservoir or primary-seal encounter, and what needs checking? The 3D review separates stratigraphic picks, sampled trajectories, reported operations and unknowns. **Research** preserves the wider NCS model. **Subsurface Studio** also contains the original FORCE VibeCode Hackathon tools (Stavanger, 19 to 20 November 2026).

## Start in 3D

Open **Smeaheia**. Select a well by name or on the scene. Five of six wellheads in the indexed survey footprints report both Sognefjord and Draupne; one has no qualifying picks. The outside reference well is separate. These are not verified crossings of a storage boundary or findings of barrier integrity. Start with the [local run guide](subsurface-evidence/README.md).

**Well tracks** searches 8,496 registered exploration and development boreholes. Only 2,034 have positioned records in the checked sources. On **Smeaheia**, turn on **Colour wellheads by rock + pressure rule** to see a candidate (+), below threshold on supported metres (−), or insufficient evidence (?). Colours are not plug-test results. [Claude handoff: current state and next task](subsurface-evidence/HANDOFF.md).

| What | Current state |
|---|---|
| **Rock + pressure interval screen** | At `31/3-3`, the longest interval meeting both conditions above Sognefjord is 13 m; the scenario requires 30 m. Five other local wells lack enough evidence. The outside reference has a 70 m interval; its result is not transferred. No barrier or CO₂ pressure prediction. |
| **Depth prediction gate** | On 20 path-supported Horda wells in five held-out spatial blocks, nearest-well MAE was 676 m vs 604 m for the training median. No candidate depth filled in. |
| **Horda demo** | Frozen build `f46ffd5abca4`: 186,538 model cells, modelled porosity, a legacy-well proximity screen, and a versioned export. Ready locally; not activated on k3s. |
| **Smeaheia seismic** | Time-domain context and separately labelled published picks. No independently verified time-to-depth tie; the first seismic sample is not the seabed. |
| **Porosity** | Measured logs improved predictions of held-out core plugs. Adding rock-physics transforms to those logs showed no reliable extra gain. The template does not feed production probabilities. Neither test validates undrilled cells. |

[Model plan](subsurface-evidence/PLAN.md) · [Experiment log](subsurface-evidence/LOG.md) · [Data guide](docs/data-guide.md) · [Seismic sources and missing controls](docs/seismic-data.md)

## Original Studio tools

| Path | Tool | What it does | Measured |
|---|---|---|---|
| `detective/` | **Diskos Detective** | Agent over Diskos report passages and FactPages: cited answers, a claim-by-claim check of each answer against its passages, one-minute wellbore dossiers, the DISKOS-QA scorecard | evidence in the top 5 for 92 % of supported DISKOS-QA questions (filtered hybrid search) |
| `barrier/` | **Barrier Ledger** | Legacy wells around a CO2 store screened by three schemes, disagreements and data gaps shown, plugs and cement read from each well's file with citations | |
| `spud/` | **Spud Brief** | Offset wells' mud weights, leak-off tests and drilling hazards by depth, the drilling window (leak-off trend against offset mud), a brief in Havtil's format, backtested on real wells | |
| `tieback/` | **Tie-back Matchmaker** | Undeveloped discoveries ranked against producing hosts, an outside-view production profile from analogue fields, a Monte Carlo chance of producing before the host closes, a screening memo | 92 discoveries, 499 MSm3 o.e. |
| `losttime/` | **Lost Time Hunter** | Reported, invisible (slow drilling) and hidden (model-found) lost time in Volve's 1,759 daily drilling reports, priced per rig day; lessons learned cited to report lines | 22 % of rig time reported NPT, 5 % more in slow drilling |
| `doctor/` | **Data Doctor** | FORCE 2020 log files against FactPages (positions, depth references, formation tops) and report statements against FactPages; a trust score per wellbore | 24 of 108 wells fully consistent |
| `seismic/` | **Seismic Lookalike** | Click a seismic feature, find look-alike patches by texture or by a learned facies metric, scored on a held-out block | 76 % / 78 % right facies in the top 10 (chance 42 %) |
| `copilot/` | **NCS Copilot** | Plain-language questions over FactPages as read-only SQL, with a map | |
| `logs/` | **Log Lens** | Lithology from logs on 10 unseen wells, explained interval by interval | 79.5 % accuracy, competition score -0.513 (winner -0.47) |
| `decline/` | **Field Pulse** | Production, Arps decline from a chosen month, forecast against Sodir's remaining reserves, a field brief | |
| `status/` | Connections | what the app can reach | |
| `atlas/` | **Data Atlas** | A dashboard over every dataset, for learning the data: what each holds, key numbers, charts with a line on how to read them, sample records, how the datasets join, a well lookup across all of them, and a glossary. Set to seismic for the event (`FOCUS` in `sketches/atlas.py`): Adele and F3 only, with a slice explorer (inline, crossline, time slice; amplitude or coherence; F3 labels), trace, spectrum and SEG-Y header per click, and QC charts. Pages: **Start here** (every word explained with the cube's numbers), **Resolution & granularity** (measured spectra and correlation, a calculator, a feature-size checker, a patch planner), a 3D box beside the explorer (the current slice strong, a faint stack of the other slices through it), dark/light toggle. Guide: `docs/seismic-guide.md` | |

Guard rails: the SQL runs read-only with file and network access off; every model answer cites FactPages tables
(`[F:tops]`) or report passages (`[S3]`); the model never reads seismic images, only numbers; wells and fields are
matched by a name normaliser; every request has input limits; model errors and a busy GPU come back as a sentence.

## Data

Raw data, indexes and generated model builds live in `data/`, not in Git. Some sources require licence acceptance or sign-in. Datasets supplied by the organisers are kept separately in `data/official/`.

**From the organisers** (`data/official/`, all CC BY 4.0, Zenodo):

| Folder | Dataset | Size | Fetch |
|---|---|---|---|
| `completion_reports/` | 4,462 NCS wellbore completion reports, PDF and JSON (page text as markdown, AI page summaries and tags, quality grades), plus Diskos metadata ([24320092](https://doi.org/10.5281/zenodo.24320092)) | 120 GB unpacked, one folder per wellbore | `fetch_data.py completion` |
| `text/` | OCR text of Norwegian (Diskos, relinquishment), UK and Dutch reports, page by page, with 1,368 hand-labelled pages ([10775273](https://zenodo.org/records/10775273)) | 6.1 GB | `fetch_data.py text` |
| `realpore/` | Core porosity, permeability and rock type, 372,930 plugs from 1,240 wells; credit GeoProvider, http://geoprovider.no/ ([4723018](https://zenodo.org/records/4723018)) | 45 MB | `fetch_data.py realpore` |
| `force2020/` | FORCE 2020 wells as LAS, casing depths and lithostratigraphy sheets ([4351156](https://zenodo.org/records/4351156)) | 170 MB | `fetch_data.py force2020_las` |
| `adele/` | Adele 3D seismic, NW Australia, SEG-Y; credit Geoscience Australia ([4299758](https://zenodo.org/records/4299758)) | 3.5 GB | `fetch_data.py adele` |
| `ksat/` | KSAT satellite radar for seep detection, handed out at the event | 2.1 GB | copy in by hand |

**Found before the event** (`data/`):

| Source | Licence | Fetch |
|---|---|---|
| Sodir FactPages: 22 tables (fields, wellbores, tops, casing and LOT, mud, DST, cores, drilling histories, documents, facilities, production, reserves, discoveries) | NLOD 2.0 | `fetch_data.py sodir` |
| FORCE 2020 lithology well logs as CSV (98 + 10 wells; the same wells as the mail's LAS) | CC BY 4.0 | `fetch_data.py force2020` |
| DISKOS-QA (1,027 questions over 1,690 Diskos report passages) | NLOD 2.0 | `fetch_data.py diskosqa` |
| Volve daily drilling reports (1,759, WITSML) | CC BY 4.0 (Hugging Face copy) | `fetch_data.py volve` |
| F3 Netherlands seismic with facies labels (stand-in for NCS seismic) | CC BY 4.0 | `fetch_data.py seismic` |
| Parihaka 3D (New Zealand) with six facies labels, 1.7 GB | CC BY 4.0 | `fetch_data.py parihaka` |
| Penobscot 3D (Nova Scotia) with seven interpreted horizons and dense labels, 2.3 GB | CC BY 4.0 | `fetch_data.py penobscot` |
| FaultSeg3D: 220 synthetic cubes with fault labels | CC BY-NC 4.0 | `fetch_data.py faultseg3d` |

More public seismic, including what needs your own sign-in (Volve, Smeaheia, Sleipner 4D): `docs/seismic-data.md`.

Zenodo serves each connection at 2 to 3 MB/s, so large files come down as 64 MB pieces over ten connections
(about 20 MB/s); an interrupted download resumes, and every file is checked against Zenodo's md5.

## Build and run the original Studio tools

From `app/`, once:

    uv run python fetch_data.py                 # all sources, or name some
    uv run python -m sketches.reports           # passage index (bge-m3 embeddings in Qdrant), about 30 min on CPU
    uv run python -m sketches.train_logs        # lithology model, about a minute
    uv run python -m sketches.seismic           # seismic index and its scores, about a minute
    uv run python -m sketches.scorecard retrieval   # DISKOS-QA retrieval scores, a few minutes
    uv run python -m sketches.atlas             # the Data Atlas profiles (data/atlas/), about a minute
    uv run python -m sketches.greenclay         # green clay labels from all completion reports (docs/greenclay.md), about a minute
    uv run python -m sketches.atlas_seis        # seismic explorer: Adele as int8 copies (1.6 GB) and both cube profiles, under a minute

Then:

    LLM_URL=http://localhost:8080/v1 LLM_MODEL=<model> uv run uvicorn app:app --reload

or in Docker (`docker build -t hackathon-force . && docker run -p 8000:8000 -v "$PWD/data:/data" -e LLM_URL=... hackathon-force`).
Open http://127.0.0.1:8000/. Behind a proxy that keeps a path prefix, set `ROOT_PATH`.

| Variable | Default | |
|---|---|---|
| `LLM_URL`, `LLM_MODEL` | `http://llm.llm/v1`, `qwen3.6-35b` | OpenAI-compatible chat endpoint; the sidebar's picker overrides the model per request |
| `EMBED_URL`, `EMBED_MODEL` | `http://llm-cpu.llm/v1`, `bge-m3` | embeddings for the passage index |
| `QDRANT_URL` | `http://qdrant.qdrant:6333` | vector store |
| `DATA_DIR` | `../data` | |
| `ROOT_PATH` | empty | path prefix kept by a proxy |

Tests (data needed, no model: it is stubbed):

    uv run pytest -q

The answer scorecard (GPU time, about four model calls per question per mode):

    uv run python -m sketches.scorecard answers --n 40

## Layout

    app/app.py             the registry of tools, error handling, the path prefix, the model picker
    app/common.py          model calls (retries, JSON schemas), embeddings, the FactPages database, wellbore lookups
    app/fetch_data.py      downloads the data
    app/sketches/          one module per tool, plus reports.py (search), wells.py (well facts), scorecard.py,
                           train_logs.py, atlas.py (the data dashboard and its profiles), atlas_seis.py (its seismic explorer)
    app/pages/             one HTML page per tool, style.css and shell.js shared (plain JS; Plotly and Leaflet)
    app/tests/             pytest
    subsurface-evidence/   3D model, evidence API, UI, model plan and experiment log
    data/                  datasets found before the event, indexes and caches (ignored by git)
    data/official/         the datasets the organisers sent
    docs/                  research, the report, model notes

## Swapping in the event's data

- DiskosQA chunks or Sodir's JSON well documents: write them as `data/diskosqa/chunks.parquet` (chunk_id, text,
  doc_name, wellbores, fields, formations) and rerun `sketches.reports`.
- Wells (LAS): map curves and depth units explicitly, and keep new wells as separately tracked inputs. Do not edit the FORCE benchmark or use its hidden test labels.
- Seismic (SEG-Y): write a numpy cube (inline, trace, sample) next to the F3 files, add it to `CUBES` in
  `sketches/seismic.py`, rebuild.
- Azure OpenAI or other models: set `LLM_URL` and `LLM_MODEL`.


## Dev shell (nix)

The app ships as Docker; this flake is only a shell for working on the data (SEG-Y tools, notebooks, GPU training).

    git add flake.nix flake.lock tools .envrc   # a git flake only sees tracked files
    nix develop                # or let direnv do it: `direnv allow` once, then cd in (the `.envrc` is `use flake`)
    nix develop .#viz          # + ParaView and PyVista for 3D
    nix develop .#gpu          # then `gpu-setup` once: .venv-gpu with PyTorch (CUDA 12.8, the 5060 Ti is sm_120)

Do not use `nix develop path:.`: a `path:` flake copies the whole directory, `data/` included (125 GB), into the nix store.

In the shell: `segy info|text|slice|trace FILE` (headers, geometry, amplitudes, dead traces and spikes, a PNG of any
slice; `tools/segy`), `jupyter lab`, segyio, obspy, devito, xarray, zarr, dask, numba, scikit-image, rasterio, gdal,
duckdb, ffmpeg, nvtop and more (`flake.nix`).
