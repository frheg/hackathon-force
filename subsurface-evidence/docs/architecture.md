# Architecture: data, links, methods, results

How every source becomes part of the NCS earth model, and what came out (numbers measured, LOG ids in brackets). Four regions, each fitted and tested on its own wells: pilot (Horda Platform / northern Viking Graben), North Sea south, Norwegian Sea, Barents Sea (L074).

## 1. Data sources and how they connect

```mermaid
flowchart LR
  subgraph SRC["Data sources (what it is: what it holds)"]
    FP["Sodir FactPages<br/>national register:<br/>8,496 wellbores, 41,537 formation tops,<br/>1,187 DST, 36,761 mud weights,<br/>8,758 casing + LOT, 8,544 cores"]
    F20["FORCE 2020 logs<br/>competition wells: 98 wells,<br/>GR RHOB NPHI PEF DTC RDEP,<br/>X Y Z per sample, expert lithology"]
    RP["RealPore<br/>lab core plugs:<br/>porosity, permeability"]
    REP["Completion reports<br/>4,462 PDFs, 648,520 OCR pages:<br/>rock descriptions, shows, tests"]
    DQA["DISKOS-QA<br/>1,027 questions over<br/>1,690 report passages"]
    SM["Smeaheia (Equinor, Gassnova)<br/>3D seismic GN1101 + TNE01,<br/>horizons, well picks, velocity maps"]
    SL["Sleipner 4D (Equinor)<br/>12 seismic vintages 1994-2010"]
    FM["Sodir FactMaps<br/>2,680 mapped faults,<br/>263 structural elements"]
    WOA["NOAA World Ocean Atlas 2023<br/>bottom-water temperature"]
    NIST["NIST CO2 density<br/>(Span-Wagner), 0-200 C, 1-80 MPa"]
    ATL["Sodir CO2 Storage Atlas<br/>evaluated aquifers (check only)"]
  end
  subgraph KEY["Join keys (how and why)"]
    K1["wellbore name, normalised<br/>+ NPDID where both have it"]
    K2["measured depth (MD)<br/>along the well"]
    K3["position: ED50 lat/lon,<br/>UTM 31N, EPSG:3035 km"]
    K4["formation / group name<br/>(lithostratigraphy)"]
  end
  FP --> K1 & K2 & K3 & K4
  F20 --> K1 & K2 & K3
  RP --> K1 & K2
  REP --> K1 & K2
  DQA --> K1
  SM --> K3
  SL --> K3
  FM --> K3
  WOA --> K3
  K1 --> J["one wellbore identity<br/>across all sources"]
  K2 --> J2["one depth axis per well<br/>(MD, then TVDSS)"]
  K3 --> J3["one map frame"]
  K4 --> J4["one stratigraphic column"]
```

| Link | Why | How | Checked |
|---|---|---|---|
| Wellbore name | Every table names wells differently | One normaliser (`se/ingest/names.py`); NPDID where present | RealPore by NPDID and name (L051) |
| MD | Logs, cores, picks, tests and report lines all carry MD | Rows fall into a well x formation interval by MD | Feet vs metres guard by total depth (L008) |
| Position | Neighbours, maps, seismic | ED50 throughout; FORCE X/Y = ED50 UTM 31N | 6 m median vs FactPages wellheads (L055) |
| Formation name | Same unit across wells | FactPages lexicon: level and parent group | 99.89 percent of group pairs agree on order (L056) |

## 2. Methods and what they yield

```mermaid
flowchart TB
  subgraph FRAME["P1 Frame: true positions"]
    T1["Trajectories<br/>FORCE X/Y/Z exact;<br/>else constant inclination from TVD at TD;<br/>kick-off point for development wells"]
    T2["Tops in TVDSS<br/>TVDSS = TVD below rig floor - KB"]
    T3["No TVD in FactPages (1,032 wellbores):<br/>sidetrack = parent TVD - 58 m;<br/>else MD x TVD/MD of its class (L076)"]
  end
  subgraph STRUCT["P2 Structure"]
    C["Column<br/>Copeland order of units<br/>from depth order in wells"]
    S["Surfaces<br/>model choice per horizon by blocked CV:<br/>constant, linear trend, GP (Matern 3/2),<br/>ML-kriging hybrid, deep-kernel GP (cuda)"]
    FR["Formations<br/>fraction of their group interval<br/>+ presence (indicator kriging)"]
    G["Stratigraphic grid<br/>2 km columns, ~10 m layers"]
  end
  subgraph PROP["P3 Properties"]
    L["Lithology: FORCE labels + tree classifier"]
    PP["Porosity, permeability: tree on logs (L046)<br/>+ compaction trend + kriged residual"]
    PR["Pressure: DST, mud weight, LOT"]
    TE["Temperature: DST; seabed from WOA;<br/>salt term (North Sea south)"]
    FL["Fluids: DST flow, well content, shows"]
  end
  subgraph PSYS["P9-P10 Petroleum system"]
    MA["Source maturity: T of Draupne, Spekk,<br/>Hekkingen ... ; at maximum burial too"]
    BU["Burial: net exhumation from porosity<br/>(Barents median 1.7 km)"]
    MI["Fill-and-spill migration<br/>along each unit top"]
    TR["Traps: closures, faults,<br/>structural highs"]
  end
  subgraph EVID["Evidence and targets"]
    R["Rules with sources, tested on data<br/>(knowledge base, 17 rules)"]
    X["Report facts<br/>local LLM: precision 0.03-0.17, not used (L072)"]
    SEL["Feature selection nested in the folds;<br/>families: logistic, spline, boosting"]
    MC["Monte Carlo: correlated fields,<br/>beta draws for rates"]
    TG["Targets: probability + support per cell;<br/>published only if it beats the unit rate<br/>and holds forward in time"]
    CO["Composites: CO2 storage, chance of success,<br/>CO2 capacity (Mt, NIST density)"]
  end
  T1 --> T2 --> C --> S --> FR --> G
  T3 --> T2
  G --> L & PP & PR & TE & FL
  PP --> BU --> MA
  TE --> MA --> MI
  G --> TR & MI
  L & PP & PR & TE & FL & R & MA & MI & TR --> SEL --> MC --> TG --> CO
  TG & CO --> UI["Subsurface model page: cells, strata, wells at TVDSS,<br/>what wells found, seismic, map layers;<br/>click = evidence chain"]
  TG & CO --> EX["Export: IRAP, ZMAP+, GRDECL<br/>(Petrel, RMS)"]
  TG & R --> AS["Strata Desk assistant:<br/>reports + FactPages + the model's<br/>numbers, tests and rules"]
```

## 3. Results so far, and what explains them

| Step | Input | Result | Why it came out this way |
|---|---|---|---|
| Frame (L055) | 87 FORCE wells with true paths vs FactPages-only | median depth error 0.42 m per well; 90 % intervals hold 92-94 % on held-out wells | Most exploration wells are near-vertical; the few deviated ones dominate the RMSE (p90 60-80 m) |
| Tops (L055) | 14,276 pilot tops | all converted; 642 wells pass the seabed check, 19 flagged | Datums agree: MD + Z = KB (median 0.0 m) |
| Column (L056) | 9,754 formation + 4,522 group tops | 12 groups in order, 55 horizons modelled | Viking formations interfinger (94.6 % pairwise agreement), so their order is decided per column |
| Shallow surfaces (L056) | ~450 wells per horizon | seabed 27 m, Rogaland 187 m, Shetland 210 m held-out error; beat trend by 25-58 % | Cenozoic layers are laterally continuous: correlation lengths 32-35 km |
| Deep surfaces (L056) | ~300-400 wells per horizon | Brent and deeper: no spatial skill; constant mean wins (~710-760 m) | Jurassic fault blocks: correlation lengths 6-15 km, depth 2 km on the platform vs 4-5 km in the graben. Wells 20+ km away cannot resolve it; seismic would |
| Hybrids (L057) | covariates from shallower surfaces | deep-kernel GP adopted for Cromer Knoll (424 vs 615 m); ML-kriging never wins | Non-stationary kernel follows the Cretaceous structure; boosted trees overfit with ~400 wells |
| Formations (L056) | fraction of group interval | beats direct fits for most (Heather 383 vs 710 m) | A formation cannot leave its group; fractions vary less than depths |

| Regions (L074) | the same pipeline per region | hydrocarbons gain 0.29-0.42, sandy delta 0.60-0.97 | Each region only on its own wells; clays have no skill anywhere |
| Factors (L075) | maturity, faults, highs, closures, salt, seabed | used only where they beat the model without them; every one also helps forward in time | Where wells are dense, neighbouring wells already carry the information |
| Honest skill (L076) | nested selection, forward-in-time test | overpressure fails forward in time in three regions and is no longer published as a model | Later wells are deeper, high-pressure targets |
| Monte Carlo fix (L076) | beta draws for rates | rare targets no longer pulled towards 0.5 (Barents hydrocarbon median 0.30 to 0.17, base rate 0.18) | Normal noise on the logit is far too wide for rare events |
| Model families (L076) | logistic, spline, boosting | boosting loses everywhere; splines win in a few region-targets | A few hundred wells per target: smooth, simple models generalise |
| Chance of success (L076) | reservoir x seal x charge x trap | no held-out skill against hydrocarbons in any region | Wells are drilled on prospects already risked for these elements; shown as an explanation, not a prediction |
| CO2 capacity (L076) | volume x NTG x porosity x NIST density x efficiency | Gt-scale per aquifer, as the atlas; our CO2 density lower for shallow Utsira (gas-like below 7.4 MPa) | Our pilot Utsira lies shallower (median top 578 m) than the atlas average (1,000 m) |

Every number has a LOG entry with its command; artefacts carry manifests (`data/subsurface-evidence/earth/pilot/*.manifest.json`).
