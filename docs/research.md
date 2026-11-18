# Research notes (2026-11-17)

## The event

- FORCE VibeCode Hackathon, run by FORCE and the Norwegian Offshore Directorate (Sodir).
- Thursday 19 November 09:00 to Friday 20 November 15:00, 2026. Prof. Olav Hanssens vei 10, Stavanger (Sodir at
  Ullanhaug, Havtil entrance). One source lists an icebreaker on the evening of 18 November.
- In person, open to anyone; full, registration closed 16 November.
- Theme: build, recreate or reimagine oil and gas apps for geoscientists and engineers in two days.
- Provided: tokens and high-end language models (Microsoft sponsors tokens and model access, per a LinkedIn repost,
  not on FORCE's pages), NCS data (wells, seismic, DiskosQA), expert mentors.
- Not published: team size, judging, prizes, rules on preparing in advance, the exact data format. Ask at kickoff.

Sources: https://www.sodir.no/en/force/events/vibecode-hackathon/ (refuses automated fetches),
https://force.registrationsystem.com/vibecode-hackathon

## Open data

- Sodir FactPages: every public table as CSV, Excel or XML. The CSV export used by `app/fetch_data.py`:
  `https://factpages.sodir.no/public?/Factpages/external/tableview/<table>&rs:Format=CSV&...` (tables such as field,
  field_production_monthly, field_reserves, field_description, wellbore_exploration_all, wellbore_development_all,
  discovery, licence, company).
- Sodir's newer REST data service: `https://factmaps.sodir.no/api/rest/services/DataService/data` (metadata at
  `.../metadata`). It answered "Invalid URL" to plain requests here; the CSV export works. Sodir resets connections
  that send curl's default user agent: send your own.
- FORCE 2020 lithology competition: 118 wells, CC BY 4.0. GitHub (train.zip, hidden_test.csv with labels,
  penalty_matrix.npy, starter notebook) and Zenodo record 4351156 (all LAS files, 170 MB, NPD lithostratigraphy).
- Geographic layers: Esri REST, WMS, WFS from factmaps (ED50 UTM32 and WGS84).

## Earlier projects

- FORCE 2020 lithology competition: 329 teams signed up, 148 submitted; won by Olawale Ibrahim (student, Lagos).
  Top entries were gradient-boosted trees with feature engineering; split by well when validating.
  https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition
- FORCE ML hackathons 2018 and 2019 (215 people in 2019): Agile Scientific's round-ups list nine projects in 2018,
  seven of them new open-source tools. Example: force-hack-2019 (bfotland), formation descriptions to grain size with
  ML. https://agilescientific.com/blog/2018/9/27/force-ml-hackathon-project-round-up
- FORCE language modelling hackathon 2023 at the NPD: a large text set from public oil and gas documents (Diskos,
  NLOG, NSTA) with oil and gas named-entity recognition.
- Text-to-SQL in the industry: SLB on drilling data (https://ai.slb.com/blog/drilling-genai-optimization), bpx
  energy's Xpert on Amazon Bedrock and Snowflake, Cognite's assistant for WellView data, a University of Calgary chat
  assistant over well logs (GeoConvention 2025).
- Decline curves: no NCS-specific open project found; generic libraries exist (decline-curve on PyPI). Sodir's own
  FORCE 2023 work on debiasing production forecasts is relevant background.

## Ideas worth taking to the event

- The copilot pattern (model writes SQL, server runs it read-only, model explains) works on any table the organisers
  hand out; swap in their schema and notes.
- Log Lens shows ML and the language model side by side: numbers from a model, words from the LLM, and the
  disagreements made visible.
- DiskosQA was mentioned: likely questions and answers over Diskos documents, a retrieval (RAG) task; Qdrant and an
  embedding model are ready for it.
