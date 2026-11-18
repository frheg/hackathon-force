# FORCE VibeCode Hackathon 2026: event data, DiskosQA and open NCS datasets

Research date: 2026-11-17. Note on method: every sodir.no page (event page, release-of-data pages) returned HTTP 403 to automated fetches, so facts from sodir.no below come from search-engine snippets of those pages, not from a full read. These are flagged "(snippet)". LinkedIn returned HTTP 999, so LinkedIn claims are also snippet-only.

## 1. What is DiskosQA?

### Takeaway
DiskosQA (published as "DISKOS-QA" / "FORCE_QA_public.csv") is an open, mostly LLM-generated question-answer benchmark of about 1,000 QA pairs grounded in OCR'd text from Diskos well reports. It was built in the FORCE ecosystem (operators + Sodir) on top of the FORCE 2023 LLM hackathon text corpus, with a Neo4j knowledge graph, Azure OpenAI and DeepEval. It is almost certainly the "DiskosQA data" that the VibeCode hackathon advertises.

### Cited Findings
- Hugging Face dataset `porestar/diskos_qa` describes DISKOS-QA as "an open question-answering benchmark for subsurface and petroleum-domain workflows, built from public DISKOS-related oil and gas documents", for domain QA benchmarking, RAG evaluation, metadata-aware slicing and studying synthetic QA generation - [HF dataset card](https://huggingface.co/datasets/porestar/diskos_qa)
- Size/format on HF: 1,027 rows, one `train` split (no official train/val/test split documented), about 9.94 MB, CSV auto-converted to Parquet - [HF dataset card](https://huggingface.co/datasets/porestar/diskos_qa)
- 16 columns: `Question_ID`, `Question`, `Answer`, `Content` (retrieved source passages), `Chunk_IDs`, `Document_id`, `Document_name`, `Well_names`, `Wellbore_names`, `Field_names`, `Formation_names` (list-valued entity metadata), `Filter_type`, `Filter_name` (retrieval constraint, e.g. formation), `Topic` (e.g. "Rock and Core"), `Evolutions` (e.g. "Concretizing", "Reasoning"), `Entailed` (bool: answer supported by context) - [HF dataset card](https://huggingface.co/datasets/porestar/diskos_qa)
- Example row: Q "What percentage of GECO Klinkenberg-corrected horizontal permeability measurements on 9/2-1 Sandnes Formation cores exceed 100 mD?" A "Less than 10%." Filter formation = SANDNES FM, Topic Rock and Core, Entailed true - [HF dataset card](https://huggingface.co/datasets/porestar/diskos_qa)
- Generation pipeline: (1) retrieve context chunks from a Neo4j knowledge graph filtered by wells, fields, formations and topic embeddings; (2) synthesize QA pairs with Azure OpenAI; (3) evaluate with DeepEval and custom checks; (4) optional human feedback via Streamlit. The card states the benchmark is "mainly machine-generated and programmatically filtered, not manually annotated" and warns of generation/selection bias - [HF dataset card](https://huggingface.co/datasets/porestar/diskos_qa)
- Source repo: [github.com/georgeghon/DISKOS-QA](https://github.com/georgeghon/DISKOS-QA). README credits the FORCE consortium with Equinor, AkerBP, ConocoPhillips, DNO, OMV, Inpex Idemitsu and Sodir; no individual authors, no paper, no citation block. Final file `benchmark/dataset/FORCE_QA_public.csv`. Repo has `ForceQA/` (pipeline, synthesizer, evaluator, graph, embedding), `NEO4J/` (Cypher loaders, raw chunk/well/field CSVs, NER utilities using GLiNER and spaCy with processed lookup tables), `data/` (example DISKOS data), `examples/` notebooks, `streamlit_app/` (feedback UI backed by Supabase), `tests/`. ~115 commits, 12 stars, 7 forks at time of fetch, no releases - [GitHub README](https://github.com/georgeghon/DISKOS-QA)
- Default models in the pipeline: `gpt-5-mini` for generation, `o4-mini` as critic/judge, `text-embedding-ada-002` for embeddings; question styles closed or multiple-choice; scoring for clarity, instruction adherence, hallucination and closed-book answerability; optional Faithfulness metric - [GitHub README](https://github.com/georgeghon/DISKOS-QA)
- Licence: NLOD 2.0 for the DISKOS-QA repo; the upstream Zenodo corpus is CC BY 4.0 - [GitHub README](https://github.com/georgeghon/DISKOS-QA); [HF dataset card](https://huggingface.co/datasets/porestar/diskos_qa)
- Upstream text: "Large Oil and Gas industry text dataset from Norwegian, UK and Dutch public oil and gas documents", FORCE NETWORK Group, publisher "FORCE Hackathon 2023", published 2024-03-03, DOI 10.5281/zenodo.10775273 - [Zenodo](https://zenodo.org/doi/10.5281/zenodo.10775273)
- A LinkedIn post (snippet only, not verifiable) describes DISKOS-QA as an open benchmark for judging LLMs on subsurface/energy knowledge with "1100 crafted question answer pairs and 50k curated text snippets", a joint industry effort under FORCE (Equinor, ConocoPhillips, OMV and others with Sodir), built on an open DISKOS corpus, with a synthetic QA pipeline adaptable to other domains - [LinkedIn profile, Dylan Loss (snippet via search)](https://no.linkedin.com/in/dylan-loss-8b541a105)
- Related but different: FormationEval (arXiv 2601.02158, Jan 2026), a 505-question multiple-choice petroleum geoscience benchmark; top models score above 97% - [arXiv](https://arxiv.org/abs/2601.02158v1)
- Context: Equinor (Daniel Dura) building a RAG subsurface assistant with groundedness evaluation and a reference set of authentic queries; Geo365 notes Sodir is working with FORCE "aimed at building shared datasets" (Nov 2025) - [Geo365 "Towards a trusted assistant"](https://geo365.no/?p=58101)

### Inferences
- "DiskosQA data" at the hackathon is very likely the DISKOS-QA benchmark CSV plus, possibly, the ~50k curated chunks and Neo4j graph assets (well/field/formation lookup tables) from the repo. The "50k snippets" matches the LinkedIn description but I could not confirm the snippet count in the public repo.
- Row count discrepancy: HF shows 1,027 rows vs "1100" in the LinkedIn post; likely 1,100 generated, ~1,027 kept after filtering, or the post was rounded. Unconfirmed.
- Natural hackathon uses: RAG over Diskos report chunks evaluated against DISKOS-QA (the dataset is explicitly built for RAG eval); entity-aware search by well/wellbore/field/formation; a "well report assistant" with citations to `Document_name`.
- The HF uploader `porestar` is a different account from `georgeghon`; possibly a mirror by a FORCE participant (Lukas Mosser, who ran the 2023 hackathon starter pack, used the handle "porestar" historically, but this is my recollection, not sourced).

### Gaps
- No paper, DOI or official FORCE/Sodir announcement page for DISKOS-QA was found.
- Exact contents of the "DiskosQA data" package handed out at the event (QA CSV only, or also the chunk corpus/graph) are not public.
- Language mix (EN vs NO) of the questions not verified.

## 2. What is Diskos, which documents does it hold, and what is public?

### Takeaway
Diskos is Norway's national E&P data repository (seismic, well, production data and reports), administered by Sodir and operated by Halliburton/Landmark since the 2023 "Diskos 2.0" upgrade. Most well and seismic data becomes public after a 2-year confidentiality period; interpreted data moved from 20 to 5 years in 2023. Non-members order released data via the Diskos Public Portal.

### Cited Findings
- Diskos 2.0 is designed to handle over 28 PB (including a copy) in a multi-cloud environment, built on Landmark's iEnergy platform; operated by Halliburton/Landmark and administered by the NPD (now Sodir); available to 79 Diskos members (oil companies, service companies, academia) - [Oilfield Technology, 2023-05-30](https://www.oilfieldtechnology.com/exploration/30052023/halliburton-upgrades-norwegian-petroleum-national-data-repository/)
- Diskos "Trade" module for data swaps is based on Kadme's WhereOil - [Oilit 2023](https://oilit.com/HTML_Articles/2023_2_5.php)
- About Diskos (Sodir page, not fetched due to 403) - [sodir.no/en/diskos/About-us](https://sodir.no/en/diskos/About-us); anniversary publication PDF - [Diskos anniversary publication](https://www.sodir.no/globalassets/3-diskos/documents/diskos_anniversary_publication_small.pdf)
- June 2023: about 30,000 datasets made public at once, many interpreted datasets previously confidential for 20 years (snippet) - [Sodir news 2023](https://www.sodir.no/en/whats-new/news/general-news/2023/30000-data-sets-are-now-publicly-accessible)
- Confidentiality periods (snippet): interpreted data changed from 20 to 5 years ("all interpreted data more than 5 years old as of 1 January 2028 will be released"); other data 2 years; commercially available (multi-client) data 10 years; interpreted data from relinquished areas can be released after 1 year; ~6,000 datasets from relinquished areas released Oct 2023 - [Sodir: NPD releasing more data](https://sodir.no/en/whats-new/news/general-news/2023/the-npd-is-releasing-even-more-data-to-the-public); [Release of data](https://www.sodir.no/en/facts/data-and-analyses/release-of-data/)
- Access (snippet): Diskos members download released data directly; non-members order via the Diskos Public Portal; the overview of released data is open to everyone through that portal - [Access to released data](https://www.sodir.no/en/facts/data-and-analyses/release-of-data/access-to-released-data/)
- Diskos report text exists in bulk in the FORCE 2023 corpus: "Norway - Diskos reports.csv" is 5.7 GB of OCR'd page text; also "Norway - Norwegian Petroleum Directorate relinquishment reports.csv" 24.7 MB - [Zenodo 10775273](https://zenodo.org/doi/10.5281/zenodo.10775273)
- A 57 TB palynology dataset is available in Diskos (search summary of a Sigma2/Diskos-related source; not verified at primary) - [Sigma2](https://www.sigma2.no/node/373)

### Inferences
- Document types in the Diskos corpus visibly include core analysis reports (the DISKOS-QA example is a GECO core permeability report for 9/2-1); final well reports, completion logs and DST reports are standard Diskos well-report types but I did not find a primary source listing them.
- "Wells" data at the event is likely released Diskos well logs (LAS/DLIS) and reports for a subset of wells; seismic likely a released survey (SEG-Y) or a CO2DataShare volume. Guess.

### Gaps
- URL of the current Diskos Public Portal not verified (sodir.no blocked).
- Precise list of Diskos document categories and counts not found.

## 3. Which open NCS datasets exist?

### Takeaway
Fully open, scriptable: Sodir FactPages/FactMaps (NLOD, CSV/XLS/XML + REST/OGC), FORCE 2020 well logs (118 wells, NLOD), FORCE 2023 text corpus (6.1 GB, CC BY 4.0), DISKOS-QA (NLOD). Open on registration with special licences: Volve (Equinor Open Data Licence), CO2DataShare (Smeaheia, Sleipner, Northern Lights 31/5-7 Eos). Released Diskos data needs ordering via the portal.

### Cited Findings
- Sodir open data is published under NLOD - [Sodir open data](https://www.sodir.no/en/about-us/open-data/); [Name change and open data](https://sodir.no/en/about-us/open-data/name-change-and-open-data/)
- FactMaps REST moved from factmaps.sodir.no/arcgis/rest to `factmaps.sodir.no/api/rest`; a DataService endpoint at `factmaps.sodir.no/api/rest/services/DataService/data` (metadata at `/metadata`) is intended to replace current FactPages download options; example layer: active exploration wellbores `FactMapsED50UTM32/MapServer/203`; shape/CSV packages do not contain all properties, use FGDB or REST/OGC for complete data - [FactPages changelog PDF](https://www.sodir.no/globalassets/1-sodir/om-oss/informasjonstjenester/factpages_changelog.pdf); [FactMaps 3 changelog](https://www.sodir.no/49595f/globalassets/1-sodir/om-oss/informasjonstjenester/karttjenester/factmaps_3_changelog.pdf); [example layer](https://factmaps.sodir.no/api/rest/services/Factmaps/FactMapsED50UTM32/MapServer/203)
- FactPages exports in XLS, XML and CSV - [factpages via data.norge.no](https://data.norge.no/en/datasets/e924e061-9fab-32ca-a8d0-bce1910c60c8); data service listing [data.norge.no](https://data.norge.no/en/data-services/6a60c312-c098-3c12-8181-7b6020c0d249)
- FORCE 2020 lithology competition: well logs from 118 wells (Norwegian sea / North Sea), hand-crafted lithofacies labels, NPD lithostratigraphy and X/Y; NLOD 2.0 - [Zenodo 4351156](https://zenodo.org/records/4351156); code/data/results [GitHub bolgebrygg/Force-2020-Machine-Learning-competition](https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition); results [Sodir](https://sodir.no/en/force/Previous-events/2020/results-of-the-FORCE-2020-lithology-competition); retrospective [PDF](https://sodir.no/globalassets/2-force/2020/seminars/contest-machine-learning/technical_retrospective_force-2020-lithofacies-competition.pdf)
- Volve (Equinor, field produced 2008-2016): ~40,000 files incl. static and dynamic models (Eclipse, RMS), well data, real-time drilling data (WITSML), production data, geophysics incl. interpretations, reports; since Sept 2020 the Equinor Open Data Licence supersedes CC BY-NC-SA 4.0 - [Equinor Volve data sharing](https://equinor.com/energy/volve-data-sharing); [Equinor 2018 news](https://www.equinor.com/news/archive/14jun2018-disclosing-volve-data); formats [Oilit 2018](https://oilit.com/HTML_Articles/2018_3_7.php); licence critique [Agile Scientific "Volve: not open after all"](https://agilescientific.com/blog/2018/10/16/volve-not-open-after-all); overview [SEG wiki](https://wiki.seg.org/wiki/The_North_Sea_Volve_Data_Village)
- Smeaheia (Equinor + Gassnova, released 2021-02-23, dataset-specific open licence): 2D/3D seismic, well reports, pressure/temperature, geomechanics, static geomodel and dynamic simulation model - [CO2DataShare Smeaheia](https://co2datashare.org/dataset/smeaheia-dataset); [SINTEF blog](https://blog.sintef.com/energy/co2datashare-releases-smeaheia-co2-storage-dataset/)
- Sleipner datasets on CO2DataShare since Feb 2020, incl. 2019 Sleipner reference model and several seismic (4D) surveys; Northern Lights released data from confirmation well 31/5-7 Eos - [IEAGHG](https://ieaghg.org/news/sharing-co2-data-with-the-world/); [IEAGHG 65,000 downloads](https://ieaghg.org/news/co2-datashare-reaches-over-65000-downloads/); [Sigma2](https://sigma2.no/node/330)
- FORCE 2023 text corpus (6.1 GB): Diskos reports 5.7 GB, NSTA NDR reports 198.7 MB, Netherlands NLOG reports 166.3 MB, NPD relinquishment reports 24.7 MB, plus 1,500 hand-classified pages ("annotated text categories.xls") for text/gibberish classification; languages EN/NO/NL; PII removed as far as possible - [Zenodo 10775273](https://zenodo.org/doi/10.5281/zenodo.10775273)

### Inferences
- For an app with zero data-access risk, FactPages (wellbores, fields, licences, discoveries, production, lithostratigraphy tops) + DISKOS-QA + the Zenodo corpus are the safest base; they are NLOD/CC BY and scriptable.
- Volve is the only open NCS set with WITSML drilling/real-time and production time series; useful for drilling or production apps, but licence is not fully open.

### Gaps
- Not researched in depth (budget): NOAKA open data, Aurora, CO2 Storage Atlas, biostrat datasets, core photo datasets, released Sodir seismic list. No primary URLs gathered for these.
- Exact DataService query syntax not documented publicly in what I found.

## 4. Previous FORCE hackathons and the 2026 VibeCode hackathon

### Takeaway
VibeCode Hackathon: in person, Stavanger, 19 Nov 09:00 to 20 Nov 15:00 2026 (ice breaker possibly 18 Nov), FORCE + Sodir, "build, recreate, or reimagine applications for geoscientists and engineers" with high-end LLMs and a real NCS dataset; Microsoft sponsors tokens and model access; event is full. The 2023 LLM hackathon at NPD (29 Nov to 1 Dec 2023) used Azure OpenAI (GPT-4, ada-002) on the Fabriq-curated text corpus.

### Cited Findings
- Event page: "In-person: VibeCode Hackathon - FORCE" - [sodir.no event page](https://www.sodir.no/en/force/events/vibecode-hackathon/) (403 to fetch; content via snippets): build, recreate or reimagine apps for geoscientists and engineers "with access to high-end language models and real Norwegian Continental Shelf dataset"; participants get "tokens, high-end language models, wells, seismic and DiskosQA data, plus expert mentors"; programme lists ice breaker 18 Nov, coding 19 Nov, final sprint morning of 20 Nov then presentations and awards in the afternoon (snippets)
- Registration page: public event "open for anyone to enter"; Prof Olav Hanssens vei 10, 4032 Stavanger (Havtil entrance); Thu 19 Nov 2026 09:00 to Fri 20 Nov 2026 15:00; registration deadline Mon 16 Nov 2026 16:00; event currently full; contact FORCE secretariat via form - [force.registrationsystem.com](https://force.registrationsystem.com/vibecode-hackathon). Conflict: a search snippet of the same page earlier gave deadline Thu 12 Nov 2026 14:00 (possibly extended).
- Fees (snippet): FORCE members NOK 2000, non-members NOK 4000, university/students NOK 500 - [sodir.no event page](https://www.sodir.no/en/force/events/vibecode-hackathon/)
- Microsoft sponsors "tokens and access to high-end language models to help teams bring ideas to life"; students and contractors can ask for free attendance (LinkedIn post by a Sodir-linked account, snippet) - [LinkedIn, Torgeir Stordal (Sodir)](https://www.linkedin.com/in/torgeir-stordal-5791a517/)
- 2023 "In-person @ the NPD: Language modelling Hackathon 2023" event page - [Sodir](https://sodir.no/en/force/Previous-events/2023/in-person--the-npd-language-modelling-hackathon-2023); starter pack [github.com/lukasmosser/force_npd_llm_hackathon](https://github.com/lukasmosser/force_npd_llm_hackathon): 29-30 Nov and 1 Dec 2023; corpus curated by Fabriq from NPD, UK NSTA and Dutch NLOG; ~755.8M tokens (scrubbed, cl100k_base); NLOD 2.0 data, MIT code; Azure OpenAI (GPT-4, ada-002 embeddings), CBOW, RAG, embedding fine-tuning; Azure OpenAI key distributed at the event via `.env.secret`
- FORCE annual report 2023 (may contain hackathon outcomes, not read) - [PDF](https://sodir.no/globalassets/2-force/2024/dokumenter/force-annual-report-2023_1.pdf)
- 2018 FORCE ML hackathon project round-up - [Agile Scientific](https://agilescientific.com/blog/2018/9/27/force-ml-hackathon-project-round-up); 2020 lithology competition results - [Sodir](https://sodir.no/en/force/Previous-events/2020/results-of-the-FORCE-2020-lithology-competition); 2021 FORCE AI challenge results - [Oilit](https://oilit.com/HTML_Articles/2021_1_5.php)

### Inferences
- Given 2023 precedent (Azure OpenAI keys handed out) and Microsoft sponsorship, models will very likely be served via Azure OpenAI / Azure AI Foundry (GPT-4.1/GPT-5-class, o-series, embeddings). DISKOS-QA itself was built with gpt-5-mini and o4-mini on Azure, which supports this. Not confirmed.
- "Recreate or reimagine applications" suggests judges value working apps for real geoscience/engineering workflows over pure model benchmarks; DISKOS-QA gives a ready-made, citable accuracy metric for any RAG app, which is likely to impress judges. Speculative.

### Gaps
- No published judging criteria, prizes, team size rules or exact model list found.
- Winners/projects of the 2023 LLM hackathon not found (FORCE annual report 2023 is the best lead).

## 5. Which LLMs/tools are likely available, and judging hints?

### Takeaway
Only "high-end language models" and Microsoft-sponsored "tokens" are confirmed; Azure OpenAI is the strong prior based on 2023 and the DISKOS-QA tooling.

### Cited Findings
- Microsoft sponsors tokens and model access (snippet) - [LinkedIn, Torgeir Stordal](https://www.linkedin.com/in/torgeir-stordal-5791a517/)
- 2023 hackathon used Azure OpenAI GPT-4 and ada-002 - [starter pack](https://github.com/lukasmosser/force_npd_llm_hackathon)
- DISKOS-QA pipeline defaults: Azure OpenAI gpt-5-mini, o4-mini, text-embedding-ada-002 - [DISKOS-QA README](https://github.com/georgeghon/DISKOS-QA)

### Inferences
- Plan apps that work with an OpenAI-compatible endpoint (Azure base URL + key) and keep the model name configurable.

### Gaps
- Exact provider, model catalogue, rate limits and token budget per team not public.
- Judging criteria not public.
