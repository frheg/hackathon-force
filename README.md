# hackathon-force

**Subsurface Studio**: ten tools for the FORCE VibeCode Hackathon (Stavanger, 19 to 20 November 2026, "create your
favourite oil and gas app in 2 days"). Each tool takes one slow, expensive task in exploration, drilling, production or
late life, runs it on public Norwegian Continental Shelf data, and uses a language model only where reading,
cross-checking or writing is the bottleneck. Research behind the choices: [docs/reports](docs/reports/) (the ranked
report), [docs/research_notes](docs/research_notes/), [docs/research.md](docs/research.md) (the event) and
[docs/oil-gas-llms.md](docs/oil-gas-llms.md) (domain models and GPU profiles).

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

Guard rails: the SQL runs read-only with file and network access off; every model answer cites FactPages tables
(`[F:tops]`) or report passages (`[S3]`); the model never reads seismic images, only numbers; wells and fields are
matched by a name normaliser; every request has input limits; model errors and a busy GPU come back as a sentence.

## Data

About 1.9 GB in `data/`, not in git. Everything is public:

| Source | Licence | Fetch |
|---|---|---|
| Sodir FactPages: 22 tables (fields, wellbores, tops, casing and LOT, mud, DST, cores, drilling histories, documents, facilities, production, reserves, discoveries) | NLOD 2.0 | `fetch_data.py sodir` |
| FORCE 2020 lithology well logs (98 + 10 wells) | CC BY 4.0 | `fetch_data.py force2020` |
| DISKOS-QA (1,027 questions over 1,690 Diskos report passages) | NLOD 2.0 | `fetch_data.py diskosqa` |
| Volve daily drilling reports (1,759, WITSML) | CC BY 4.0 (Hugging Face copy) | `fetch_data.py volve` |
| F3 Netherlands seismic with facies labels (stand-in for NCS seismic) | CC BY 4.0 | `fetch_data.py seismic` |

## Build and run

From `app/`, once:

    uv run python fetch_data.py                 # all sources, or name some
    uv run python -m sketches.reports           # passage index (bge-m3 embeddings in Qdrant), about 30 min on CPU
    uv run python -m sketches.train_logs        # lithology model, about a minute
    uv run python -m sketches.seismic           # seismic index and its scores, about a minute
    uv run python -m sketches.scorecard retrieval   # DISKOS-QA retrieval scores, a few minutes

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
                           train_logs.py
    app/pages/             one HTML page per tool, style.css and shell.js shared (plain JS; Plotly and Leaflet)
    app/tests/             pytest
    data/                  datasets, indexes and caches (ignored by git)
    docs/                  research, the report, model notes

## Swapping in the event's data

- DiskosQA chunks or Sodir's JSON well documents: write them as `data/diskosqa/chunks.parquet` (chunk_id, text,
  doc_name, wellbores, fields, formations) and rerun `sketches.reports`.
- Wells (LAS): map curve names to the FORCE 2020 ones and append to `train.csv` / `hidden_test.csv`.
- Seismic (SEG-Y): write a numpy cube (inline, trace, sample) next to the F3 files, add it to `CUBES` in
  `sketches/seismic.py`, rebuild.
- Azure OpenAI or other models: set `LLM_URL` and `LLM_MODEL`.
