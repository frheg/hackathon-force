# LLMs and agents for geoscience and subsurface documents (state of the art 2023-2026)

Research date: 2026-11-17. Scope: document intelligence over well reports, RAG/QA, knowledge graphs, agents and Text-to-SQL, data management/QC, quantified business value, and vision-language models. Numbers are as reported by the cited source. Many are self-reported or vendor claims, and the notes say so where it matters.

## 1. LLMs and RAG over well reports and geological documents (domain models, extraction, NER, benchmarks)

### Takeaway
Geoscience-specific LLMs (K2, GeoGalactica, GeoGPT) have mostly been overtaken by frontier general models: on the 2026 FormationEval petroleum-geoscience MCQ benchmark, the top frontier models score 97-99.8%. The open problems are no longer domain knowledge but grounded retrieval, extraction from messy/scanned reports, and evaluation. For the NCS specifically there is now a public FORCE benchmark (DISKOS-QA, about 1,027 QA pairs), a public FORCE text corpus (Zenodo), and Sodir's ongoing conversion of Diskos well documents to AI-readable JSON (about 92,000 so far, as of Oct 2026).

### Cited Findings
**Domain foundation models (2023-2025)**
- K2 (June 2023): LLaMA-7B further pre-trained on 5.5B tokens of geoscience text (over 1 million pieces of geoscience literature), then instruction-tuned on "GeoSignal". The authors also introduced GeoBench, which they call the first geoscience LLM benchmark. Data and checkpoints are released on GitHub ([arXiv 2306.05064](https://arxiv.org/pdf/2306.05064)).
- GeoGalactica (Dec 2023/Jan 2024): 30B parameters, further pre-training of Galactica on about 65B geoscience tokens plus 1M instruction pairs ([arXiv 2401.00434](https://arxiv.deeppaper.ai/papers/2401.00434v2)).
- GeoGPT (Zhejiang Lab, Deep-time Digital Earth initiative): released globally on 27 April 2025, free and open. It runs on several base models (Llama3, DeepSeek R1, Mixtral, Qwen2.5, Zhejiang Lab's own model), with a corpus of 288,000 open-access papers from 15 publishers and 182 journals. It reported over 40,000 users in 135 countries by July 2025 ([DDE news](https://www.ddeworld.org/news/detail/297); [Geoscientist](https://geoscientist.online/sections/viewpoint/geogpt-an-update/)). A GeoGPT-RAG technical report is on arXiv ([arXiv 2509.09686](https://arxiv.org/pdf/2509.09686)).

**Benchmarks**
- FormationEval (Ermilov, Jan 2026, v2 Feb 2026): 505 MCQs across 7 domains including petrophysics, petroleum geology and reservoir engineering. 72 models were evaluated. Gemini 3 Pro Preview scored 99.8%, GPT-4o 92.9%, and the best open-weight model (GLM-4.7) 98.6%. Several DeepSeek, Llama, Qwen and Mistral models scored above 93%. Petrophysics was the hardest domain for all models. The dataset has a documented length bias, with correct answers tending to be longer ([arXiv 2601.02158](https://arxiv.org/abs/2601.02158)).
- DISKOS-QA (FORCE consortium with Sodir and operators, 2026, NLOD 2.0): about 1,027 rows in a single split. Each row has a question, an answer, the retrieved context, chunk IDs, well, wellbore, field and formation names, topic, an "evolution" type (reasoning, comparative, hypothetical, multi-context, ...), and an `Entailed` flag. Topics include rock and core, test fluid and pressure, geology, drilling, petrophysics, and VSP. It is machine-generated: chunks were retrieved from a Neo4j KG of Diskos chunks, QA pairs were synthesised with Azure OpenAI, and the pairs were filtered with DeepEval. No baseline scores are published ([HF dataset card](https://huggingface.co/datasets/porestar/diskos_qa)).
- DISKOS-QA repo pipeline defaults: gpt-5-mini for generation, o4-mini as critic, text-embedding-ada-002 for embeddings. The repo has NER utilities (GLiNER/SpaCy), Neo4j Cypher loaders, raw chunk/well/field CSVs, and a Streamlit plus Supabase human-feedback app. The public file is `benchmark/dataset/FORCE_QA_public.csv` ([GitHub georgeghon/DISKOS-QA](https://github.com/georgeghon/DISKOS-QA)).
- WellLogBench (OpenReview) is an expert-curated LLM benchmark for petrophysical reasoning. It serialises well logs into compact text context rather than images. The details could not be fetched because the page had a bot wall ([OpenReview PDF](https://openreview.net/pdf?id=RzMqCe2xVK)).

**FORCE / NCS corpora and NER**
- FORCE Language Modelling Hackathon, Stavanger, 30 Nov - 1 Dec 2023. The aim was to fine-tune language models on open NCS subsurface data. The organisers released a large text dataset from public Diskos, NLOG (NL) and NSTA (UK) documents, together with O&G-specific NER ([Sodir FORCE previous events](https://www.sodir.no/en/force/Previous-events/); [Zenodo 10775273](https://zenodo.org/records/10775273)).
- Zenodo record 10775273 is English, Norwegian and Dutch. Its pages are classified as real text or "mostly gibberish", which signals OCR noise in old scanned reports ([Zenodo](https://zenodo.org/records/10775273)).
- An earlier FORCE hackathon (2018) had a "300 Wells" team that tried to extract hydrocarbon show depths and identification confidence from well reports ([Agile Scientific](https://agilescientific.com/blog/2018/9/24/machine-learning-goes-mainstream)).
- Sodir (26 Oct 2026): about 92,000 Diskos well documents have been converted from PDF to structured JSON. This is phase 1 of "several hundred thousand" PDF/TIFF files, with completion expected in 2027. Phase 1 covers geological information, reservoir properties, drilling events, core analyses, fluid properties and test results. The initiative came from FORCE. Stated goal: "AI, analysis tools and digital assistants", and linking wells, fields, licences, seismic surveys, reports, samples and interpretations. The conversion method and access rules are not stated ([energy-pedia / Sodir](https://www.energy-pedia.com/news/norway/large-volumes-of-data-from-the-norwegian-offshore-directorate-ready-for-ai-205818)).
- 2023 NPD pilot: FabriqAI and Kadme built an AI search/chat tool over more than 600 NCS licence status reports. It answered in Norwegian or English with source references, and the pilot ran until October 2023 ([Offshore Magazine, 30 May 2023](https://www.offshore-mag.com/business-briefs/equipment-engineering/article/14294524/norway-trials-aibased-field-wells-search-engine)).

**Extraction from well reports (incl. scanned)**
- Ma et al. (LANL, arXiv May 2024; Scientific Reports 2024): Llama 2 extracted well location and depth from 160 historical (orphaned) well records. Accuracy was about 100% on clean text-PDF reports and about 70% on image-based or scanned records, so OCR quality is the bottleneck. More detailed prompts improved extraction, and larger models did better ([arXiv 2405.05438](https://arxiv.org/abs/2405.05438); [Sci Rep](https://www.nature.com/articles/s41598-024-81846-5)).
- ESSD preprint (2026): a vision-language model read scanned driller's logs directly with no OCR step. Across 11 scanned-PDF US states, 97.2% of logs yielded at least one lithology interval, with a mean of 7.85 intervals per log. These are water-well records, not petroleum records ([ESSD preprint essd-2026-527](https://essd.copernicus.org/preprints/essd-2026-527/essd-2026-527.pdf)).
- No published benchmark was found for LLM extraction of formation tops, DST results or core descriptions from petroleum well reports. A USPTO patent describes the OCR then LLM pattern for well-report extraction ([USPTO 12608412](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12608412)).

**RAG engineering for O&G documents**
- Taiwo and Yusoff (Mar 2026) evaluated chunking on O&G enterprise documents (manuals, specs, P&IDs). Structure-aware chunking beat semantic and fixed-size chunking on retrieval (top-K) and cost less compute ([arXiv 2603.24556](https://arxiv.org/abs/2603.24556)).
- Energies (MDPI, 2026): LLM-as-a-judge for evaluating O&G RAG knowledge bases ([MDPI Energies 19(17) 4207](https://www.mdpi.com/1996-1073/19/17/4207)).
- Mahjour and Mahjour (Sep 2025) ran a RAG over more than 50,000 petroleum documents with GPT-4o, Claude 4 Sonnet and Gemini 2.5 Pro. They claim 94.2% "reservoir characterization accuracy" and a 62-78% cost reduction. These are self-reported numbers from an abstract with an unclear methodology, so treat them as weak evidence ([arXiv 2509.11376](https://arxiv.org/abs/2509.11376)).
- SPE-227420-MS (MEOS GEO, Sep 2025): a DeepSeek-based assistant over historical drilling documents. Experts rated it highly, but it was tested on simulated reports ([OnePetro](https://onepetro.org/SPEMEOS/proceedings-abstract/25MEOS/25MEOS/790250)). SPE ADIPEC 2025 also has a multi-agent RAG for O&G drilling and completion reports (abstract only; the page was 403) ([OnePetro 25ADIP 792960](https://onepetro.org/SPEADIP/proceedings-abstract/25ADIP/25ADIP/792960)).

### Inferences
- Domain fine-tuning is not worth the 2 days. Frontier models already know petroleum geoscience at above 97% on MCQ. Hackathon value is in grounding: citations to page/report, structured extraction, and cross-checking against Sodir FactPages/DB.
- DISKOS-QA is an evaluation set for the NCS that is ready to use and has no published baselines. "First public baseline on DISKOS-QA: plain RAG vs KG-RAG vs agentic RAG with frontier LLMs" is a novel and feasible 2-day result that would also produce a leaderboard. Caveat: answers are synthetic, so filter on `Entailed=True`.
- The scanned-report gap (about 100% on text PDFs vs about 70% on scans in the LANL study) suggests a VLM-first extraction pipeline for old NCS reports (1970s-90s TIFFs). It can be scored against existing structured truth (FactPages formation tops, DST tables, core intervals). That makes a measurable "extraction accuracy vs ground truth" demo.
- Sodir's JSON conversion means a hackathon team may get pre-structured report content. Check whether hackathon data includes it, because that changes what is worth building (QA/agent on top rather than OCR plumbing).

### Gaps
- No published accuracy numbers for LLM extraction of formation tops, DST results, lithology or core descriptions from petroleum well reports.
- No baseline results on DISKOS-QA. The exact Norwegian/English mix was not verified.
- Results of the FORCE 2023 language hackathon (winning projects, NER model quality) were not found because the Sodir event page returned 403.
- K2/GeoGalactica GeoBench scores were not retrieved. "PetroGPT/OilGPT" and "PetroBench" turned up no credible primary sources.

## 2. Agentic workflows, tool calling, Text-to-SQL, OSDU, knowledge graphs

### Takeaway
Agentic designs that join structured queries (SQL/DuckDB) with semantic search over reports, using domain-specific tools, are the 2025-2026 pattern. TADI on Equinor's public Volve data is a close, reproducible template. Vendors (SLB Tela/Lumi, Cognite Atlas AI at Aker BP) ship agents, but published accuracy for E&P Text-to-SQL is scarce. The best O&G-specific number is 88.5% exact-match on 1,711 queries over an OSDU-style schema (2023, fine-tuned T5).

### Cited Findings
- TADI (Lu, arXiv Apr 2026) uses the Equinor Volve dataset: 1,759 daily drilling reports, WITSML objects, 15,634 production records, formation tops and perforations. DuckDB holds 12 tables (65,447 rows) and ChromaDB holds 36,709 embedded documents. 12 domain tools are orchestrated by LLM function calling. All 1,759 DDR XML files were parsed with zero errors, and 3 incompatible well-naming conventions were reconciled. Evaluation: 95 automated tests, a 130-question stress taxonomy, and a proposed "Evidence Grounding Score". The codebase is 6,084 lines with no framework. Conclusion: tool design matters more than model scale. That conclusion is qualitative, with no quantitative RAG-baseline comparison ([arXiv 2605.00060](https://arxiv.org/abs/2605.00060)).
- SPE ADIPEC 2023, "Enabling Contextual Natural Language Search on Oil and Gas Databases": a fine-tuned T5 for Text-to-SQL over O&G entities (fields, wellbores, well logs, markers) on the OSDU platform. Exact-set-match was 88.5% on 1,711 test queries, and multi-task training helped ([OnePetro](https://onepetro.org/SPEADIP/proceedings-abstract/23ADIP/23ADIP/D021S065R001/534522)).
- General Text-to-SQL context: GPT-4 execution accuracy is 54.89% vs 92.96% for humans on BIRD (12,751 pairs), as cited in a GeoQA multi-agent paper ([arXiv 2503.14251](https://arxiv.org/pdf/2503.14251)). "Empowering Drilling and Optimization with Generative AI" claims the first LLM Text-to-SQL in O&G. No numbers were retrieved ([ResearchGate](https://www.researchgate.net/publication/385520500_Empowering_Drilling_and_Optimization_with_Generative_AI)).
- GeoMind (arXiv Apr 2026): an LLM planner does task decomposition and tool orchestration (perception, reasoning and analysis tools) for lithology classification ([arXiv 2604.21501](https://arxiv.org/html/2604.21501)).
- GGeoLog-Agent (arXiv Nov 2026) uses an LLM's geological priors for well-log reconstruction. Blind-well R² averages 0.9307 ([arXiv 2611.19624](https://arxiv.org/abs/2611.19624)).
- GAIA geothermal/subsurface agent (arXiv Nov 2025): RAG-enabled agent with up to 3.1x improvement on RAGAS metrics over the base model ([arXiv 2511.03852](https://arxiv.org/html/2511.03852)).
- Open-source examples: Petrophysics-Copilot (Gemini routes English requests to deterministic lasio/numpy petrophysics functions) ([GitHub](https://github.com/Ovar9000/Petrophysics-Copilot)), and legacy-well-rag (LLM tools for LAS curve stats and plots) ([GitHub](https://github.com/SAnderwald/legacy-well-rag)).
- SLB Tela, launched 3 Nov 2025, is an "agentic AI assistant purpose-built" for upstream. No time-saving figure is published ([SLB press release](https://www.slb.com/news-and-insights/newsroom/press-release/2025/pr-2025-1103-slb-tela-ai)). The SLB Lumi data and AI platform (Sep 2024) is built on OSDU, embeds frontier LLMs plus SLB domain foundation models, and uses Cognite Data Fusion ([SLB IR](https://investorcenter.slb.com/news-releases/news-release-details/slb-launches-ai-powered-lumi-platform)).
- Aker BP and Cognite Atlas AI (Sep 2025): pre-built and low-code industrial agents. Agents cut the time engineers spend on root-cause analysis by more than 70%. Other uses are document processing and barrier management, which are operations rather than subsurface ([World Oil](https://worldoil.com/news/2025/9/16/aker-bp-expands-ai-first-strategy-with-cognite-to-transform-e-p-efficiency/)). Aker BP keeps subsurface data in Azure Data Manager for Energy (OSDU-based) ([Forrester](https://www.forrester.com/blogs/cognite-lets-customers-demonstrate-the-power-of-industrial-ai/)).
- bp's "Xpert" chatbot reportedly lets engineers query production data in natural language. This is from an aggregator with weak sourcing ([Klover.ai](https://www.klover.ai/bp-ai-strategy-analysis-of-dominance-in-energy-ai/)).
- Knowledge graphs: dual-layer (process and knowledge) GraphRAG for reservoir-engineering decision support ([Processes 13(10):3230, 2025](https://doi.org/10.3390/pr13103230)). KG and LLM for O&G HSE Q&A with an ontology in Neo4j ([Lacuna summary](https://lacuna.tiptreesystems.com/work/knowledge-graph-construction-of-large-language-model-retrieval-augmented/wrk_401656646bbbe8a96f24c7582999710b)). The DISKOS-QA pipeline itself is built on a Neo4j KG of Diskos chunks linked to wells, fields and formations ([GitHub](https://github.com/georgeghon/DISKOS-QA)).

### Inferences
- The TADI pattern (DuckDB for structured tables, a vector store for report text, and about 10 typed tools such as `get_formation_tops(well)`, `get_dst(well)`, `search_reports(query, well)` and `compute_vsh(las)`) fits 2 days well with NCS data. Sodir FactPages/API give well headers, tops, DSTs, cores and licences as the structured side, and DISKOS-QA plus the FORCE corpus give the text side.
- Text-to-SQL over the FactPages schema is feasible and measurable: write 50-100 gold queries and report execution accuracy. Typed tools (fixed queries) are more reliable than free SQL for a live demo. A hybrid "tools first, SQL fallback" design is the safe choice.
- An agent that answers "show me wells near X with gas shows in Brent Group and a DST" by combining FactPages, report text and LAS would show cross-source reasoning, which vendors claim but rarely quantify.

### Gaps
- No published accuracy for Text-to-SQL on OSDU/Diskos/FactPages with frontier LLMs (2025-2026).
- No public details or metrics for Equinor's internal subsurface copilots, or for bp Xpert accuracy.
- No peer-reviewed multi-agent subsurface assistant with a quantitative comparison against human geoscientists.

## 3. Data management: cost of finding data, ML-based QC, legacy digitisation

### Takeaway
The often-cited "50-80% of geoscientist time spent finding data" claim is old and second-hand (tracing to a 2008 IBM presentation). Recent surveys put data-management time at about 20-30%+ of working time. ML for log QC, depth matching and raster-log digitisation is established (SPE/SPWLA 2018-2023) but still imperfect, which leaves room for LLM/VLM-assisted QC and cross-source consistency checks.

### Cited Findings
- GeoExPro: geoscientists and engineers reportedly spend more than 50% of their time searching for and assembling data, with some reports saying up to 80% ([GeoExPro, "The importance of structured data"](https://geoexpro.com/the-importance-of-structured-data/)).
- Seequent 2011 survey: "data searchers" spend 15-35% of their time searching, and find what they seek 50% of the time or less. The often-quoted "almost 70% of time" figure traces to a 2008 IBM presentation, which the authors call hard to analyse ([Seequent 2011](https://files.seequent.com/PDFs/exploration_information_management_survey_2011.pdf)).
- Seequent Geoprofessionals Data Management Report, 7th edition (2026): 75% of geoprofessionals spend over 25% of their time on data management. The share is 20% or more in every industry and highest in mining ([Seequent 2026](https://files.seequent.com/PDFs/TheGeoprofessionalsDataManagementReport_7edition.pdf)). In the 2021 edition, 35% of respondents spent over 30% of their time on data management ([Seequent 2021](https://files.seequent.com/PDFs/Seequent-Geoscience-Data-Management-Report-2021.pdf)).
- Ovation Data published a G&G legacy data survey in May 2026. Its text was not extractable here because it is image-based ([Ovation PDF](https://www.ovationdata.com/wp-content/uploads/2026/05/geological-geophysical-legacy-data-survey-report-may-2026.pdf)).
- SPE-202977-MS (SLB/ADNOC, 2020): ML log QC, bad-data flagging, depth-offset correction and log reconstruction, trained on 50 vertical wells in a carbonate field ([SLB](https://www.slb.com/resource-library/technical-paper/di/spe-202977-ms)).
- Akkurt et al. (SPWLA 2018): an automated ML workflow for log outlier detection and reconstruction ([cited in USPTO 11965399](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11965399)). The SLB/Dataiku isolation-forest log outlier workflow works with Techlog ([Dataiku](https://dataiku.com/solutions/catalog/isolation-forest-well-log-outlier-detection-with-slb)).
- NTNU/SPWLA Petrophysics papers (2021-2022): deep-learning depth-shift inference with an automatic QC stage ([NTNU](https://ntnuopen.ntnu.no/ntnu-xmlui/bitstream/11250/2988262/2/SPWLA_D_21_00021_Petrophysics_Manuscript_Rev2_minors_edit.pdf)), and multi-log depth matching by dynamic programming ([NTNU](https://ntnuopen.ntnu.no/ntnu-xmlui/bitstream/11250/2988259/1/SPWLA_D_21_00006_Manuscript_Rev2_highlighted_editions.pdf)).
- VeerNet (J. Imaging, Jul 2023) does raster well-log digitisation with an attention UNet. Curve segmentation reached 97% recall but only 35% F1 and 30% IoU, and the GR prediction had Pearson r = 0.62 vs measured. Commercial Neuralog-style tracing often stalls on the grid ([PMC10381386](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10381386/)).
- Diskos legacy context: Sodir's JSON conversion targets "several hundred thousand" PDF/TIFF files by 2027 ([energy-pedia](https://www.energy-pedia.com/news/norway/large-volumes-of-data-from-the-norwegian-offshore-directorate-ready-for-ai-205818)).

### Inferences
- A credible pitch number is "20-30%+ of geoprofessional time goes to data management (Seequent 2021/2026)". Cite "50-80%" only as an older industry claim.
- An "LLM data-QC auditor" is a strong 2-day idea that is easy to score. It would cross-check report-extracted values (TD, KB elevation, spud date, formation tops, DST intervals, coordinates) against FactPages and LAS headers, and flag mismatches with citations. Precision can be measured on a hand-labelled sample. It is novel because published ML QC is signal-level (logs), not cross-document consistency.
- Raster-log digitisation is too hard to beat in 2 days given VeerNet's weak F1. A VLM reading header blocks and tabular pages of scanned reports is more realistic.

### Gaps
- No rigorous 2023-2026 time-and-motion study specific to NCS geoscientists' data search time.
- No published LLM-based well-header or coordinate QC evaluation was found.
- Ovation 2026 survey numbers could not be extracted.

## 4. Quantified business value (operators, vendors, consultancies)

### Takeaway
The headline numbers cover AI broadly, not GenAI on documents. McKinsey estimates about $65B per year of near-term upstream AI value and up to $230B at full potential. Equinor reports $130M of AI value in 2025 and over $330M since 2020, mostly from classic ML, including 10x faster seismic interpretation. Hard numbers for GenAI document assistants in subsurface are almost absent from public sources, so a hackathon that measures time saved would itself be a contribution.

### Cited Findings
- McKinsey (2025): AI can unlock about $65B per year of recurring upstream value near term with today's technology, and about $230B at full potential. The figure is net of more than $30B per year of implementation costs and is built from more than 550 use cases. The top 10 use cases hold about half the value, and the top 60 about 95%. Exploration improvements could add more than $35B per year of balance-sheet value via reserves. At about 40% margins, the cash-flow impact is about $7B (near term) and $24B (full). GenAI and agentic AI are listed among the technologies for subsurface interpretation, model updating and reserves, but they are not separately quantified ([McKinsey](https://www.mckinsey.com/industries/oil-and-gas/our-insights/can-upstream-oil-and-gas-produce-value-from-ais-230-billion-dollar-pay-zone); [OGJ](https://www.ogj.com/general-interest/news/55400981/analysis-ai-could-unlock-230-billion-in-annual-upstream-oil-and-gas-value)).
- Rystad Energy estimates $500B of cumulative digital and AI value for E&P by 2030, with subsurface workflows having the biggest upside. The methodology differs from McKinsey's, so the two are not comparable ([Rystad](https://www.rystadenergy.com/insights/digital-and-ai-in-upstream-whitepaper)).
- Equinor (JPT, 7 Jan 2026): $130M of AI value in 2025 and more than $330M since 2020. Predictive maintenance covers more than 700 machines and 24,000 sensors, worth about $120M since 2020. AI well and field planning found a $12M saving on Johan Sverdrup Phase 3. Seismic is analysed "10 times faster", and 2 million km² of NCS was AI-interpreted in 2025. More than 100 new AI use cases have been identified. Copilots, chatbots and agents are used, but no time-saved figures are given for them ([JPT](https://jpt.spe.org/equinor-says-ai-saved-it-130m-in-2025)).
- Aker BP and Cognite agents cut root-cause analysis time by more than 70% ([World Oil, Sep 2025](https://worldoil.com/news/2025/9/16/aker-bp-expands-ai-first-strategy-with-cognite-to-transform-e-p-efficiency/)).
- SLB's own figures: an 80% reduction in time-to-insight for waterflood optimisation (SPE-215944) and up to 6x faster property modelling (SPE-211398). Results vary by workflow, and these are not GenAI-document specific ([SLB AI solutions](https://slb.com/solutions/data-and-ai-platform/artificial-intelligence-solutions)). Petrobras/Delfi (2023): AI/ML cut fault interpretation time by 60% ([AIwire](https://aiwire.net/2023/07/06/slb-secures-petrobras-contract-for-ai-enhanced-delfi-digital-platform-deployment)).
- Petrobras' "ChatPetrobras" runs on Azure OpenAI and is available to 110,000 employees and contractors. It is a general assistant, not a subsurface tool. The source is an aggregator ([Klover.ai](https://www.klover.ai/petrobras-ai-strategy-analysis-of-dominance-in-energy-ai/)).
- Shell and SparkCognition (2023): generative AI for subsurface imaging and exploration speed. This is a press-release claim with no published numbers ([Rigzone](https://www.rigzone.com/news/will_oil_gas_companies_ramp_up_their_use_of_generative_ai_in_2024-05-dec-2023-174946-article)).
- The 2025 Mahjour paper claims a 62-78% cost reduction and an 8-month payback for an LLM and RAG reservoir decision-support system. The claim is self-reported, and the evidence is weak ([arXiv 2509.11376](https://arxiv.org/abs/2509.11376)).
- Sodir says AI-ready Diskos data "can save the industry time and money", but the saving is not quantified ([energy-pedia](https://www.energy-pedia.com/news/norway/large-volumes-of-data-from-the-norwegian-offshore-directorate-ready-for-ai-205818)).

### Inferences
- For a hackathon pitch, the strongest defensible framing combines three points: (a) Seequent's survey figure that 75% of geoprofessionals spend over 25% of their time on data management; (b) Equinor's public $130M/year from AI, which shows NCS operators will pay for AI; and (c) a measured result from the demo, for example "compiling a well summary (tops, DSTs, shows, cores) took a geoscientist N minutes manually vs M seconds with the agent, at X% field accuracy vs FactPages".
- Avoid quoting McKinsey's $230B as GenAI value. It covers all AI.

### Gaps
- No public hours-saved-per-well or per-study figure for an LLM well-report assistant at any operator (Equinor, Aker BP, Shell, ExxonMobil, Petrobras, bp).
- No McKinsey/BCG/Deloitte figure isolating GenAI's share of upstream subsurface value was found in this pass. McKinsey's main page timed out on a direct fetch, so the numbers come from the search snippet and the OGJ summary.
- ExxonMobil: no public GenAI subsurface copilot found.

## 5. Vision-language models on logs, core photos, seismic and scanned reports

### Takeaway
There is little rigorous evaluation of GPT-4V/4o/Claude/Gemini on well-log plots, core photos or seismic sections. General geospatial VLM benchmarks show that VLMs describe images well but are weak at precise spatial or quantitative reading. The most practical VLM win is reading scanned report pages (tables, header blocks, lithology descriptions) rather than digitising curves.

### Cited Findings
- A 2026 ESSD preprint shows that a VLM reading scanned driller's logs directly (no OCR) extracted at least one lithology interval from 97.2% of logs, with a mean of 7.85 intervals per log, across 11 states ([ESSD](https://essd.copernicus.org/preprints/essd-2026-527/essd-2026-527.pdf)).
- LANL/Ma et al. 2024: text-LLM accuracy fell from about 100% to about 70% on image-based well records. This motivates going VLM-first on scans ([arXiv 2405.05438](https://arxiv.org/abs/2405.05438)).
- GPT-4V geography evaluation: it extracts fine-grained detail but is weak at localisation and bounding boxes ([arXiv 2311.14656](https://arxiv.org/html/2311.14656v3)). Performance varies by domain and image complexity ([arXiv 2312.17016](https://arxiv.org/abs/2312.17016)). GEOBench-VLM benchmarks geospatial VLM tasks ([arXiv 2411.19325](https://arxiv.org/pdf/2411.19325)).
- WellLogBench serialises logs to text for LLMs rather than using plot images ([OpenReview](https://openreview.net/pdf?id=RzMqCe2xVK)). WLFM is a well-log foundation model (non-LLM) for multi-task, cross-well interpretation ([arXiv 2509.18152](https://arxiv.org/pdf/2509.18152)).
- Core imagery: a CVPR 2026 workshop paper generates core images conditioned on FMS images and logs (generative, not interpretive) ([CVPRW 2026](https://openaccess.thecvf.com/content/CVPR2026W/AI4RWC/papers/Shi_Log-Gated_Dual-Path_Conditioning_Framework_for_Multimodal_Geological_Core_Image_Generation_CVPRW_2026_paper.pdf)).
- Raster-log curve digitisation remains hard: VeerNet reached 35% F1 ([PMC10381386](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10381386/)).

### Inferences
- A VLM on scanned report pages is feasible and demonstrable in 2 days. One example would extract the DST summary table, the formation-tops table and the core description pages from scanned NCS final well reports into JSON, then score against FactPages. A second would use the VLM as a "second reader" of composite-log images, checking that annotated tops and lithology agree with numeric LAS data. That is a useful QC framing that avoids precise curve digitisation.
- Seismic images with a VLM (for example "describe faults and horizons in this inline") would make a flashy demo but cannot be validated in 2 days. If shown, keep it as a qualitative side feature.
- Petrophysics was the hardest FormationEval domain, and WellLogBench chose text serialisation. Both point to petrophysical calculations belonging in deterministic tools (lasio/numpy), with the LLM only orchestrating and explaining.

### Gaps
- No peer-reviewed study was found that evaluates GPT-4o/Claude/Gemini on interpreting well-log plot images, core photos or seismic sections with quantitative accuracy.
- WellLogBench details (size, scores) could not be retrieved because of a bot wall.

## Cross-cutting: candidate hackathon ideas ranked by 2-day feasibility (inference, based on the findings above)

1. **DISKOS-QA baseline and leaderboard (high feasibility, high novelty).** Compare plain RAG, KG/metadata-filtered RAG (wells, fields, formations) and an agentic RAG with frontier LLMs on the about 1,027 public QA pairs, scoring correctness, faithfulness and citation precision. There are no published baselines yet ([HF](https://huggingface.co/datasets/porestar/diskos_qa)).
2. **NCS Well Dossier agent (high feasibility).** Follow TADI's design ([arXiv 2605.00060](https://arxiv.org/abs/2605.00060)): DuckDB with Sodir FactPages, a vector store over the FORCE corpus or Diskos JSON, and LAS tools. The agent outputs a cited one-page well summary. Time the manual vs agent path to produce an hours-saved number.
3. **Cross-source QC auditor (high feasibility, measurable).** The LLM extracts key facts from reports and diffs them against FactPages and LAS headers to flag inconsistencies (tops, TD, coordinates, DST intervals). Report precision on a labelled sample.
4. **VLM extraction from scanned legacy reports (medium feasibility).** Target DST, tops and core-description tables, scored against FactPages, to show the scan-vs-text accuracy gap and whether a VLM closes it.
5. **Text-to-SQL or typed-tool NL query over FactPages (high feasibility).** Use a gold set of 50-100 questions and report execution accuracy. The 88.5% EM from 2023 with fine-tuned T5 is a reference point ([OnePetro](https://onepetro.org/SPEADIP/proceedings-abstract/23ADIP/23ADIP/D021S065R001/534522)).
6. **Seismic or core-photo VLM interpretation (low validation feasibility).** Use only as a qualitative add-on.
