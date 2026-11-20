# Architecture: data, links, methods, results

How every source becomes part of the NCS earth model, and what came out (numbers measured, LOG ids in brackets). Pilot = Horda Platform / northern Viking Graben.

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
    TE["Temperature: DST"]
    FL["Fluids: DST flow, well content, shows"]
  end
  subgraph EVID["Evidence and targets"]
    R["Rules with sources, tested on data<br/>(knowledge base)"]
    X["Report facts<br/>local LLM on the GPU, page + quote"]
    MC["Monte Carlo realisations (GPU)<br/>of surfaces and properties"]
    TG["Targets: probability + support per cell<br/>calibrated on held-out wells"]
  end
  T1 --> T2 --> C --> S --> FR --> G
  G --> L & PP & PR & TE & FL
  L & PP & PR & TE & FL & R & X --> MC --> TG
  TG --> UI["3D view: isosurfaces,<br/>opacity = support,<br/>click = evidence chain"]
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

Every number has a LOG entry with its command; artefacts carry manifests (`data/subsurface-evidence/earth/pilot/*.manifest.json`).
