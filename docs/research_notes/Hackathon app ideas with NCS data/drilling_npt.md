# Drilling cost problems and AI solutions: NPT, invisible lost time, offset-well analysis, drilling optimisation (NCS focus)

Research date: 2026-11-17. Format note: each finding ends with its source link. Vendor claims are tagged [VENDOR]; peer-reviewed or conference papers [PAPER]; regulator or official statistics [OFFICIAL]; trade press or secondary [PRESS]. My own arithmetic is marked "(my calc)".

## 1. Cost numbers: rig day rates, well costs, NPT share, NPT causes, cost per NPT event, Sodir statistics

### Takeaway
A harsh-environment semi-sub on the NCS costs about USD 395,000 to 420,000 per day in rig rate alone (2024 to 2026). NPT is commonly cited at 15 to 30% of rig time, and stuck pipe at about 25% of NPT. So every NCS rig-day lost burns roughly USD 0.4M in rig rate, and more once spread costs are added. I found no official current Sodir figure for cost per well. NCS-specific NPT percentages are not published in open sources.

### Cited Findings

Rig day rates (NCS, 2024 to 2026)
- Equinor exercised a Q2 2025 extension of Transocean Spitsbergen for NCS work at USD 395,000/day [PRESS]. [JPT, offshore fleet and day rates](https://jpt.spe.org/global-offshore-drilling-fleet-shrinks-day-rate-pressure-remains)
- Mid-2026: Transocean signed a seven-year deal worth about USD 1 billion with Equinor for three Cat D harsh-environment semi-subs on the NCS. The base day rate is USD 399,000, with adjustment provisions that lift the effective rate above USD 400,000 at commencement [PRESS]. [World Oil, 2026-06-30](https://worldoil.com/news/2026/6/30/transocean-lands-seven-year-1-billion-equinor-rig-deal/); [Offshore Magazine](https://www.offshore-mag.com/regional-reports/north-sea-europe/news/55388687/equinor-secures-three-transocean-rigs-for-long-term-service-offshore-norway)
- Odfjell Deepsea Nordkapp's extension with Aker BP from 2025-01-01 has a 2025 contract value of USD 124 to 146 million under a floor/ceiling rate. That is about USD 340,000 to 400,000/day over a full year (my calc) [PRESS]. [Offshore Energy](https://offshore-energy.biz/?p=696889)
- An aggregated industry table (repost, original likely Clarksons or Esgian) gives the average Norway harsh-environment semi-sub day rate as USD 418,000 in H1 2024 and USD 406,670 in H1 2025, down 3% YoY. It expects rates flat to slightly down through 2026, then a recovery in early 2027. The repost site is low-quality, so verify against the original. [Westwood Insight via Hellenic Shipping News](https://www.hellenicshippingnews.com/?p=1058476)
- Jack-up NCS day rates for 2024 to 2026: no reliable figure found (see Gaps).

Exploration and development well costs, Sodir activity statistics
- 2024: 42 exploration wells were completed on the NCS (28 wildcats, 14 appraisals). Exploration costs were NOK 32.54 billion [OFFICIAL]. [Sodir, The Shelf in 2024](https://www.sodir.no/en/whats-new/publications/reports/the-shelf/the-shelf-in-2024/?print=2). That gives roughly NOK 775 million per exploration well if all exploration spend is divided by wells (my calc). This includes seismic, G&G and studies, not only drilling.
- 2025: 40 exploration wells were completed with 21 discoveries, about 67 million Sm3 o.e. preliminary. Sodir called it the best exploration year in ten years apart from 2021 [OFFICIAL]. [Sodir, Best exploration year in several years (2026)](https://www.sodir.no/en/whats-new/news/general-news/2026/best-exploration-year-in-several-years/); [Sodir Resource Report 2026, exploration](https://www.sodir.no/en/whats-new/publications/reports/resource-report/resource-report-2026/exploration/)
- 2026 outlook: 18% fewer exploration wells expected [PRESS]. [Baird Maritime](https://www.bairdmaritime.com/offshore/exploration-development/oil-companies-in-norway-to-drill-18-per-cent-fewer-exploration-wells-in-2026). Total NCS investments of NOK 256 billion are expected in 2026, down 6.5% [OFFICIAL]. [Sodir, The Shelf in 2025](https://www.sodir.no/en/whats-new/publications/reports/the-shelf/the-shelf-in-2025/)
- Sodir says "higher drilling costs per development well" is one driver of higher investment levels (2024 and 2026 outlooks) [OFFICIAL]. [Sodir, The Shelf in 2024](https://www.sodir.no/en/whats-new/publications/reports/the-shelf/the-shelf-in-2024/?print=2)
- Historical: average well investment per development well fell by more than 40% from 2014 to 2018 [OFFICIAL]. [Offshore Energy summarising NPD](https://www.offshore-energy.biz/norway-oil-field-development-costs-almost-cut-by-half)
- About NOK 660 billion was spent on exploration on the NCS from 2004 to 2023, and the discoveries are valued at about three times the cost [OFFICIAL]. [Sodir, exploration profitable in all ocean areas (2024)](https://www.sodir.no/en/whats-new/news/general-news/2024/exploration-activity-has-been-profitable-in-all-ocean-areas)
- Westwood: in one decade, 279 NCS exploration well programmes cost an estimated USD 10.0 billion in drilling. That is about USD 36 million per programme (my calc) [PRESS/analyst]. [Westwood, Norway state of exploration](https://www.westwoodenergy.com/reports/product-reports/norway-state-of-exploration)
- Sodir's 2018 Resource Report charted average drilling cost per exploration well by area (2008 to 2017): North Sea lowest, Barents Sea highest [OFFICIAL]. [Sodir Resource Report 2018, ch. 4](https://sodir.no/en/whats-new/publications/reports/resource-report/resource-report-2018/chapter-4)
- P&A cost range on the NCS runs from about NOK 50 million for the simplest plugging operations to more than NOK 1 billion for complex ones [OFFICIAL]. [Sodir, new technology profitable when shutting down wells (2025)](https://www.sodir.no/en/whats-new/news/general-news/2025/new-technology-is-profitable-when-shutting-down-wells/)

NPT share and causes (mostly global, older data)
- Stuck pipe is commonly cited at about 25% of all drilling NPT, and up to 25% of total well budget on deep wells. This comes from industry task-force data reported by Oil & Gas Journal (old) [PAPER/secondary]. [Springer, J Petrol Explor Prod Technol (2020)](https://link.springer.com/article/10.1007/s13202-020-01059-0)
- Gulf of Mexico: "trouble time" from hole problems consumed 24 to 27% of operators' drilling budgets from 1993 to 2002, and the share stayed roughly constant [PRESS, old]. [Offshore Magazine](https://www.offshore-mag.com/drilling-completion/article/16756938/gulf-of-mexico-trouble-time-creates-major-drilling-expenses)
- Industry stuck-pipe cost exceeds USD 250 million/year, and historically BP's alone exceeded USD 30 million/year. A BP task force put stuck-pipe incidents in 1985 to 1988 at about USD 170,000 per well on average, or 3 to 5% of drilling cost [PAPER, old data]. [Springer (2020)](https://link.springer.com/article/10.1007/s13202-020-01059-0)
- NPT "can account for more than 30% of the cost of a drilling operation" [VENDOR glossary]. [GA Drilling](https://www.gadrilling.com/glossary/non-productive-time-npt)
- NPT can reach up to 25% of total rig time [VENDOR, citing industry]. [Provectus case study (2026)](https://provectus.com/case-studies/oil-gas-upstream-drilling-npt-genai)
- NCS well control (one key NPT cause): 15 NCS well control incidents "last year" (2025) caused 35 days of NPT [PRESS citing Havtil]. [JPT, 2026-07-08](https://jpt.spe.org/study-highlights-link-between-pore-pressure-uncertainty-and-well-control-incidents). At about USD 400k/day rig rate, 35 days is about USD 14M in rig rate alone, before spread cost (my calc).
- RNNP 2024: 14 well control incidents in 2024, all in the lowest risk category. Havtil gives a 2015 to 2024 average of about 13.9 per year and "no significant reduction in the number of well control incidents on the NCS over the last decade" [OFFICIAL]. [Havtil RNNP 2024 press release](https://www.havtil.no/en/explore-technical-subjects2/rnnp/rnnp-2024/rnnp-2024-pressemelding); [Havtil, well control incidents and main focus](https://www.havtil.no/contentassets/82ebc4b482a4432a9c17e1d9f13566a2/well-control-incidents-and-main-focus-havtil.pdf)

Invisible lost time (ILT)
- ILT definition: actual operation duration minus a best-practice or technical-limit target, counted only when actual exceeds target. It is hidden inside "productive" time in DDRs [VENDOR]. [Halliburton, 2022-03-09](https://www.halliburton.com/en/resources/investigating-invisible-lost-time-on-textual-data-using-artificial-intelligence); [drillingmetrics.com](https://drillingmetrics.com/resources/detecting-invisible-lost-time-from-drilling-activity-data/)
- A Woodside North West Shelf paper notes ILT hides inside productive time in daily reports and can only be found by benchmark gap analysis [PAPER, via index]. [scite author page](https://scite.ai/authors/p-w-scott-LDbnQ)
- Bakken (onshore, 2017): contractor-controlled processes made up 15 to 25% of total well time, and 30 to 40% fell under "other processes" with little contractor control [PRESS]. [Drilling Contractor](https://drillingcontractor.org/deconstructing-invisible-lost-time-kpis-analytics-standardization-improve-well-deliveries-in-bakken-44170)
- ILT benchmarks often use percentiles rather than a composite best (offshore Abu Dhabi) [PAPER]. [SPE 188238 via SLB](https://slb.com/resource-library/technical-paper/so/spe-188238)

### Inferences
- Order-of-magnitude NCS prize: about 40 exploration wells plus some 150 to 200 development wells per year (development count not verified, see Gaps). At USD 0.4M+/day rig rate, and NCS spread cost often 1.5 to 2x rig rate (unverified rule of thumb), 1 rig-day saved per well is worth tens of millions USD per year NCS-wide. This supports "million-dollar" framing even for small time savings.
- A defensible hackathon pitch number: "1 day of NPT on an NCS semi-sub is about USD 400k in rig rate alone (Transocean/Equinor 2026 contract: USD 399k base)". This is sourced and current.
- Most quoted NPT percentages (15 to 30%, stuck pipe 25%) are old or global. They are fine as context but should not be presented as NCS facts.

### Gaps
- No open, current (2024 to 2026) NCS jack-up day rate found. Jack-ups on the NCS are mainly harsh-environment CJ70-class units at Aker BP and ConocoPhillips. Rates would need Clarksons, Esgian or Westwood data, or Borr/Shelf/Noble fleet status reports.
- No official Sodir figure for average drilling cost per exploration or development well in 2020 to 2026. The 2018 Resource Report chart exists, but numbers were not extracted.
- Number of development wells drilled per year on the NCS was not retrieved. Sodir FactPages/DataService can give it by counting wellbores by entry year and purpose.
- No published NCS-wide NPT percentage or NPT-by-cause breakdown found. Operators hold this internally. Rystad and Offshore Norge public material was not found.
- No current per-event cost for stuck pipe or lost circulation on the NCS.
- The Havtil RNNP 2022 study "Causal factors and measures for well control incidents" (40 pp., Norwegian) was downloaded, but text could not be extracted here (no PDF tools on host). [Havtil PDF](https://www.havtil.no/contentassets/68844acc35b342339e812ee13bdfa5ee/causal-factors-and-measures-relating-to-well-control-incidents-on-ncs.pdf)

## 2. AI/ML solutions (2020 to 2026): DDR NLP, NPT classification, lessons learned, offset-well analysis, stuck pipe, planning assistants, industry products, quantified results

### Takeaway
Classifying NPT from DDR free text is a well-trodden, proven pattern. It has moved from deep-NLP sentence classifiers (2017) to fine-tuned 7B LLMs (SLB) and RAG chatbots over 200+ wells (SPE 2024). Reported accuracy is 90 to 96%. Dollar results are almost all vendor claims, such as a USD 4.2M saving over a 100-well campaign and AI-found hidden NPT of 7% of reported NPT. The best-documented NCS money figure is Equinor's USD 12M Johan Sverdrup phase 3 well-planning saving within its USD 130M AI value in 2025. Lessons-learned retrieval and offset-well hazard summarisation from text is less mature in the literature. That makes it the open gap for an LLM app.

### Cited Findings

Academic and conference papers on DDR text mining
- arXiv 1712.01476 (2017), "Sequence Mining and Pattern Analysis in Drilling Reports with Deep NLP" [PAPER, preprint]. It uses 9,670 daily reports from 303 wells and classifies sentences as EVENT, SYMPTOM or ACTION, reporting state-of-the-art accuracy. Its framing: an operation is non-productive when actions are taken to solve an issue. [arXiv](https://arxiv.org/pdf/1712.01476)
- Fuzzy string matching on DDRs to find invisible lost time (APPEA Journal, CSIRO, Oliveira et al.) [PAPER]. It flagged 92 of 208 "normal" observations, together 923 hours of potential non-productive time hidden in reports logged as normal. [CSIRO Publishing AJ21118](https://www.publish.csiro.au/AJ/fulltext/AJ21118)
- IADC/SPE 217700 (2024), Intellicess and Apache. A GPT LLM with RAG over data from more than 200 wells, with source visibility and the ability to decline when it lacks an answer [PAPER, via press]. [Drilling Contractor, Jul/Aug 2024](https://drillingcontractor.org/ai-enabled-large-language-model-speeds-up-wells-data-retrieval-but-must-be-used-with-care-69503)
- SPE 220798 (ATCE 2024), "Next-gen LLM-AI for real-time support in well construction control rooms". It classifies log records and WITSML data and claims a more than 50x gain in decision-making efficiency, with search time cut "from hours to minutes" (authors' claim) [PAPER]. [OUCI index](https://ouci.dntb.gov.ua/works/4KQP5G39)
- SPE 217671 (2024): zero-shot LLM drilling information retrieval, a roadmap for a drilling chatbot adviser [PAPER]. Found via the search summary only, not verified in full text.
- EAGE 2026 paper: a multi-agent LLM workflow over daily reports extracting highlights, lowlights and lessons learned, with a fact-checking module grounding outputs in the original logs. This is the closest published match to "lessons learned retrieval" [PAPER]. [EarthDoc 10.3997/2214-4609.2026101276](https://www.earthdoc.org/content/papers/10.3997/2214-4609.2026101276)
- Patents: US 11466554 (NLP plus ML to identify NPT, NPT type and drilling phase from DDR text; notes human NPT coding is biased or inaccurate) and US 12129755 (information extraction from DDRs with ML). [US11466554](https://patents.google.com/patent/US11466554); [US12129755](https://patents.google.com/patent/US12129755)

Vendor and industry products with numbers
- SLB, GenAI drilling-risk extraction from DDRs [VENDOR]. Fine-tuned on-prem Mistral 7B beat Llama2 13B for drilling event and hidden-NPT classification, with nearly 96% accuracy on an imbalanced dataset. The original blog URL now redirects. [SLB blog (redirects)](https://ai.slb.com/blog/extract-drill-risk-genai); [SLB AI solutions](https://www.slb.com/products-and-services/delivering-digital-at-scale/artificial-intelligence-solutions)
- Provectus case study (published 2026-05-04, US shale operator) [VENDOR]. A domain-tuned LLM classifies NPT from free-text DDRs into 13 risk categories: stuck pipe, losses, equipment failure, weather, wellbore instability and more. Claimed results:
  - more than 94% agreement with expert labels, calibrated on more than 1,500 DDR entries
  - AI-discovered NPT equal to 7% of reported NPT, or USD 42,000 per well
  - USD 4.2M saved across a 100-well campaign, about one month of rig time recovered
  - analysis cut from weeks to under 2 hours, and 30% higher engineer productivity

  [Provectus](https://provectus.com/case-studies/oil-gas-upstream-drilling-npt-genai)
- Halliburton ILT on rig-report text (2022) [VENDOR]. NLP plus unsupervised "well clustering" sets technical limits per well configuration and flags operations exceeding target. It claims analysis time cut "from days to minutes". No accuracy or hours figures. [Halliburton](https://www.halliburton.com/en/resources/investigating-invisible-lost-time-on-textual-data-using-artificial-intelligence)
- Equinor: AI delivered about USD 130M of value and savings in 2025, and more than USD 330M since 2020 [OFFICIAL company]. The drilling-relevant item is AI-driven well planning at Johan Sverdrup phase 3, which generated thousands of alternatives and saved the partnership USD 12M. Most of the remainder is predictive maintenance and seismic interpretation. [Equinor, 2026-01-07](https://www.equinor.com/news/20260107-artificial-intelligence-saved-equinor-usd-130-million); [JPT](https://jpt.spe.org/equinor-says-ai-saved-it-130m-in-2025)
- Equinor's NCS 2035 presentation (March 2026) lists "reducing nonproductive time (NPT), increasing rig availability" under planning and execution goals. This is a goal, not a result [OFFICIAL company]. [Offshore Norge PDF](https://www.offshorenorge.no/contentassets/abf39fcd873a4818b7d406f4cc013445/ncs-2035-equinor_lillharrietbrusdal.pdf)
- Exebenus (Norwegian, Stavanger) [VENDOR]:
  - Spotter ML Stuck Pipe agents predict in real time high-risk conditions from pressure differentials, hole cleaning, restricted movement and wellbore geometry.
  - Pulse auto-generates digital procedures (DOP/SID) to cut NPT.
  - No published quantified field results found.

  [Norwep, Exebenus Spotter](https://www.norwep.com/technologies-solutions/exebenus-spotter-stuck-pipe-agents); [Kongsberg Digital partner page](https://kongsbergdigital.com/partners/exebenus)
- Aker BP and DrillDocs: AI computer vision automatically detects cavings at the shakers, a first on the NCS, to cut pack-off and stuck-pipe risk [VENDOR/PRESS]. [OE Digital](https://www.oedigital.com/amp/news/522845-aker-bp-employs-drilldocs-ai-enabled-solution-to-enhance-wellbore-stability)
- Infosys notes that getting value on complex investigations like NPT "requires more than deploying an AI model" [VENDOR]. [Infosys blog](https://blogs.infosys.com/infosys-consulting/?p=1851)

Stuck pipe prediction (ML on time series)
- Khan et al. (2020, Energies): the best ANN classifier for real-time stuck pipe reached 88.89% accuracy, 91.89% sensitivity and 86.36% specificity. These are model metrics, not field NPT reductions [PAPER]. [UTP repository](https://khub.utp.edu.my/scholars/12937)
- D'Amicis et al. (2023, Upstream Oil and Gas Technology): HMM-based stuck pipe prediction from rare events [PAPER]. [Politecnico di Milano PDF](https://re.public.polimi.it/bitstream/11311/1259354/5/11311-1259354_Matteucci.pdf)
- Weatherford 2025 paper on ML drilling analytics and stuck pipe: claims NPT reduction, but no percentage in the abstract [VENDOR paper]. [Weatherford](https://www.weatherford.com/documents/papers/2025/from-reactive-to-proactive-machine-learning-powered-drilling-analytics-for-operational-excellence/)
- A conference paper built Volve time-series stuck pipe datasets and published them on GitHub [PAPER]. [OMAE session listing](https://omae.secure-platform.com/a/solicitations/214/sessiongallery/15586/application/128386)

### Inferences
- The proven, low-risk 2-day pattern: DDR text, then LLM structured extraction (event type, NPT hours, root cause, depth, hole section, formation), then cross-well aggregation. Several sources validate it with 90 to 96% expert agreement (SLB, Provectus), so a hackathon demo can credibly claim feasibility.
- Under-served niche, where the novelty lies: NCS-wide, pre-spud "offset-well hazard briefings" generated by LLM from public Sodir wellbore history text plus Havtil incident themes. Given a planned location, retrieve nearby offset wellbores and summarise documented problems (shallow gas, losses, tight hole, overpressure, kicks) with citations to the source text. The EAGE 2026 lessons-learned paper and SPE 217700 RAG show the approach works, but no public NCS-wide product appears to exist.
- Value framing: the Provectus figure (hidden NPT of 7% of reported NPT, USD 42k per shale well) is a US onshore number. Scaled to a USD 400k/day NCS rig, finding even 1 day of avoidable NPT per well is about USD 0.4M+ per well (my calc, rig rate only).
- Stuck pipe real-time prediction needs high-frequency WITSML. It is harder to demo convincingly in 2 days than text-based analytics, and incumbents already occupy it (Exebenus, SLB, Halliburton, Weatherford).

### Gaps
- Full texts of SPE 217700, 217671 and 220798 not read. Accuracy and dataset details beyond abstracts are unverified.
- No peer-reviewed quantified field NPT reduction (percent or USD) from ML stuck pipe prediction found.
- No quantified public results found for Cognite, NOV, Equinor's internal drilling platforms, or Sekal/Halliburton DrillTronics on the NCS. Secondary sources link Equinor's automation to "26 wells planned", but this is unverified. [enkiai (secondary)](https://enkiai.com/ai-infrastructure/equinor-drilling-automation-north-sea/)
- No source found on fully automated well-program generation with LLMs, or a named commercial "Well Planning copilot" with results.
- No ROP-optimisation results were collected in this pass. Literature exists, but searches were spent elsewhere.

## 3. Public data that supports this (Volve, Sodir FactPages, Diskos, Havtil/RNNP)

### Takeaway
Volve gives a ready-made, openly licensed DDR corpus: about 1,759 DDR files in WITSML, already converted to an LLM-friendly HF dataset. Sodir's open API (NLOD licence) covers every NCS wellbore and includes a `wellbore_history` table, the likely home of the free-text drilling history. Havtil publishes aggregate well control statistics and study reports, but not event-level data. Diskos final well reports are not open to the public.

### Cited Findings
- The Volve DDRs released by Equinor consist of 1,759 files, converted from WITSML to Alpaca format for summarisation. The test split covers 2016 campaigns, licence CC-BY-2.0 [DATASET]. [Hugging Face bengsoon/volve_alpaca](https://huggingface.co/datasets/bengsoon/volve_alpaca/raw/main/README.md)
- Volve drilling data has been used for public stuck pipe time-series datasets on GitHub [PAPER]. [OMAE listing](https://omae.secure-platform.com/a/solicitations/214/sessiongallery/15586/application/128386). It was also used in a UiS master's thesis on formation classification and bit dull grading [THESIS]. [UiS Brage](https://uis.brage.unit.no/uis-xmlui/bitstream/handle/11250/2780846/no.uis%3Ainspera%3A78834591%3A46747052.pdf?sequence=1)
- Sodir open data: the REST API is at https://factmaps.sodir.no/api/rest, and the DataService "contains all our public data". The API is meant to replace FactPages bulk downloads, and data is under the NLOD licence [OFFICIAL]. [Sodir open data](https://www.sodir.no/en/facts/about-us/open-data/); [FactPages changelog](https://www.sodir.no/globalassets/1-sodir/om-oss/informasjonstjenester/factpages_changelog.pdf)
- The FactMaps changelog lists a `wellbore_history` table keyed on `wlbNPDID_wellbore`, alongside oil sample, mud and log tables [OFFICIAL]. [FactMaps 3 changelog](https://www.sodir.no/49bc11/globalassets/1-sodir/om-oss/informasjonstjenester/karttjenester/factmaps_3_changelog.pdf)
- Exploration wellbore pages on FactPages, such as 25/1-3, are public [OFFICIAL]. [FactPages wellbore example](https://factpages.sodir.no/wellbore/pageview/exploration/all/349). For exploration wellbores more than two years old, Sodir also provides Well Data Summary Sheets (WDSS) [OFFICIAL]. [Sodir open data](https://www.sodir.no/en/facts/about-us/open-data/)
- Sodir has an exploration activity dashboard (2025) [OFFICIAL]. [Sodir news](https://www.sodir.no/en/whats-new/news/general-news/2025/new-dashboard-provides-insight-into-exploration-activity-on-the-ncs/)
- Sodir dry-well and discovery press releases (2022 to 2026) give short, structured narratives per exploration well: target, result, depth, rig. They are a clean text corpus. [Example: Dry well 25/8-C-23 D (2026)](https://www.sodir.no/en/whats-new/news/exploration-drilling-results/2026/dry-well-in-the-north-sea-258-c-23-d/)
- Havtil RNNP gives annual aggregate well control incident counts: 14 in 2024, average 13.9 per year over 2015 to 2024 [OFFICIAL]. [RNNP 2024](https://www.havtil.no/en/explore-technical-subjects2/rnnp/rnnp-2024/rnnp-2024-pressemelding); [RNNP 2024 summary report PDF](https://www.havtil.no/contentassets/d8f6b474fed74f709b920b9f8fb3df59/rnnp-2024-summary-report.pdf). Havtil investigation reports are public. [Havtil investigation reports](https://www.havtil.no/en/supervision/investigation-reports/)
- Licence relinquishment reports, which often summarise well results and prospect evaluations, are published as PDFs on FactPages [OFFICIAL]. [Example PL 878C](https://factpages.sodir.no/pbl/licence_status_reports/38723891_Relinquishment_report_PL_878C.pdf)

### Inferences
- A 2-day app can use the Sodir API, which is free, open-licence and needs no NDA, as the NCS-wide spine. It would hold wellbore coordinates, dates, rig, operator, purpose, total depth, plus mud and history tables. Volve DDRs then serve as the demo corpus for DDR-level NPT extraction. Volve is a single field (15/9, about 2008 to 2016), so DDR-level claims generalise poorly to the whole NCS.
- If the hackathon team has company access to Diskos final well reports or internal DDRs, which Odfjell Drilling as a rig contractor would have for its own rigs, the same pipeline scales. The demo should be built so private data can be swapped in.

### Gaps
- I could not confirm the columns of `wellbore_history`, or that its free text matches the "Wellbore history / Operations and results" prose on FactPages pages. Check the DataService metadata endpoint before building on it.
- Not verified here: Diskos access terms (generally restricted to licensees and members, with release of older data). DDR availability inside Diskos is also unverified.
- Havtil does not appear to publish event-level well control incident data, only aggregates and study PDFs.
- Equinor's official Volve download page was not re-verified in this session.

## 4. Pore pressure and shallow hazard prediction from offset wells and seismic

### Takeaway
On the NCS, 71% of well control incidents in 2013 to 2022 originated in wrong or too-low pore pressure estimates. Shallow gas and shallow water flow in top-hole and pilot-hole sections are a persistent, unreduced share. Havtil (2025 to 2026) explicitly calls for better offset and depletion data sharing, clearer uncertainty communication and checklists. That is a regulator-validated problem statement for an offset-well pore-pressure and shallow-hazard briefing tool.

### Cited Findings
- 71% of NCS well control incidents in 2013 to 2022 originated in erroneous or too-low pore pressure estimates (Havtil, Roar Sognnes). Havtil and GeoProvider recommend the following [OFFICIAL via PRESS]:
  - reduce pore-pressure and stress uncertainty
  - use MPD-style techniques and early inflow/outflow and mud-gas warning indicators
  - present predictions by measured depth with lower and upper bounds (per DNV-RP-C207) rather than P95 labels, with safe mud-weight windows per step
  - share depletion and injection pressure data across licences
  - adopt standard terminology, plots and a pore-pressure/borehole-stress checklist, building on IOGP RP 608

  [JPT, 2026-07-08](https://jpt.spe.org/study-highlights-link-between-pore-pressure-uncertainty-and-well-control-incidents)
- 2025 Havtil study "Challenges and Opportunities for Shallow Hazard Risk Reduction". It aims to use seabed and shallow data to avoid shallow-hazard locations in top-hole and pilot-hole drilling. Shallow gas and shallow water flows have been "a significant share" of NCS well control incidents for some years [OFFICIAL]. [Havtil 2025 study](https://www.havtil.no/en/explore-technical-subjects2/technical-competence/reports-from-projects/2025/challenges-and-opportunities-for-shallow-hazard-risk-reduction/); [GeoProvider slides](https://www.havtil.no/contentassets/82ebc4b482a4432a9c17e1d9f13566a2/shallow-hazards-geoprovider.pdf); [Shallow hazard risk reduction PDF](https://www.havtil.no/contentassets/8227a8937f704d5c900182a656884072/shallow-hazard-risk-reduction.pdf)
- Havtil's 2024 presentation lists well control incidents in pilot holes at Haltenbanken and in the North Sea. The extracted breakdown was garbled, so it is unverified [OFFICIAL]. [Havtil presentation](https://www.havtil.no/contentassets/82ebc4b482a4432a9c17e1d9f13566a2/well-control-incidents-and-main-focus-havtil.pdf)
- Haltenbanken lessons-learned deck (2025) [OFFICIAL]: even with all-green shallow hazard prognoses, pilot holes are essential for subsea template locations. It covers keeper-well design and NORSOK D-010 constraints when shallow gas is proven. [Havtil, lessons learned Haltenbanken](https://www.havtil.no/contentassets/c8fd98ea9d4b4a609e44393bc094b779/lessons-learned-and-strategy-from-haltenbanken.pdf)
- Activities Regulations section 83 requires that the well structure and drilling parameters prevent gas or formation fluid from threatening personnel, environment or facility [OFFICIAL]. [Havtil regulations s.83](https://www.havtil.no/en/regulations/all-acts/the-activities-regulations3/XV/83)
- Havtil RNNP 2022 study on causal factors for well control incidents (Norwegian, 40 pp.). Not extracted here [OFFICIAL]. [Havtil PDF](https://www.havtil.no/contentassets/0075fda7233846c9af020fbc34ccf921/causal-factors-and-measures-for-well-control-incidents-related-to-norwegian-petroleum-activities---rnnp-2022-study.pdf)

### Inferences
- Strongest NCS-specific, regulator-backed app angle: an "Offset-Well Hazard Brief" generator. Input is a planned well location or licence block. The app pulls nearby wellbores from the Sodir API (coordinates, mud weights from the mud table, history text, discovery/dry status). An LLM extracts hazard mentions (shallow gas, kicks, losses, overpressure, tight hole, H2S) with depth and citation. Output is a one-page brief by measured depth with lower and upper bounds, matching Havtil's recommended format. This addresses the 71% pore-pressure root cause and the shallow-hazard theme directly. Each well control incident averages about 2.3 days of NPT (35 days over 15 incidents in 2025, my calc), or about USD 0.9M+ in rig rate per incident.
- Quantitative pore-pressure prediction (Eaton or ML from logs and seismic velocities) is out of scope for 2 days. LLM summarisation of offset-well text plus mud-weight tables is feasible and demoable.

### Gaps
- No open dataset of NCS shallow-gas observations per wellbore found, beyond what FactPages history text or WDSS may contain.
- No peer-reviewed ML pore-pressure prediction results on NCS data collected in this pass.
- Total incident count behind the 71% (2013 to 2022) not given in the JPT article.
