# AI for seismic interpretation and well-log analysis (2022-2026): state of the art, open code, and value

Scope note: 21 searches/fetches on 2026-11-17. Most claims below come from arXiv abstract pages, GitHub READMEs, and vendor or regulator pages. I did not open full PDFs. Benchmark numbers are as reported by the authors and were not reproduced. "2-day feasible" flags are my own judgement, marked as inferences.

## 1. Seismic AI: foundation models, faults, horizons, geobodies, facies, well tie. What is open and runnable?

### Takeaway
Seismic AI has shifted to self-supervised foundation models (ViT/MAE backbones, SAM adaptations), and two of them are directly usable: Sheng et al.'s SFM (MIT license, weights downloadable) and the NCS-Model, which was trained on Norwegian DISKOS seismic and has weights reported as open-sourced. For a 2-day hackathon, the safest runnable building blocks are pretrained FaultSeg3D (Keras, 128^3 cubes), SFM fine-tuning or embedding examples, zero-shot SAM with prompts, and the dlseis automated well-tie package, which ships with Volve weights.

### Cited Findings
**Foundation models**
- SFM (Sheng et al., Geophysics 2025, vol. 90 no. 2, IM59-IM79; arXiv 2309.02791) was pretrained on 2,286,422 2D seismic images from 192 3D volumes worldwide. — [ADS](https://ui.adsabs.harvard.edu/abs/2025Geop...90.IM59S/abstract); [arXiv 2504.17384 search snippet](https://arxiv.org/pdf/2504.17384)
- The SFM repo is MIT licensed and has 4 checkpoints: SFM-Base and SFM-Large at 224x224, and SFM-Base-512 and SFM-Large-512 at 512x512 (Google Drive or Baidu). It includes downstream examples for facies classification (768x768 data), geobody identification, reflectivity inversion, denoising and interpolation (all 224x224), plus a facies `visualization.ipynb`. The environment is Python 3.9.12 and PyTorch 1.8.1+cu111. The README states no hardware requirements. — [GitHub shenghanlin/SeismicFoundationModel](https://github.com/shenghanlin/seismicfoundationmodel)
- **NCS-Model** (Ordonez, Forgaard, Wade, Bugge, Nese, Waldeland; arXiv 2603.23211, March 2026, revised Oct 2026, Geophysics) is a family of MAE ViT models pretrained on full-stack 3D time and depth volumes from the public **DISKOS** database on the Norwegian Continental Shelf. It comes in 2D, 2.5D multi-view and 3D tokenizations. Evaluation uses frozen backbones with kNN and linear probing on NCS interpretation benchmarks. NCS-2.5D scored the best average, ahead of an ImageNet MAE, a "frontier vision foundation model", and a globally pretrained seismic FM. Each variant took about 250 GPU-hours to pretrain. The abstract says the weights are open-sourced and the embeddings support similarity search for interactive interpretation. I found no direct repo link on the abstract page. — [arXiv 2603.23211](https://arxiv.org/abs/2603.23211)
- **SeisDFE** (Guo, Wu et al., arXiv 2611.20745, submitted 16 Nov 2026) is a 7B-parameter seismic FM pretrained on 5.34M 2D images from more than 500 volumes. It uses a frozen encoder with task decoders and is evaluated on facies, salt, faults and relative geologic time. The authors claim it beats prior seismic FMs on all four tasks. With only 2 annotated F3 sections, it gains 12-19 points of whole-volume mIoU over baselines. No code or weights were listed. — [arXiv 2611.20745](https://arxiv.org/abs/2611.20745)
- **TGS SFM**: Sansal et al. (2025) describe a 1.8B-parameter model and a 660M-parameter 3D ViT-H pretrained on 63 surveys using the open-source MDIO storage format. I found no public weights. MDIO itself is open source (TGSAI GitHub). — [TGS scaling SFMs](https://www.tgs.com/articles/scaling-seismic-foundation-models); [TGS press release MDIO](https://www.tgs.com/press-releases/tgs-launches-new-open-source-solution-for-multidimensional-energy-data); [github.com/TGSAI](https://github.com/TGSAI)
- ThinkOnward hosts a gated "denoizer" seismic model on Hugging Face, and a "SeisGround" HF repo runs on a frozen third-party SFM (ViT-B/16 at 512). — [HF thinkonward/denoizer](https://huggingface.co/thinkonward/denoizer); [HF seisground-weights](https://huggingface.co/thirdExec/seisground-weights)
- Review papers: "Foundation Models for Seismic Data Processing: An Extensive Review" — [arXiv 2503.24166](https://arxiv.org/html/2503.24166v2); "AI for Subsurface Imaging Understanding: A Decade Review" (covers 2015-2025 structural, geobody, facies and property tasks) — [arXiv 2606.09094](https://arxiv.org/pdf/2606.09094); a geophysics FM workflow paper — [arXiv 2504.17384](https://arxiv.org/pdf/2504.17384); a light-weight processing FM — [arXiv 2503.10092](https://arxiv.org/pdf/2503.10092)

**SAM for seismic**
- Zero-shot SAM with domain-guided prompting (Ahmad, Bedle, Mustafa; arXiv 2606.15786, 2026) combines attribute and colormap choices with hybrid sparse-point and dense-mask prompts. The authors conclude SAM works best as an interpreter's assistant, not as an autonomous tool. — [arXiv 2606.15786](https://arxiv.org/abs/2606.15786)
- Seismic Fault SAM (arXiv 2407.14121, 2024) adds lightweight adapters and a 2.5D strategy, and runs fully automated fault segmentation with no prompting. — [arXiv 2407.14121](https://arxiv.org/html/2407.14121v1)
- "Segment any geobody" with a multi-modal prompt engine (arXiv 2409.04962, 2024): vanilla SAM performed poorly, while the fine-tuned version beat UNet and DeepLabV3+ on multi-geobody tasks. — [arXiv 2409.04962](https://arxiv.org/html/2409.04962v1)
- AAPG 2025 abstract: zero-shot and fine-tuned SAM and SAM 2 for faults, channels and stratigraphic sequences. — [AAPG 2025](https://imageevent.aapg.org/portals/26/abstracts/2025/4315035.pdf)

**Faults**
- FaultSeg3D (Wu et al., 2019, the standard baseline) has an official Keras repo with a downloadable pretrained model and a `prediction.ipynb` demo. It was trained on 200 synthetic seismic/fault pairs of 128x128x128. — [GitHub xinwucwp/faultSeg](https://www.github.com/xinwucwp/faultSeg); [SBGf 2025 abstract](https://sbgf.org.br/mysbgf/eventos/expanded_abstracts/19th_CISBGf/VBVQP6JVNR.pdf)
- NVIDIA reports that fault systems which "can take up to a month to analyze by hand" are processed in seconds on a GPU with the CNN. This is a qualitative claim, not a benchmark. — [NVIDIA blog 2019](https://blogs.nvidia.com/blog/2019/12/26/deep-learning-seismic-fault-systems)
- The FORCE 2020 fault-mapping competition data was a seismic cube "with some migration issues", released with Petrel-ready files. Only 5 of 80 signed-up teams submitted a valid fault cube. Sparveon won, followed by Equinor and Woodside. — [GitHub bolgebrygg/Force-2020](https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition)

**Horizons / RGT**
- Older but open approaches: multi-resolution horizon tracking from a few training images (Peters et al.) — [arXiv 1812.11092](https://arxiv.org/pdf/1812.11092); horizon detection as segmentation with RGT via phase unwrapping (Wu & Zhang) — [arXiv 1804.06814](https://www.arxiv.org/pdf/1804.06814); open-sourced binary-segmentation horizon detection across cubes — [PapersWithCode](https://www.paperswithcode.com/paper/seismic-horizon-detection-with-neural)
- DeepISMNet (Bi, Wu et al., GMD 2022) is a CNN implicit structural model built from sparse horizon and fault data. Code availability is unconfirmed. — [GMD preprint](https://gmd.copernicus.org/preprints/gmd-2022-117/gmd-2022-117.pdf)
- SeisDFE evaluates relative geologic time estimation as a downstream FM task. — [arXiv 2611.20745](https://arxiv.org/abs/2611.20745)

**Facies benchmark**
- F3 Netherlands facies benchmark (Alaudah et al., Interpretation 2019): a fully annotated 3D geologic model with deconvnet baselines and an evaluation scheme. Code: olivesgatech/facies_classification_benchmark. Data: Zenodo zip of about 2.1 GB. — [arXiv 1901.07659](https://arxiv.org/abs/1901.07659v1); [Zenodo 3755060](https://zenodo.org/records/3755060); [GitHub olivesgatech](https://www.github.com/olivesgatech/facies_classification_benchmark)

**Seismic-to-well tie**
- dlseis_well_tie (Tschannen, Fraunhofer ITWM): a variational CNN for wavelet extraction, trained on synthetic reflectivity/seismic pairs, with random search and Bayesian optimization of tie parameters. It **includes pretrained weights and Volve + Poseidon data**. Paper: Computers & Geosciences, 2022. — [GitHub dlseis/dlseis_well_tie](https://github.com/dlseis/dlseis_well_tie); [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0098300422000784)
- Di et al. 2023 (Geophysical Prospecting): a self-supervised dual-task autoencoder for time-variant wavelets. It beat statistical wavelet extraction and DTW on 2 field datasets. Code status unknown. — [Wiley](https://onlinelibrary.wiley.com/doi/10.1111/1365-2478.13333)

### Inferences
- The most hackathon-relevant model is the **NCS-Model**: it is trained on the same basin and the same DISKOS data the hackathon likely uses, and it is designed for frozen-embedding kNN, linear probing and similarity search. A "click a feature, find similar seismic everywhere" app needs no training, only embedding plus a vector index. Feasibility depends on actually locating the weights, so check the PDF or the authors (NR, the Norwegian Computing Center, judging by Waldeland/Ordonez) before committing.
- 2-day feasible on 1 GPU: FaultSeg3D inference on 128^3 tiles of an NCS cube (a sliding window over a full cube takes minutes on a GPU; CPU is likely tens of minutes for a modest cube, but this is unbenchmarked), SFM embeddings plus clustering for unsupervised facies, zero-shot SAM/SAM2 with point prompts on inline images, and a dlseis well tie on an NCS well with a checkshot.
- Not 2-day feasible: pretraining any FM (NCS-Model took about 250 GPU-hours per variant) or using SeisDFE (7B, no weights).

### Gaps
- No NCS-Model weights URL was found on the abstract page.
- I found no published CPU or GPU runtime figures for SFM, FaultSeg3D or SAM on full 3D cubes.
- No Parihaka or SEAM AI facies benchmark numbers or mIoU values were retrieved.
- No 2022-2026 sources were found for open ML for DHI/AVO screening, seismic super-resolution, or salt-specific open models. Denoising appears only via the SFM example and the ThinkOnward denoizer.

## 2. Well logs: lithology, imputation, petrophysics, tops/correlation, QC, pore pressure

### Takeaway
FORCE 2020 (NCS wells, NPD lithostratigraphy, a penalty-matrix score) remains the reference benchmark, and the best solutions were tuned gradient-boosted trees (XGBoost), not deep nets. Recent work points toward well-log foundation models (WLFM, TGS's promptable formation-top model), but I found none with public weights. Classic petrophysics (Vsh, porosity, Archie Sw) is fully covered by open Python libraries, which makes it the easiest base layer for an app.

### Cited Findings
**Lithology (FORCE 2020)**
- FORCE 2020 lithology: 148 teams on the open leaderboard. The top 30 were asked for pretrained models for the hidden test set, and 13 ran. Final scores: Olawale Ibrahim -0.4690, GIR -0.4792, Lab.ICA -0.4954, H3G -0.5045, ISPL -0.5084. The open-leaderboard leader ended 11th. The data is LAS/CSV with NPD lithostratigraphy and X/Y positions; models and weights are on external Drive. Citation: Bormann et al. 2020 (Zenodo DOI). — [GitHub bolgebrygg/Force-2020](https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition)
- The winner used a single XGBoost with 10-fold stratified CV. Ensembles did worse on local validation. GIR also used XGBoost. The organisers say the top 5-7 were so close they could all be considered winners. — [Medium (winner)](https://ibrahim-olawale13.medium.com/force-2020-machine-learning-lithology-predictionwinning-solution-8cbf78290b41); [NPD results](https://www.npd.no/en/force/events/results-of-the-FORCE-2020-lithology-competition/); [GitHub olawaleibrahim](https://github.com/olawaleibrahim/2020_FORCE_Lithology_Prediction)
- The penalty matrix penalises geologically plausible confusions (shale vs. marl) less than implausible ones (shale vs. anhydrite). — [GeoExpro](https://geoexpro.com/and-the-winner-is-the-human-with-the-machine/); [Sodir geological summary PDF](https://www.sodir.no/globalassets/2-force/2020/seminars/contest-machine-learning/blog-post-litho-facies-competition-geological-summary.pdf)
- ThinkOnward hosts a "FORCE well logs" challenge page. — [ThinkOnward](https://thinkonward.com/app/c/challenges/force-well-logs/overview)

**Well-log foundation models**
- WLFM (arXiv 2509.18152, Sep 2025) was pretrained on multi-curve logs from 1,200 wells using patch tokenization, masked-token modeling and stratigraphy-aware contrastive learning. Porosity MSE is 0.0041 (0.0038 fine-tuned). Lithology accuracy is 74.13% (78.10% fine-tuned). Masked-curve reconstruction shows offsets in shallow and ultra-deep intervals. No code or weights were stated. — [arXiv 2509.18152](https://arxiv.org/abs/2509.18152)
- TGS IMAGE 2025: a "promptable" well-log foundation model takes a log plus a formation name and returns the formation depth, fine-tuned on manually picked tops. — [TGS IMAGE 2025 PDF](https://www.tgs.com/hubfs/2025%20IMAGE%20Preliminary/IMAGE2025_Well%20log%20foundation%20model%20-%20Making%20promptable%20AI%20models%20for%20well%20log%20interpretation_DA_03142025_Final.pdf)
- OpenSeisML is an open large-scale real seismic and well-log dataset for generative AI (arXiv 2605.20539). I saw the title only. — [arXiv 2605.20539](https://arxiv.org/pdf/2605.20539)

**Synthetic logs / imputation (DTS, DTC)**
- CVAE+LSTM dual model to impute DTS and other logs on Volve (EGU 2025). — [EGU25-5429](https://meetingorganizer.copernicus.org/EGU25/EGU25-5429.html)
- A random-forest DTS on Volve with a blind well found DTC was the top feature (39% importance). — [Hibatullah portfolio](https://ichsanhibatullah.github.io/portfolio/volvesonicdts)
- Deep sequence learning predicts DTC and DTS from common logs across fields (2022). — [Bohrium/arXiv listing](https://bohrium.dp.tech/paper/arxiv/811978860655542272)
- Volve ML notebooks repo (yohanesnuwara). — [GitHub volve-machine-learning](https://github.com/yohanesnuwara/volve-machine-learning)

**Formation tops / correlation**
- A recommender system predicts unpicked top depths from tops already picked in other wells, with no logs needed; error falls as training data grows. — [arXiv 2202.08869](https://arxiv.org/pdf/2202.08869)
- 1D CNN ensemble (GeoConvention 2025): trained on about 3,000 wells, it picked consistent Mannville tops across about 20,000 wells, using ensemble spread as a confidence measure. — [GeoConvention 2025](https://geoconvention.com/wp-content/uploads/abstracts/2025/114724-automated-formation-top-picking-with-1d)
- Earlier deep correlation: BiLSTM and Inception autoencoder CNN (zones as classification, tops as edge detection) — [SPE ATCE 2020](https://onepetro.org/SPEATCE/proceedings-abstract/20ATCE/20ATCE/D022S061R020/449943); a 1D conv autoencoder with "image stitching" point matching, trained on more than 30 wells — [SPE ADIPEC 2020](https://onepetro.org/SPEADIP/proceedings-abstract/20ADIP/20ADIP/D021S054R003/452256)
- DTW auto-picking of tops is patented (US11914099B2). — [Google Patents](https://patents.google.com/patent/US11914099B2/en)

**Petrophysics libraries**
- petropy (on lasio) covers Vsh, porosity, Sw (Archie, Simandoux), Timur permeability and pay flags — [PyPI petropy](https://pypi.org/project/petropy/0.1.5). petrolib covers Vsh (Clavier, Stieber, Larionov), Sw (Archie, Simandoux) and Pickett plots — [PyPI petrolib](https://pypi.org/project/petrolib). stoneforge covers Archie, Fertl, Indonesia and Simandoux behind one interface — [stoneforge docs](https://giecaruff.github.io/stoneforge/modules/petrophysics/water_saturation.html). welly (on lasio) handles multi-well management and curve QC — [PyPI welly](https://pypi.org/pypi/welly/)

### Inferences
- 2-day feasible on CPU: an XGBoost lithology model with FORCE 2020 data (minutes to train), a DTS/DTC/RHOB imputation model with gradient boosting plus a blind-well test, a deterministic petrophysics pipeline (lasio, petropy or stoneforge), DTW-based top propagation between neighbouring NCS wells using NPD/Sodir lithostratigraphy as labels, and a recommender-style top prediction from Sodir's published tops.
- The ambitious variant is a "promptable" tops picker (TGS-style) trained on FORCE plus Sodir tops. A small 1D CNN or transformer is trainable on one GPU in hours, but performance is unproven, so it is risky in 2 days.

### Gaps
- No sourced 2022-2026 open models were found for log depth matching, automated log QC/despiking, core-log integration, or pore-pressure prediction from logs (Eaton/Bowers ML). Searches were not run specifically for these because of the call budget.
- No transformer-specific DTS paper for Volve was retrieved.
- The exact number of FORCE 2020 wells and classes was not stated on the GitHub page. My recollection is about 98 training wells, 10 open-test wells and 12 lithology classes, but this is unverified and should be checked in the repo data.

## 3. Time and money: manual effort and value of faster interpretation

### Takeaway
NCS exploration wells average about US$36-42M each (Westwood aggregates), and roughly half to 72% fail to find commercial volumes depending on the definition. Published ML speedups for interpretation are vendor case studies showing 60-70% fewer hours (for example 400 h to 144 h for top-salt picking), and manual structural interpretation is described as weeks to months.

### Cited Findings
- Westwood (NCS 2014-2023): 289 exploration wells, about US$12.1bn drilling cost, which works out to about **US$42M per well**. 80 commercial discoveries, 2.5 bnboe, a commercial success rate of 28% (6% in 2015, 55% in 2023), and a finding cost of US$4.8/boe. High-impact wells: 100 drilled, 7 commercial. — [Westwood Insight](https://www.westwoodenergy.com/news/westwood-insight/westwood-insight-norway-state-of-exploration-2014-2023)
- A separate Westwood 10-year figure: 279 well programmes, US$10.0bn, 89 commercial discoveries, which works out to about **US$36M per well**. — [Offshore Magazine/Westwood](https://www.offshore-mag.com/drilling-completion/article/55131092/westwood-global-energy-group-norway-drillers-focused-on-near-infrastructure-targets)
- Technical success on the NCS is about 50%: 468 wildcats in 2010-2024 gave 229 discoveries. — [Norskpetroleum](https://www.norskpetroleum.no/en/exploration/exploration-activity/)
- 2024: 42 wells and 16 discoveries, with an average discovery of 15.7 MMboe (down 30%) — [S&P Global](https://www.spglobal.com/energy/en/news-research/latest-news/crude-oil/010925-higher-norway-exploration-drilling-yields-less-oil-and-gas-in-2024-regulator). 2025: 49 wells and 21 discoveries — [Sodir resource report 2026](https://www.sodir.no/en/whats-new/publications/reports/resource-report/resource-report-2026/exploration/)
- About NOK 660bn was invested in NCS exploration over 2004-2023. Exploration returns about NOK 3 per NOK invested in the Norwegian Sea and about NOK 2 in the Barents Sea. — [World Oil / Sodir](https://worldoil.com/news/2024/9/23/20-years-of-offshore-exploration-yields-plethora-of-valuable-discoveries-with-abundant-remaining-potential-norwegian-offshore-directorate-reports/)
- SLB Kwanza Basin case study (vendor): ML cut top-of-salt interpretation from **400 h to 144 h** and base-of-salt from **320 h to 100 h**. — [SLB](https://www.slb.com/resource-library/case-study-with-navigation/di/accelerating-seismic-interpretation-in-the-kwanza-basin)
- Manual structural interpretation "typically takes months of interpreters' time", and a new area may demand "several weeks" (patent filings). Manual seismic labelling takes "weeks or months" (SoftServe vendor). — [USPTO 11320551](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11320551); [SoftServe case study](https://www.softserveinc.com/en-us/case-study/machine-learning-in-seismic-data-interpretation)
- Fault interpretation "can take up to a month" by hand versus seconds with a CNN (NVIDIA). — [NVIDIA blog](https://blogs.nvidia.com/blog/2019/12/26/deep-learning-seismic-fault-systems)
- Explainable ML for hydrocarbon prospect risking (DHI/AVO-related risking). — [arXiv 2212.07563](https://arxiv.org/pdf/2212.07563)

### Inferences
- Pitch math: at about US$36-42M per NCS exploration well and a 28% commercial success rate, avoiding a single dry well per year pays for a large interpretation-AI effort. Shaving 60-70% of interpreter hours (the SLB-type figure) on a prospect is the defensible productivity claim. Both are vendor or aggregate numbers, so present them as such.
- The user's brief cited "$30-100M per exploration well". The Westwood aggregates support about $36-42M as the NCS average, with deepwater or HPHT wells higher. I found no source for the $100M upper end.

### Gaps
- I found no peer-reviewed, published ROI for ML interpretation on the NCS.
- No sourced figure was found for hours per well for manual well correlation, tops picking or petrophysical evaluation.
- No source was found for exploration cycle time (prospect to drill decision) on the NCS.

## 4. LLMs + interpretation models: agents and VLMs

### Takeaway
Agentic geoscience is early. Published agents target seismic modelling and processing workflows (MCP servers for SPECFEM, natural-language processing flows), and VLM benchmarks show frontier models are weak at geological diagram and map reasoning. I found no published agent that runs fault, horizon or log interpretation tools end to end and explains the results, which is an open niche for a hackathon.

### Cited Findings
- Seismology modelling agent (arXiv 2512.14429, Dec 2025): an LLM agent that builds and uses **MCP servers** for the SPECFEM seismic modelling suite. — [arXiv 2512.14429](https://arxiv.org/pdf/2512.14429)
- Kanfar et al. 2025 (The Leading Edge 44(2):142-151): geophysicists state goals and constraints in natural language, and an agent proposes seismic processing flows. Cited via 2512.14429. — [arXiv 2512.14429](https://arxiv.org/pdf/2512.14429)
- An agentic AI framework for subsurface discovery and geothermal monitoring (arXiv 2511.03852). I saw the title only. — [arXiv 2511.03852](https://arxiv.org/pdf/2511.03852)
- VLMs: GeoMap-Bench (CVPR 2025) reports that leading VLMs have key limitations reading geologic maps — [Microsoft Research](https://www.microsoft.com/en-us/research/?p=1137041). Geo-Strat-RL is a synthetic benchmark of stratigraphic diagrams and seismic-style images for recovering event histories; diagram-to-seismic transfer works, but synthetic data misses real noise — [EmergentMind 2606.25000](https://www.emergentmind.com/papers/2606.25000). LithoBench (May 2026) shows VLMs are weak at higher-order lithology reasoning (remote sensing) — [alphaXiv 2605.07640](https://www.alphaxiv.org/abs/2605.07640)
- The NCS-Model embeddings are explicitly pitched for similarity search in interactive interpretation, which is a natural retrieval tool for an agent. — [arXiv 2603.23211](https://arxiv.org/abs/2603.23211)
- TGS frames LLMs plus seismic FMs as complementary for subsurface E&P. — [Offshore Magazine / TGS](https://www.offshore-mag.com/geosciences/article/55241563/tgs-from-llms-to-seismic-foundation-models-ai-can-be-utilized-for-subsurface-ep)

### Inferences
- A strong 2-day concept is an "interpreter copilot" agent: an LLM calling tools such as FaultSeg3D inference, SAM point-prompt segmentation, an NCS-Model or SFM similarity search, an XGBoost lithology predictor, a petrophysics calculator, and a dlseis well tie. It would explain outputs with Sodir/NPD well metadata and lithostratigraphy, and render overlays. The tools are each runnable, and the novelty is the orchestration plus explanation.
- Do not rely on a VLM alone to read seismic: published benchmarks show weak geological visual reasoning. Use VLMs to caption or explain outputs of specialised models, not to replace them.

### Gaps
- No published evaluation was found of GPT-4V/GPT-5-class or Claude VLMs on real seismic sections.
- No open-source geoscience agent was found that wraps interpretation tools (only the SPECFEM MCP work for modelling).
