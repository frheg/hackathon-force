# The data, explained (2026-11-18)

A guide for someone new to oil and gas: how the industry works, how the shelf names and measures things, what each
dataset captures (with its real numbers, quirks and what it is good for), how the datasets connect, what we found
in them, and a glossary of every term. The numbers come from profiling the data on disk (`python -m sketches.atlas`);
the Data Atlas (`/atlas/`) shows the same with charts.

Contents: [1. The industry in five minutes](#1-the-industry-in-five-minutes) ·
[2. How the shelf names and measures things](#2-how-the-shelf-names-and-measures-things) ·
[3. The datasets](#3-the-datasets) · [4. How they connect](#4-how-the-datasets-connect) ·
[5. Findings](#5-findings) · [6. Glossary](#6-glossary)

---

## 1. The industry in five minutes

**What is down there.** Oil and gas formed from the remains of tiny marine organisms, buried in mud that became
**source rock** (on the NCS mostly the Late Jurassic Draupne Formation). Buried deep enough (about 2 to 5 km) the
rock heated up and the organic matter cooked into oil and gas. These fluids are lighter than water, so they crept
upward through the rocks until something stopped them: a **trap**, where a porous **reservoir** rock (usually
sandstone, sometimes chalk) sits under a tight **seal** (shale, salt). Oil and gas sit in the tiny pores between
sand grains, not in caves. That gives the four questions of every prospect: is there a source, a reservoir, a
seal and a trap? Exploration is the art of answering them before drilling, because a well costs USD 36 to 42
million and most wildcats find nothing.

**The life of a field.** Each stage leaves data behind, and the datasets here are those traces:

| Stage | What happens | Typical duration | Data it leaves (in this repo) |
|---|---|---|---|
| Licence | The state awards a **production licence** (PL) to a group of companies, one of them the **operator** | | FactPages `licence` |
| Explore | **Seismic** is shot and interpreted; **wildcat** wells test the best traps | 2 to 10 years | seismic (F3, Adele), well logs, cores, completion reports |
| Discover and appraise | A find; **appraisal** wells measure size and quality; a **DST** proves it flows | 1 to 5 years | FactPages `discovery`, DST, RealPore, DISKOS-QA |
| Develop | A **PDO** (plan for development and operation) is approved; platforms or subsea templates are built; **development** wells drilled | 3 to 8 years | Volve daily drilling reports, FactPages casing, mud, LOT |
| Produce | Oil and gas flow; rate peaks (**plateau**), then **declines**; water rises | 10 to 50 years | FactPages monthly production, reserves |
| Late life | Wells are **plugged and abandoned** (P&A); facilities removed; empty reservoirs may store CO2 | | completion reports (what is in each well), FactPages status |

If a licence is given up before production, the companies write a **relinquishment report** explaining why
(the text corpus has 599 of them).

**Where the money goes.** These are the problems the tools in this repo go after (sources in
`docs/reports/Hackathon app ideas with NCS data.md`):

- **Plugging old wells.** About 2,900 NCS wellbores are waiting to be plugged, at NOK 50 million to over NOK 1
  billion each. Only 30 to 40 are plugged a year, and the state pays 78 % through the tax system.
- **Well control.** 71 % of NCS well-control incidents (2013 to 2022) came from wrong or too-low pore-pressure
  estimates. A floating rig costs about USD 400,000 a day, so every lost day costs that much.
- **Stranded discoveries.** About 91 discoveries holding over 500 million Sm³ o.e. are awaiting a decision. Most
  are only profitable as **tie-backs** to an existing platform, and the platforms are closing.
- **Searching for data.** 75 % of geoscientists spend over a quarter of their time on data management. The answer
  to most questions sits in a scanned report from the 1980s.
- **Interpreting seismic.** Manual interpretation takes weeks to months. Equinor says AI let it interpret seismic
  ten times faster in 2025.

---

## 2. How the shelf names and measures things

### Names

- **The NCS** (Norwegian Continental Shelf) is split into three areas: the **North Sea** (south, oldest and most
  drilled, 1,565 exploration wellbores), the **Norwegian Sea** (middle, 440) and the **Barents Sea** (north, 196).
- **Quadrants and blocks.** The map is cut into quadrants of 1° latitude by 1° longitude, numbered, and each
  quadrant into 12 blocks. Block 15/9 is block 9 in quadrant 15 (where Sleipner and Volve lie).
- **Wellbore names** follow `quadrant/block-number`, plus suffixes:
  - `15/9-19`: exploration well 19 in block 15/9.
  - `15/9-19 A`, `B`: sidetracks, meaning new wellbores drilled out of the first one toward a new target.
  - `15/9-19 ST2`, `T2`: technical sidetracks, redrilled around a problem such as stuck pipe.
  - `25/8-5 S`: the S marks a deviated wellbore, one that does not go straight down.
  - `15/9-F-12`: a development well. The letter is the platform or subsea template (Volve's F), and the number is
    the slot.
  - `25/4-C-1 HT2`: template C, well 1. In practice H marks a horizontal section and T2 the second technical
    sidetrack.

  Spellings vary between sources (`NO 15/9-F-12`, `15/9-F- 12`, `15_9-F-12`). The repo normalises all of them to
  one form (`common.norm`), which is what makes the datasets joinable.
- **Wellbore and well** are not the same thing. A well is the surface location; a wellbore is one hole from
  surface to bottom, and a well can have several. Almost every dataset is per wellbore.
- **NPDID** is Sodir's numeric id for each object (wellbore, field, licence). Sodir was called the NPD
  (Norwegian Petroleum Directorate) until 2024, hence the name. Joining on it is safer than joining on names: this
  is how RealPore was matched to FactPages.

### Depth

- **MD** (measured depth) is the length along the hole. **TVD** (true vertical depth) is straight down. In a
  deviated well MD is longer than TVD. Logs, cores and formation tops are in MD; pressure depends on TVD.
- Depths are measured from a reference, usually **RKB** (the rig's kelly bushing, some tens of metres above the
  sea). "2,500 m MD RKB" means 2,500 m along the hole from the rig floor. Water depth is from sea level to the seabed.
- Seismic is not measured in metres but in **TWT** (two-way time): milliseconds for sound to go down and back up.
  Turning time into depth needs a velocity model or a well tie (VSP, sonic log).

### Units

| Quantity | Unit | Rule of thumb |
|---|---|---|
| Oil and gas volumes | **Sm³** (standard cubic metre, at 15 °C and 1 atm) | 1 Sm³ oil = 6.29 barrels |
| All products in one number | **Sm³ o.e.** (oil equivalent) | 1 Sm³ oil = 1,000 Sm³ gas = 1 Sm³ o.e.; MSm³ = million, GSm³ = billion. 1 GSm³ gas = 1 MSm³ o.e. |
| Mud weight, leak-off test, pressure gradient | **g/cm³**, also called **sg** (specific gravity) | water 1.0 to 1.03; typical mud 1.1 to 1.9; 1 sg = 8.33 ppg |
| Porosity | **%** of rock volume (or fraction, v/v) | good reservoir 20 to 30 %; tight below 10 % |
| Permeability | **mD** (millidarcy) | below 1 mD tight; 10 to 100 moderate; above 100 good; varies over 7 orders of magnitude, so always shown on a log scale |
| Gamma ray | **API** units | sand and carbonate below about 60; shale above about 80 to 100 |
| Bulk density | **g/cm³** | quartz 2.65; porous sand 2.2 to 2.4; salt 2.04 |
| Resistivity | **ohm·m** | brine-filled rock 0.5 to 5; oil or gas filled 10 to 1,000; log scale |
| Sonic | **µs/ft** (microseconds per foot) | fast hard rock 50 to 70; soft shale 100 to 150 |
| Seismic time | **ms TWT** | the Adele cube records 4 s |
| Rig time | hours, days; money at about USD 300k to 500k per rig day | |

---

## 3. The datasets

Ten datasets: six from the organisers' mail (`data/official/`, the official source) and four found before the
event (`data/`). For each: what it captures, how it was made, what a record looks like, the numbers, the quirks,
and what it is good for.

### 3.1 Completion reports (from the organisers)

**What it captures.** The **final well report** (also called the completion report or end-of-well report) of each
wellbore. Every operator must deliver one when a well is finished. It is the most complete single account of a
well:
- why it was drilled;
- the rocks met, with formation tops and a lithology description;
- shows of oil and gas;
- cores taken, logs run and tests done;
- pressures, temperatures and mud weights;
- drilling problems such as losses, kicks and stuck pipe;
- the casing and cement left in the hole;
- the result, and how the well was left (plugged, suspended, completed as a producer).

**How it was made.** The reports are the original PDFs (mostly scans of typed paper reports from the 1970s on),
published 17 November 2026 (Zenodo 24320092, CC BY 4.0). In 2026 an undisclosed pipeline turned each one into
JSON: a **document layout model** found the pages, text blocks, tables and figures, and other machine-learning
models described the content of pages, images and tables. That makes even scanned log plots and well diagrams
partly searchable.

**The numbers** (from the metadata CSV):

| | |
|---|---|
| Wellbores | 4,441 in the metadata (the title says 4,462), 3,960 of them found in FactPages |
| Files | 5,453 PDF reports (102 GB, median 10 MB) and 5,327 JSON |
| Wellbore types | 2,975 development, 1,442 exploration, 24 other |
| Decade drilled | 1970s: 364 · 1980s: 751 · 1990s: 1,422 · 2000s: 1,187 · 2010s: 203 |
| Written by | 58 companies; Statoil 1,528, Norsk Hydro 1,132, ConocoPhillips 483, StatoilHydro 275, BP 274, Esso 212 |
| Archive | 4 tar parts of 28 GB each, to be concatenated and unpacked (the fetch script does this) |

**The metadata** has one row per file. The columns that matter:
- `Wellbore Name`: the join key.
- `Wellbore Type`.
- `Delivery Company`: who wrote the report.
- `Format`: PDF or JSON.
- `File Size (MB)`.
- `Create Date` and `Release Date`.
- `FolderFileName`: the file inside the archive.
- `DISKOS Info Item Id`: the id in Diskos.

**Quirks.**
- Few reports are from after 2010, because reports are released only after a confidentiality period.
- Company names are historical. Statoil, Norsk Hydro, StatoilHydro and Equinor are the same lineage.
- Scanned reports have OCR errors.
- The layout of each JSON can only be described once the archive is unpacked. The Atlas rebuilds that part
  automatically when the download finishes.

**Good for.**
- Search and question answering over every well, with DISKOS-QA as the test.
- Extracting casing, cement and plugs for P&A and CO2 legacy-well screening (Barrier Ledger).
- Drilling hazards for offset wells (Spud Brief).
- Checking FactPages against the reports (Data Doctor).

### 3.2 Oil and gas text corpus (from the organisers)

**What it captures.** The text of public reports, page by page, made by OCR from scanned documents for FORCE's
2023 language-model hackathon (Zenodo 10775273). There are four sources plus a labelled sample:

| Source | Documents | Pages | Real text | Median characters per page |
|---|---|---|---|---|
| Norway, Diskos reports | 39,217 | 2,752,381 | 29 % | 493 |
| Norway, relinquishment reports | 599 (586 licences) | 11,368 | 64 % | 830 |
| UK, NSTA well reports | 1,631 (404 wellbores) | 89,764 | 37 % | 635 |
| Netherlands, NLOG reports | 2,717 | 75,266 | 42 % | 743 |
| Hand-labelled pages | | 1,368 | | |

**A record** is one page. Each has:
- `filename` and `page`;
- `content`, the OCR text;
- `possible_language` and `langdetect` (mostly English, with some Norwegian, `nb`);
- `content_could_be_natural_language`: True for real prose, False for **gibberish**, which is what OCR makes of
  log plots, tables, maps and stamps;
- `content_scrubbed_light`: the text with personal data lightly removed.

The UK file adds `wellbore` and `summary_tag`, the NSTA document type:
- `DRILL_EOWR`: end-of-well reports, 6,756 pages;
- `GEOL_CHEM`: geochemistry;
- `GEOL_GEOW`: well geology;
- `WELL_SUMMARY`;
- `CORE_GEN`: core reports;
- `GEOL_BIO`: biostratigraphy;
- `-DUPL`: duplicates.

**The hand-labelled pages** carry a code in `cat`. The file does not explain the codes. Reading the sample pages:

| Code | Meaning | Pages |
|---|---|---|
| `g` | geology, cuttings | 417 |
| `l` | lithology description | 283 |
| `b` | biostratigraphy | 175 |
| `d` | service company job report | 163 |
| `pp` | petrophysics | 141 |
| `dd` | drilling data sheet | |
| `r` | rig report, BHA | |
| `gc` | geochemistry | |
| `ref` | references | |

**The relinquishment reports** are a hidden gem. Each explains why a licence was given back: the prospect was dry,
too small, the seal failed, or the area was too far from infrastructure. By area: 283 North Sea, 197 Norwegian
Sea, 97 Barents Sea. Most ended between 2010 and 2023. Nine are still partly held, because only part of the area
was given back.

**Quirks.**
- Only 29 % of Diskos pages read as real text. Drop the rest, or treat them differently, before indexing.
- The Diskos text overlaps with the completion reports and is older OCR. Prefer the completion-report JSON where
  both exist.
- At 5.7 GB the Diskos file is too large to embed whole on a CPU. Index a filtered slice: the wells you care about
  plus distractors.

**Good for.**
- Search across Norwegian, UK and Dutch reports.
- A "why prospects fail" analysis by play and area from the relinquishment reports, which no one has published.
- A page classifier, using the labelled pages.
- Benchmarking OCR quality.

### 3.3 RealPore core data (from the organisers)

**What it captures.** Lab measurements on **core plugs**. A **core** is a cylinder of rock cut from the wellbore
and brought to the surface, the only direct sample of the reservoir. A **plug** is a small cylinder (2.5 to 3.8 cm)
drilled out of the core every 25 cm or so and measured in a lab. RealPore holds every porosity and permeability
measurement from the released Norwegian wells up to the end of 2018, with the geologist's rock description for
each plug. More than 600 wells existed only on paper and were typed in by hand. Sponsored by GeoProvider; any use
must credit them with a link (http://geoprovider.no/).

**A record** is one plug, with:
- the well and measured depth;
- **permeability**, in several flavours:
  - `ka`: measured with air;
  - `ke` / `kl`: Klinkenberg-corrected, an equivalent liquid permeability;
  - `kg`: gas;
  - nitrogen;
  - horizontal (along the bedding) and vertical (across it; usually lower);
- **porosity**, in several flavours (helium, fluid summation, horizontal and vertical plug), plus a "best of
  available";
- **saturations** (So oil, Sw water);
- **grain density**;
- the original description, with columns parsed from it: main lithology, grain size, rounding, cementation,
  sorting and structures.

**The numbers.**

| | |
|---|---|
| Plugs | 372,930 |
| Wellbores | 1,238 (1,235 found in FactPages, matched on NPDID) |
| Measurements | porosity on 323,463 plugs, permeability on 284,927 |
| Medians | porosity 17.6 %, permeability 14.1 mD |
| Deepest plug | 6,334 m |
| Rock types | sandstone 218,412, siltstone 12,093, limestone 6,913, claystone 4,829, chalk 2,321 |

**What the data shows.**
- **Porosity and permeability are linked:** permeability rises about tenfold for every few percent of porosity,
  with a wide scatter. That spread is why permeability is so hard to predict from logs.
- **Porosity falls with depth.** Sandstone medians are 25 % at 1,000 m, 21 % at 2,000 m, 20 % at 3,000 m, 14 % at
  4,000 m and 12 % at 5,000 m. This is the **compaction trend**: burial squeezes the grains and minerals cement
  the pores. It tells you what reservoir quality to expect at a target depth.
- **Chalk** can be very porous but tight. That is the Ekofisk-type reservoir.

**Quirks.**
- The well names in the file are spelt many ways; use the NPDID.
- Some values are impossible (porosity above 50 %, grain density above 3.5). The Atlas sets them to empty.
- The translation of rock descriptions into clean terms is incomplete, as the authors say.
- Units differ between columns.

**Good for.**
- Predicting permeability from logs. RealPore shares 76 wellbores with FORCE 2020, so a model can learn from the
  logs where core truth exists.
- Reservoir-quality maps by formation and depth.
- Finding analogue rocks for a new prospect.
- Checking porosity statements in reports.

### 3.4 FORCE 2020 well logs (from the organisers)

**What it captures.** **Well logs**: measurements recorded continuously down a wellbore by tools lowered on a
cable (**wireline**) or carried in the drill string (**LWD**, logging while drilling), one sample every 15 cm. Each
sample has a **lithology label** (the rock type) made by geoscientists (Explocrowd) for the 2020 FORCE
machine-learning competition. The challenge was to predict lithology from logs on wells the models never saw.

**The numbers.**
- Wells: 118 in the mail's LAS copy. Our CSV copy has 108: 98 training and 10 hidden test.
- Depth samples: 1,292,908, down to 5,437 m.
- Curves: 20.
- Lithology classes: 12.

**The curves** (the share of samples that have each is in brackets):

| Curve | Measures | Coverage | Reading it |
|---|---|---|---|
| GR, gamma ray | natural radioactivity (API) | 100 % | high = shale, low = sand or carbonate. The first log anyone looks at |
| RDEP, RMED, RSHA | resistivity, deep / medium / shallow (ohm·m) | 99 / 96 / 51 % | high in a porous rock = oil or gas (water conducts, hydrocarbons do not) |
| DTC | compressional sonic (µs/ft) | 93 % | slower = more porous or softer; ties logs to seismic |
| CALI | caliper, hole diameter (in) | 93 % | wider than the bit = caved hole, other logs unreliable there |
| RHOB | bulk density (g/cm³) | 87 % | lower = more porous, or gas |
| DRHO | density correction | 85 % | large = bad density reading |
| SP | spontaneous potential (mV) | 71 % | shifts in permeable beds |
| NPHI | neutron porosity (v/v) | 67 % | hydrogen content: high in shale, low in gas |
| PEF | photoelectric factor | 60 % | mineral: quartz ~1.8, dolomite ~3, calcite ~5 |
| BS | bit size (in) | 59 % | compare with CALI |
| ROP | rate of penetration (m/h) | 48 % | drilling speed |
| RXO, RMIC | flushed-zone and micro resistivity | 26 / 15 % | invasion of mud filtrate |
| MUDWEIGHT | mud density | 25 % | |
| DTS | shear sonic | 19 % | rock strength, fluid |
| SGR | spectral gamma ray | 6 % | |

**Lithology classes**, by number of samples:

| Class | Samples |
|---|---|
| Shale | 792,630 (61 %) |
| Sandstone | 182,982 |
| Sandstone/shale | 162,738 |
| Limestone | 64,694 |
| Marl | 37,725 |
| Tuff (volcanic ash) | 16,186 |
| Halite (salt) | 14,711 |
| Chalk | 13,418 |
| Coal | 4,064 |
| Dolomite | 1,975 |
| Anhydrite | 1,682 |
| Basement | 103 |

The rare classes are where models fail. The competition scored with a **penalty matrix**, where confusing shale
with sandstone costs less than calling salt sandstone. Scores are negative and closer to zero is better: the
winner had -0.47, and our Log Lens gets -0.513 (79.5 % accuracy) on the hidden wells.

**Stratigraphic groups** in the data, by samples:

| Group | Samples | What it is |
|---|---|---|
| Hordaland | 321,010 | Eocene-Oligocene mud |
| Shetland | 261,627 | Late Cretaceous chalk and marl |
| Viking | 149,414 | Late Jurassic, with the Draupne source rock |
| Rogaland | 144,887 | Paleocene, with the Balder tuff |
| Dunlin | 125,173 | Early Jurassic |
| Nordland | 117,836 | youngest, Miocene to recent |
| Cromer Knoll | 59,374 | Early Cretaceous |
| Båt | 38,421 | Norwegian Sea Jurassic |

The classic reservoirs sit in the **Brent** and **Viking** groups (Jurassic sandstones). Groups are made of
formations, and formations of members.

**Two plots every petrophysicist knows.**
- **Density against neutron** (RHOB against NPHI). Sandstone, limestone and dolomite fall on different lines,
  shale plots at high neutron, and gas pulls points toward low neutron and low density.
- **Gamma ray by rock type.** GR separates shale from clean rock, but not sandstone from limestone. That needs
  density and PEF.

**The mail's copy** adds the LAS files and four sheets from Sodir:
- casing depths for most wells;
- lithostratigraphy (groups, and formations with members) for all wells;
- the scoring matrix.

**Good for.**
- Lithology and porosity prediction.
- Log QC: bad hole, missing curves.
- Predicting missing curves, for example a synthetic shear sonic.
- Joining with RealPore for core-calibrated permeability.

### 3.5 Adele 3D seismic (from the organisers)

**What it captures.** A **3D seismic** survey: an image of the subsurface made from sound. A ship tows air guns
and kilometres of receivers. The sound echoes off each boundary between rock layers, where density and velocity
change, and processing stacks millions of echoes into a 3D cube. Adele is a survey from the Northwest Shelf of
Australia (Geoscience Australia, who must be credited), used in FORCE 2020's fault-detection competition, as a
**SEG-Y** file exported from Petrel in 2020.

**Geometry** (from the file's own headers):

| | |
|---|---|
| Traces | 822,031 |
| Inlines | 301 (numbered 4175 to 4775) |
| Crosslines | 2,731 (5670 to 8400) |
| Samples per trace | 1,001 at 4 ms |
| Record length | 4,004 ms TWT (the header stores time as negative values, -1,500 to -5,500) |
| Coordinates | GDA94 / MGA zone 51 |
| Size | 3.5 GB, floating-point amplitudes |

**Terms.**
- A **trace** is one vertical column: the echo at one surface position.
- An **inline** is a vertical slice along the shooting direction; a **crossline** is at right angles. A
  horizontal slice is a **time slice**.
- **Amplitude** is how strong the echo is; red and blue are positive and negative reflections. Bright spots can
  mean gas.
- **Faults** show as breaks and offsets in the layers.

**A SEG-Y file** has:
- a 3,200-character text header (who shot it, how it was processed, where the coordinates are; the Atlas shows
  it);
- a binary header;
- then trace after trace, each with its own header (inline, crossline, x, y).

**Quirks.**
- It is not from the NCS.
- It has no labels, so fault-detection results can only be judged by eye or against an interpreter.
- In the 2020 competition only 5 of 80 teams submitted a valid result.

**Good for.**
- Fault detection with pretrained models (FaultSeg3D).
- Practice at reading, QC and tiling SEG-Y.
- Attribute maps.

### 3.6 KSAT satellite radar (from the organisers, at the event)

**What it captures.** About 2.1 GB of **SAR** (synthetic aperture radar) images of the North Sea from KSAT
(Kongsberg Satellite Services), for spotting oil on the sea surface. The radar sees through cloud and at night.
Oil damps the small capillary waves, so a slick shows as a dark, smooth patch.
- A slick near a platform, pipeline or ship lane is likely a spill or a discharge.
- A slick far from any of them, or one that recurs in the same place, may be a **natural seep**: oil leaking from
  the seabed, a sign of an active petroleum system below.

The format is unknown until the event.

**Good for.**
- A seep finder: dark-spot detection on the images, then FactPages to check what lies under each slick (wells,
  facilities, fields).
- Linking to the DISKOS-QA passages about fluid-inclusion microseeps (Johan Castberg).
- Separating spills from seeps by their distance to infrastructure.

### 3.7 Sodir FactPages (found before the event)

**What it captures.** The official register of the shelf, kept by Sodir (the Norwegian Offshore Directorate) since
the first well in 1966. Everything public about every wellbore, field, discovery, licence, company and facility,
plus monthly production and the reserves estimates. 22 tables in `data/ncs.duckdb` (NLOD 2.0 licence).

**The numbers.**

| | |
|---|---|
| Wellbores | 2,201 exploration, 6,295 development (8,496 in all) |
| Fields | 142: 102 producing, 29 shut down, 11 approved for production |
| Discoveries | 650 |
| Licences | 1,813 |
| Facilities | 915 |
| Produced since 1971 | 9,106 MSm³ o.e. (about 57 billion barrels) |
| Remaining reserves | 2,208 MSm³ o.e. (2025 estimate) |
| Biggest remaining | Troll 576, Johan Sverdrup 201, Snøhvit 165, Johan Castberg 89, Snorre 68, Ormen Lange 60, Oseberg 55, Heidrun 53 (MSm³ o.e.) |

**What exploration wells found** (the `content` column):

| Content | Wellbores |
|---|---|
| Dry | 570 |
| Oil | 547 |
| Oil and gas | 339 |
| Gas | 173 |
| Gas and condensate | 173 |
| Shows only | 274 (all show types together) |

About one in three wildcats finds something, but most finds are small.

**Discoveries by status**: what happens to finds.

| Status | Discoveries | Recoverable, MSm³ o.e. |
|---|---|---|
| Included in another discovery | 223 | |
| Production unlikely | 185 | |
| Producing | 99 | |
| Production not evaluated | 49 | 124 |
| Likely but unclarified | 33 | 164 |
| In clarification | 27 | 211 |

The last three are the undeveloped resources the Tie-back Matchmaker ranks.

**The 22 tables:**

| Table | One row per | What is in it |
|---|---|---|
| `wellbore_exploration`, `wellbore_development` | wellbore | operator, purpose, dates, depths, water depth, KB, content, position, formation at TD |
| `wellbore_formation_top` | top | depth where each group, formation and member starts |
| `wellbore_casing_and_lot` | casing string | type, size, shoe depth, hole depth, leak-off test result |
| `wellbore_mud` | mud sample | mud weight, viscosity and type by depth |
| `wellbore_dst` | test | drill-stem test: interval, rates, pressures |
| `wellbore_core` | core | cored interval |
| `wellbore_history` | wellbore | the drilling history as text |
| `wellbore_document` | document | links to published reports |
| `field`, `field_description`, `field_reserves` | field | operator, status, fluid; text; reserves |
| `field_production_monthly` | field and month | oil, gas, NGL, condensate, water, since 1971 |
| `field_investment_yearly`, `field_operator_hst` | field and year | investment; operator history |
| `discovery`, `discovery_description`, `discovery_reserves` | discovery | status, fluid, text, resources |
| `licence` | licence | dates granted and valid to, area, status |
| `company` | company | |
| `facility_fixed` | facility | platforms and templates: position, start-up, function |
| `strat_litho_overview` | unit | the lithostratigraphic chart |

**Quirks.**
- `field_reserves` has one row per field **per year of estimate**. Always take the newest `fldVersion`; summing
  them all gives a wrong 66,750 MSm³ o.e.
- Produced water is reported only from 2000.
- The current year's production is incomplete.
- Leak-off values of 0 mean "not recorded".

**Good for.** Everything: it is the reference other data is joined to and checked against. NCS Copilot
(text-to-SQL), Field Pulse (decline), Tie-back Matchmaker and Spud Brief (offsets).

### 3.8 DISKOS-QA (found before the event)

**What it captures.** A **benchmark** for question answering over well reports. It has 1,027 questions, each with
a reference answer, written from 1,690 **passages** (chunks of a few paragraphs) of 817 Diskos well reports. Each
question is tied to the passage that answers it (`Chunk_IDs`) and to the wellbores, fields and formations it
names. In the set: 954 wellbores, 124 fields, 76 formations; the median passage is 1,577 characters. The event
promised "DiskosQA data"; this is the public copy (NLOD 2.0).

**Columns.**
- `Question`, `Answer` and `Content` (the passage).
- `Topic`:

  | Topic | Questions |
  |---|---|
  | Drilling | 190 |
  | Rock and core | 167 |
  | Test fluid and pressure | 151 |
  | VSP / well seismic | 119 |
  | Geology | 117 |
  | Petrophysics | 109 |
  | Well log | 90 |
  | Wellbore path | 84 |

- `Filter_type`, what the question narrows to: a well (428), a formation (342) or a field (257).
- `Evolutions`, how the question was made harder from a simple seed, a technique from synthetic-data generation:

  | Evolution | Questions | What it means |
  |---|---|---|
  | Concretizing | 304 | made more specific |
  | Comparative | 261 | compare two things |
  | Multi-context | 210 | needs more than one fact |
  | Reasoning | 192 | needs a step of inference |
  | Hypothetical | 60 | "what if" |

- `Entailed`: whether the answer really follows from the passage. 938 do; use only these for scoring.

**Quirks.**
- The answers are synthetic, generated by a language model, so a model of the same family may score well on style.
- Some questions do not match their passage (one asks about 15/9-F-15 and points to 15/9-F-1).
- About a third of passages are longer than 2,000 characters. Prompts must not cut them, which was a real bug here.

**Good for.** Measuring search and answering instead of guessing. This is the Diskos Detective scorecard (results
in section 5).

### 3.9 Volve daily drilling reports (found before the event)

**What it captures.** Every **daily drilling report** (DDR) from Equinor's Volve field in block 15/9. Volve
produced from 2008 to 2016, and in 2018 Equinor released all its data. A DDR is the rig's account of each 24
hours: every activity with start and end time, an activity code, the depth reached and a comment. The reports
were stored as WITSML, the drilling data XML standard; this is a Hugging Face copy, flattened.

**The numbers.**
- 1,759 reports, 1,758 with a valid date, from 1992-09 to 2018-01. The 1990s are the exploration wells (15/9-19 A
  and others); the field wells run from 2007 to 2016.
- 26 wellbores, 23,447 activities, 39,398 rig hours, deepest 5,331 m MD.

**Where the time went**, by activity class:

| Class | Hours |
|---|---|
| Drilling | 16,847 |
| Interruption | 8,343 |
| Plug and abandon | 4,277 |
| Completion | 4,136 |
| Workover | 3,336 |
| Formation evaluation | 1,988 |
| Moving | 470 |

The drilling class includes making hole (5,394 h) but also running casing (5,027 h) and tripping (2,348 h).
Interruption is the reported **NPT**: 21.7 % of all hours, of which 1,926 h was waiting on weather. The Lost Time
Hunter finds about 5 % more hidden in slow drilling.

**A record** in the activity list has:
- the start and end time;
- the measured depth;
- the activity code (`drilling -- drill`, `drilling -- trip`, `interruption -- waiting on weather` and so on);
- the state (ok or fail);
- a free-text comment, where the real story is: *"Drilled 8 1/2" hole from 4464 m to 4562 m with 2350 lpm ... ECD
  1.44 - 1.45 sg. Average ROP 11.6 m/hr. Occasionally drilled with reduced RPM due to hard stringers."*

**The drilling curve** plots depth against days. Steep stretches are fast drilling; flat steps are trips, casing
runs and problems. Comparing these curves between wells is how drilling performance is judged.

**Quirks.**
- It is one field. A few reports carry a placeholder date (1979).
- Equinor's Volve licence is its own; the Hugging Face copy says CC BY 4.0.
- The codes are coarse, so problems hide in the comments.

**Good for.**
- Lost-time analytics.
- Lessons learned with citations.
- Benchmarking drilling curves.

### 3.10 F3 seismic (found before the event)

**What it captures.** A 3D seismic cube from block F3 in the Dutch North Sea, with every sample labelled by rock
unit (**facies**) by Alaudah and others (2019). It has become the standard benchmark for teaching models to read
seismic. The shape is 401 inlines by 701 traces by 255 samples.

**The six labels**, from top (young) to bottom (old):

| Label | Rock | Age |
|---|---|---|
| Upper North Sea group | sands and clays | Neogene |
| Middle North Sea group | clays | Paleogene |
| Lower North Sea group | clays and sands | Paleogene, the biggest unit |
| Rijnland / Chalk | marl and chalk | Cretaceous |
| Scruff | shale and sand | Late Jurassic |
| Zechstein | salt | Permian; salt flows and builds domes that make traps |

**Good for.** Facies classification with known answers. The Seismic Lookalike scores 76 % (texture) and 78 %
(learned) right facies in the top 10 similar patches, against 42 % by chance.

---

## 4. How the datasets connect

Nearly everything is about wellbores, so the **wellbore name** (normalised) joins the datasets, with FactPages as
the register every name is checked against.

| Dataset | Wellbores | Found in FactPages |
|---|---|---|
| FactPages | 8,496 | (the register) |
| Completion reports | 4,441 | 3,960 |
| RealPore | 1,239 | 1,235 |
| DISKOS-QA | 954 | 861 |
| FORCE 2020 logs | 108 | 106 |
| Volve DDRs | 26 | 23 |

Wellbores shared by two datasets, which is where joined apps become possible:

| | Completion | RealPore | DISKOS-QA | FORCE logs | Volve |
|---|---|---|---|---|---|
| **Completion** | 4,441 | 1,005 | 786 | 96 | 24 |
| **RealPore** | | 1,239 | 387 | 76 | 2 |
| **DISKOS-QA** | | | 954 | 45 | 15 |
| **FORCE logs** | | | | 108 | 0 |

The overlaps that matter:
- **Completion reports and DISKOS-QA (786):** the benchmark can test search over the full reports, not only over
  its own passages.
- **Completion reports and RealPore (1,005):** reported porosity can be checked against the lab.
- **FORCE logs and RealPore (76):** logs with core truth, to calibrate permeability.

Of the 4,799 wellbores named outside FactPages, 3,263 are in one dataset, 1,137 in two, 365 in three and 34 in
four (such as 35/4-1, 34/8-3, 16/10-1, 25/9-1 and 15/9-15). The Atlas
well lookup shows one of them through all its data on a single page.

The seismic does not join by name: F3 and Adele are not on the NCS. On the NCS, seismic would join to wells by
position and a time-depth tie.

---

## 5. Findings

### From measuring (this repo)

- **Search over reports works when it respects names.** On the 938 supported DISKOS-QA questions, plain
  embedding search finds the right passage in the top 5 for 75.6 % (MRR 0.615). Adding keyword search (BM25) lifts
  that to 88.3 %, and filtering to the wellbore, field or formation named in the question to 92.5 % (MRR 0.838).
  Embeddings blur exact strings like "15/9-F-12"; keywords and filters do not.
- **The model knows almost nothing about specific wells.** With qwen3.6-35b on a 40-question sample:

  | Mode | Correct |
  |---|---|
  | Closed book (no search) | 5 % |
  | One-shot vector search | 45 % |
  | One-shot filtered search | 55 % |
  | The agent (searches again and checks FactPages) | 67.5 % |

  Grounding is not optional. A bug was found on the way: passages were cut at 2,000 characters in the prompt, and
  the prompt told the model to refuse when unsure. Fixing both raised one-shot answers from 35 to 45 % (vector)
  and from 40 to 55 % (filtered).
- **Lithology from logs:** 79.5 % accuracy and a competition score of -0.513 on 10 unseen wells (the 2020 winner:
  -0.47).
- **Seismic look-alikes:** 76 % (texture) and 78 % (learned metric) right facies among the 10 most similar patches,
  against 42 % chance.
- **Lost time at Volve:** 21.7 % of rig hours are reported NPT, and about 5 % more is invisible, in drilling
  slower than the 75th-percentile rate for the depth.
- **Data consistency:** only 24 of 108 FORCE 2020 wells agree fully with FactPages on position, depth reference
  and formation tops.
- **Tie-backs:** 92 undeveloped discoveries with 499 MSm³ o.e. are within reach of producing hosts.

### From the data itself

- **Reserves are concentrated.** Troll alone holds a quarter of what is left; the top 8 fields hold over half.
- **Oil peaked around 2000; gas took over.** Shelf output is still about 240 MSm³ o.e. a year. Produced water
  (174 MSm³ in 2025) now exceeds oil (107 MSm³) by volume.
- **Exploration** peaked in the mid 1980s, around 2008 to 2014, and again in the 2020s. About a third of wildcats
  find something.
- **Most scanned pages are not text.** In the Diskos OCR corpus, 71 % of pages are flagged as not natural language.
  The completion-report JSON, with its layout and table models, is the better source.
- **Porosity falls predictably with depth** in sandstone, from about 25 % at 1 km to 12 % at 5 km. Below about 4 km
  most sandstones are no longer good reservoirs unless something preserved them.
- **Shale is 61 % of the logged rock.** The interesting rocks (sand, carbonate) are the minority, and the rarest
  classes (coal, anhydrite, basement) are where models fail.

### From the research (sources in `docs/reports/`)

- Frontier general models already know textbook geology (99.8 % on FormationEval). The open problem is grounding:
  finding and citing the facts of a particular well.
- No public hours-saved figure exists for a subsurface document assistant. A measured minutes-per-dossier against a
  manual baseline would be a new number.
- Three published CO2 legacy-well screening schemes classify the same wells differently, and no machine-readable
  P&A records database exists. The completion reports could become one.

---

## 6. Glossary

Grouped by subject; the Data Atlas has the same terms with hover definitions.

### The shelf and the business

- **NCS**: Norwegian Continental Shelf: the North Sea, Norwegian Sea and Barents Sea.
- **Sodir**: the Norwegian Offshore Directorate, the state agency that collects and publishes shelf data. Formerly
  the **NPD**.
- **Havtil**: the Norwegian Ocean Industry Authority, the safety regulator (formerly the PSA).
- **Diskos**: the national data bank for the shelf (reports, logs, seismic), run by Sodir and the companies. Data
  becomes public after a confidentiality period.
- **FORCE**: Sodir's forum for industry cooperation on subsurface technology; it runs the hackathons.
- **Licence (PL)**: the permit to explore and produce in an area, held by a group of companies.
- **Operator**: the company that does the work for the licence partners.
- **Relinquishment**: giving a licence, or part of it, back to the state.
- **Discovery**: oil or gas proven by a well.
- **Field**: a discovery approved for production.
- **PDO**: plan for development and operation, approved by the state before a field is built.
- **Facility**: a platform, subsea template, FPSO (floating production ship) or other installation.
- **Tie-back**: producing a small discovery through an existing host platform via pipelines and a subsea template.
- **Host**: the platform a tie-back connects to. Its spare capacity is **ullage**.
- **Reserves**: what the companies plan to produce. **Recoverable** is the total producible, **remaining** what is
  left.
- **Resources**: oil and gas in discoveries not yet approved for production.
- **Plateau and decline**: a field's rate holds at a peak (plateau) and then falls (decline).
- **Arps decline**: the standard curve for falling production (exponential to hyperbolic).
- **Produced water**: formation water that comes up with oil; it rises as a field ages.
- **NGL**: natural gas liquids (ethane, propane, butane) taken out of the gas.
- **Condensate**: light liquid that drops out of gas as pressure falls.
- **o.e.**: oil equivalents, one number for all products (1,000 Sm³ gas = 1 Sm³ o.e.).
- **Sm³**: standard cubic metre (15 °C, 1 atm). 1 Sm³ oil = 6.29 barrels.
- **CCS**: carbon capture and storage. On the NCS: Northern Lights, Smeaheia.
- **Legacy well**: an old well near a CO2 store that must not leak.

### Rocks and geology

- **Lithology**: rock type.
- **Sandstone**: sand grains cemented together; the usual reservoir.
- **Siltstone**: finer than sand.
- **Shale, claystone, mudstone**: fine clay rock. Low permeability, so it acts as a seal or as source rock.
- **Limestone**: calcium carbonate. **Chalk** is a fine, often porous limestone (Ekofisk). **Dolomite** is a
  magnesium carbonate. **Marl** is clay mixed with carbonate.
- **Halite, anhydrite**: salt and gypsum-like rocks (evaporites). Salt flows and shapes traps.
- **Tuff**: volcanic ash turned to rock (the Balder Formation).
- **Coal**: plant matter turned to rock.
- **Basement**: old crystalline rock below the sediments.
- **Breccia**: angular broken rock, cemented.
- **Conglomerate**: rounded pebbles, cemented.
- **Source rock**: organic-rich rock that generated oil and gas (Draupne / Kimmeridge shale).
- **Reservoir**: porous, permeable rock that holds oil or gas.
- **Seal / cap rock**: tight rock above a reservoir.
- **Trap**: the shape that holds oil and gas under a seal (dome, tilted fault block, salt flank).
- **Play**: a family of prospects sharing source, reservoir and seal (for example the Jurassic Brent play).
- **Prospect**: a mapped trap not yet drilled.
- **Wildcat**: the first well into a prospect.
- **Fault**: a fracture where blocks have moved; it makes traps and can leak.
- **Formation**: a named rock layer of one character (Draupne, Sleipner, Hugin, Utsira). **Group** is a set of
  formations (Viking, Brent, Nordland). **Member** is a part of a formation.
- **Formation top**: the depth where a formation starts in a wellbore.
- **Lithostratigraphy**: naming rock units by rock type. **Biostratigraphy**: dating rock by its microfossils.
- **Palynology**: the study of fossil pollen and spores, one tool of biostratigraphy.
- **Facies**: a body of rock with one character and origin (for example channel sand). On seismic, a region with
  one texture.
- **Compaction trend**: porosity falls with burial depth.
- **Diagenesis**: the changes after burial (cementation, dissolution) that alter porosity.
- **Seep**: oil or gas leaking naturally to the seabed. **Microseep** is the trace version, seen in fluid
  inclusions (**FIS**, fluid inclusion stratigraphy).

### Rock properties and cores

- **Porosity**: the pore share of the rock, in %.
- **Permeability**: how easily fluid flows through the rock, in mD. **Horizontal** is along the bedding, usually
  higher; **vertical** is across it.
- **Darcy, millidarcy (mD)**: the units of permeability. 1 D = 1,000 mD.
- **Klinkenberg correction**: converts gas or air permeability to an equivalent liquid permeability (gas slips
  through small pores, so it reads high).
- **ka, ke, kg, kl**: permeability measured with air, Klinkenberg-corrected, measured with gas, and
  liquid-equivalent.
- **Helium porosity**: porosity measured by helium injection, the lab standard.
- **Saturation (Sw, So, Sg)**: the share of the pores filled with water, oil or gas.
- **Grain density**: the density of the mineral grains alone (quartz 2.65 g/cm³).
- **Core**: a rock cylinder cut from the wellbore. **Sidewall core**: a small sample shot from the borehole wall.
- **Core plug**: a small cylinder drilled from a core for lab tests.
- **Cuttings**: rock chips from the bit, carried up by the mud. **Ditch cuttings** are those collected at the
  shakers.
- **Shows**: traces of oil or gas in cuttings, cores or gas readings.
- **Grain size**: from clay through silt and very fine, fine, medium and coarse sand to gravel. **Sorting**: how
  uniform the grains are. **Rounding**: how rounded they are. **Cementation**: how strongly the grains are bound.

### Wells and drilling

- **Wellbore, well**: one hole, and the surface location that may hold several holes.
- **Exploration, appraisal, development well**: a well that finds, measures, or produces (or injects).
- **Producer, injector, observation well**: development well types.
- **Sidetrack**: a new wellbore out of an existing one. **Technical sidetrack (T, ST)**: one drilled around a
  problem.
- **Spud**: the start of drilling. **TD**: total depth reached.
- **MD, TVD, RKB, KB**: measured depth, true vertical depth, and the rig-floor depth reference.
- **Deviated, horizontal well**: one not straight down, or one along the reservoir.
- **Drill string, bit, BHA**: the pipe; the cutting tool; the bottom-hole assembly (bit, motor, stabilisers,
  measurement tools).
- **ROP**: rate of penetration, in m/h.
- **WOB, RPM**: weight on bit and rotation speed.
- **Trip**: pulling the string out and running it back.
- **Casing**: steel pipe cemented in the hole in steps (30", 20", 13 3/8", 9 5/8", 7" liner). The **shoe** is its
  bottom. A **conductor** is the first, widest string.
- **Liner**: casing hung inside the last string instead of reaching the surface.
- **Cement**: pumped behind casing to seal it in. **TOC** is the top of cement.
- **Mud**: drilling fluid. Its weight (g/cm³, sg) holds back formation pressure. **ECD** (equivalent circulating
  density) is its effective weight while pumping.
- **Pore pressure**: the pressure of fluid in the rock. **Overpressure**: higher than a column of water would give.
- **Fracture pressure**: the pressure at which the rock cracks.
- **LOT / FIT**: leak-off test and formation integrity test below a casing shoe. They give the strongest mud the
  hole can hold.
- **Drilling window**: the mud weights between pore pressure and fracture pressure.
- **Kick**: formation fluid entering the well. **Blowout**: an uncontrolled kick.
- **Losses**: mud flowing into the rock.
- **BOP**: blowout preventer, the valves on top of the well.
- **Stuck pipe, fishing, washout, tight hole, pack-off, cavings**: common problems. Pipe that cannot move;
  recovering lost equipment; an enlarged hole; a narrow hole; cuttings blocking the annulus; rock falling from the
  wall.
- **Shallow gas, shallow water flow**: hazards in the top hole.
- **HPHT**: high pressure and temperature (above about 690 bar or 150 °C).
- **NPT**: non-productive time, rig time with no progress. **ILT** (invisible lost time): time lost inside normal
  operations, measured against a benchmark.
- **DDR**: daily drilling report. **WITSML**: the XML standard for drilling data.
- **Completion**: equipping a well to produce (tubing, packers, perforations). **Perforate**: shoot holes through
  the casing into the reservoir.
- **Workover**: later intervention on a producing well.
- **Wireline**: tools run on a cable (logging, setting plugs).
- **Plug and abandon (P&A)**: sealing a well permanently with cement plugs. **TA**: temporary abandonment.
- **Barrier**: an element that stops flow (a cement plug, casing, the cap rock). NORSOK **D-010** is the standard.
- **Final well report / completion report / EOWR**: the document written after the well is finished.

### Logs and petrophysics

- **Well log**: a measurement recorded continuously down the hole. **LWD/MWD**: logging or measuring while drilling.
- **LAS**: the plain-text log file format.
- **GR**: gamma ray. **SGR**: spectral gamma ray.
- **RHOB**: bulk density. **DRHO**: its correction.
- **NPHI**: neutron porosity.
- **RDEP, RMED, RSHA, RXO, RMIC**: resistivity at different depths of investigation.
- **DTC, DTS**: compressional and shear sonic.
- **PEF**: photoelectric factor.
- **CALI, BS, DCAL**: caliper, bit size, and the caliper minus the bit size.
- **SP**: spontaneous potential.
- **Petrophysics**: turning logs into porosity, saturation and permeability.
- **Archie equation**: links resistivity and porosity to water saturation.
- **Crossplot**: one log against another. Density-neutron is the classic.
- **Net pay**: the thickness of rock that would produce.
- **Penalty matrix**: the FORCE 2020 score, where some lithology confusions cost more than others.

### Tests and fluids

- **DST**: drill-stem test, flowing a zone to measure rate, pressure and fluid.
- **MDT / RFT**: wireline pressure and fluid sampling tools.
- **PVT**: the pressure-volume-temperature behaviour of the reservoir fluid.
- **GOR**: gas-oil ratio.
- **API gravity**: oil density on a scale where higher means lighter.
- **Water cut**: the water share of the produced liquid.

### Seismic

- **Seismic, 2D, 3D**: a sound image of the subsurface, as lines or as a cube.
- **Survey**: one acquisition campaign.
- **Trace**: one vertical column of the image.
- **Inline, crossline**: the two horizontal directions of the grid.
- **Time slice**: a horizontal slice.
- **TWT**: two-way time, in ms.
- **Amplitude**: echo strength. A **bright spot** is a strong amplitude, often gas. **Reflector**: a boundary that
  echoes.
- **Horizon**: a picked reflector surface. **Interpretation**: picking horizons and faults.
- **SEG-Y**: the seismic file format.
- **Attribute**: a number computed from the seismic (coherence, envelope).
- **VSP**: vertical seismic profile, seismic recorded in the wellbore to tie depth to time.
- **Well tie**: matching a well's logs to the seismic.
- **SAR**: synthetic aperture radar from satellites. Not seismic, but sea-surface images where slicks look dark.

### Data and AI terms used here

- **OCR**: optical character recognition, reading text from scans. **Gibberish page**: OCR output that is not
  language (plots, tables, maps).
- **Document layout model**: finds the text blocks, tables and figures on a page.
- **VLM**: vision-language model, a language model that also reads images.
- **Passage / chunk**: a few paragraphs returned by search.
- **Embedding**: a vector that captures meaning, for similarity search. **bge-m3**: the embedding model used here.
- **BM25**: keyword search scoring.
- **Hybrid search**: keyword and embedding search combined (here by **RRF**, reciprocal rank fusion).
- **RAG**: retrieval-augmented generation, finding passages and answering from them with citations.
- **Agent**: a model that calls tools (search, database) in a loop until it can answer.
- **Text-to-SQL**: a model writing database queries from plain questions.
- **Recall@5**: how often the right passage is in the top 5. **MRR**: mean reciprocal rank, rewarding the right
  passage near the top.
- **Entailed / supported**: the answer follows from the passage.
- **Closed book**: answering without search, from the model's memory.
- **LLM judge**: a model grading answers against a reference.
- **Benchmark**: a test set with known answers.
- **Facies classification**: labelling rock units on seismic or logs.
- **Quantisation (IQ3, Q4, Q8)**: storing model weights with fewer bits so a model fits on a GPU.
