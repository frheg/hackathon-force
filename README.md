# hackathon-force

**Subsurface Studio**: ten tools for the FORCE VibeCode Hackathon (Stavanger, 19 to 20 November 2026, "create your
favourite oil and gas app in 2 days"). Each tool takes one slow, expensive task in exploration, drilling, production or
late life, runs it on public Norwegian Continental Shelf data, and uses a language model only where reading,
cross-checking or writing is the bottleneck. Research behind the choices: [docs/reports](docs/reports/) (the ranked
report), [docs/research_notes](docs/research_notes/), [docs/research.md](docs/research.md) (the event) and
[docs/oil-gas-llms.md](docs/oil-gas-llms.md) (domain models and GPU profiles) and [docs/data-guide.md](docs/data-guide.md) (every dataset and term explained).

## The tools

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
| `atlas/` | **Data Atlas** | A dashboard over every dataset, for learning the data: what each holds, key numbers, charts with a line on how to read them, sample records, how the datasets join, a well lookup across all of them, and a glossary of 107 terms | |

Guard rails: the SQL runs read-only with file and network access off; every model answer cites FactPages tables
(`[F:tops]`) or report passages (`[S3]`); the model never reads seismic images, only numbers; wells and fields are
matched by a name normaliser; every request has input limits; model errors and a busy GPU come back as a sentence.

## Data

About 125 GB in `data/`, not in git. Everything is public. The datasets the organisers sent by mail (17 November
2026) are kept apart in `data/official/`, as the most official source; the ones found before the event stay in
`data/`.

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

Zenodo serves each connection at 2 to 3 MB/s, so large files come down as 64 MB pieces over ten connections
(about 20 MB/s); an interrupted download resumes, and every file is checked against Zenodo's md5.

## Build and run

From `app/`, once:

    uv run python fetch_data.py                 # all sources, or name some
    uv run python -m sketches.reports           # passage index (bge-m3 embeddings in Qdrant), about 30 min on CPU
    uv run python -m sketches.train_logs        # lithology model, about a minute
    uv run python -m sketches.seismic           # seismic index and its scores, about a minute
    uv run python -m sketches.scorecard retrieval   # DISKOS-QA retrieval scores, a few minutes
    uv run python -m sketches.atlas             # the Data Atlas profiles (data/atlas/), about a minute

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
                           train_logs.py, atlas.py (the data dashboard and its profiles)
    app/pages/             one HTML page per tool, style.css and shell.js shared (plain JS; Plotly and Leaflet)
    app/tests/             pytest
    data/                  datasets found before the event, indexes and caches (ignored by git)
    data/official/         the datasets the organisers sent
    docs/                  research, the report, model notes

## Swapping in the event's data

- DiskosQA chunks or Sodir's JSON well documents: write them as `data/diskosqa/chunks.parquet` (chunk_id, text,
  doc_name, wellbores, fields, formations) and rerun `sketches.reports`.
- Wells (LAS): map curve names to the FORCE 2020 ones and append to `train.csv` / `hidden_test.csv`.
- Seismic (SEG-Y): write a numpy cube (inline, trace, sample) next to the F3 files, add it to `CUBES` in
  `sketches/seismic.py`, rebuild.
- Azure OpenAI or other models: set `LLM_URL` and `LLM_MODEL`.
