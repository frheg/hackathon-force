"""Data Atlas: a dashboard over every dataset, to learn what is in each, what the words mean and how they connect.

    uv run python -m sketches.atlas [factpages logs diskosqa volve realpore text completion seismic links]

profiles each dataset into data/atlas/<name>.json (counts, distributions, samples), which the page reads. Profiles
are numbers and short samples only, so the page stays fast however large the source is. The well lookup reads the
sources live, joined on the wellbore name.
"""

import base64
import json
import re
import sys
import tarfile
import time
from collections import Counter
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from common import DATA_DIR, load_json, norm, page, rows, save_json, wellbore

router = APIRouter(prefix="/atlas")
OUT = DATA_DIR / "atlas"
OFFICIAL = DATA_DIR / "official"  # the datasets the organisers sent; the rest were found before the event
REALPORE_XLSX = OFFICIAL / "realpore" / "RealPore Por Perm Lithology data 1240 Wells Norway public_v2.0.xlsx"
REALPORE = OFFICIAL / "realpore" / "realpore.parquet"
TEXT = OFFICIAL / "text"
COMPLETION = OFFICIAL / "completion_reports"
COMPLETION_META = COMPLETION / "Diskos metatadata for 4462 public end of well reports from the Norwegian continental shelf .csv"
LOGS = OUT / "logs.parquet"
ADELE = OFFICIAL / "adele" / "Adele_seismic_survey_NW australia_bind cube_fault_detection.segy"
TEXT_SOURCES = {
    "relinquishment": "Norway - Norwegian Petroleum Directorate relinquishment reports.csv",
    "diskos": "Norway - Diskos reports.csv",
    "uk": "UK - North Sea Transition Authority NDR reports.csv",
    "nl": "Netherlands - Netherlands Oil & Gas Portal reports.csv",
}
# the datasets, in the order the page lists them. origin "mail": sent by the organisers (data/official/), the most
# official source; "earlier": found before the event. "path" must exist for it to count as downloaded, "profile" is
# the data/atlas/<profile>.json that describes it.
CATALOG = [
    {"id": "completion", "origin": "mail", "name": "Completion reports", "path": "official/completion_reports",
     "profile": "completion", "licence": "CC BY 4.0", "source": "https://doi.org/10.5281/zenodo.24320092",
     "what": "The final well report of 4,462 NCS wellbores, as the original PDF and as structured JSON (pages, "
     "tables, figures described by models). Published for the event on 17 November 2026."},
    {"id": "text", "origin": "mail", "name": "Oil and gas text corpus", "path": "official/text", "profile": "text",
     "licence": "CC BY 4.0", "source": "https://zenodo.org/records/10775273", "what": "Text read (OCR) from public "
     "reports: Norwegian Diskos and relinquishment reports, UK and Dutch well reports, page by page, flagged as "
     "text or gibberish. Made for FORCE's 2023 language model hackathon."},
    {"id": "realpore", "origin": "mail", "name": "RealPore core data", "path": "official/realpore",
     "profile": "realpore", "licence": "CC BY 4.0, credit GeoProvider (http://geoprovider.no/)",
     "source": "https://zenodo.org/records/4723018", "what": "Porosity and permeability measured on rock plugs "
     "cut from cores in 1,240 Norwegian wells, with a rock description for each plug."},
    {"id": "logs", "origin": "mail", "name": "FORCE 2020 well logs", "path": "official/force2020", "profile": "logs",
     "licence": "CC BY 4.0", "source": "https://zenodo.org/records/4351156", "what": "Depth-by-depth measurements "
     "down 118 wells (gamma ray, density, resistivity and more), with a lithology label at every depth set by "
     "geoscientists. The mail's copy is LAS files; the same wells as CSV (data/force2020) feed the charts."},
    {"id": "adele", "origin": "mail", "name": "Adele 3D seismic", "path": "official/adele", "profile": "seismic",
     "licence": "CC BY 4.0, credit Geoscience Australia", "source": "https://zenodo.org/records/4299758",
     "what": "A 3D seismic survey from NW Australia in SEG-Y, the cube of FORCE 2020's fault-finding competition."},
    {"id": "ksat", "origin": "mail", "name": "KSAT satellite radar", "path": "official/ksat", "profile": None,
     "licence": "event data", "source": "", "what": "2.1 GB of satellite radar (SAR) over the North Sea for "
     "spotting oil slicks and seeps. Handed out at the event; put it in data/official/ksat."},
    {"id": "factpages", "origin": "earlier", "name": "Sodir FactPages", "path": "ncs.duckdb", "profile": "factpages",
     "licence": "NLOD 2.0", "source": "https://factpages.sodir.no", "what": "The official register of the shelf: "
     "every wellbore, field, discovery, licence and facility, with monthly production and reserves. 22 tables."},
    {"id": "diskosqa", "origin": "earlier", "name": "DISKOS-QA", "path": "diskosqa/diskos_qa.csv",
     "profile": "diskosqa", "licence": "NLOD 2.0", "source": "https://github.com/georgeghon/DISKOS-QA",
     "what": "1,027 questions with reference answers, each tied to the passages of Diskos well reports that answer "
     "it. A test for search and question answering. The event promised DiskosQA; this is the public copy."},
    {"id": "volve", "origin": "earlier", "name": "Volve daily drilling reports", "path": "volve/ddr.parquet",
     "profile": "volve", "licence": "CC BY 4.0", "source": "https://huggingface.co/datasets/bengsoon/volve_daily_drilling_report",
     "what": "1,759 daily reports from drilling Volve's wells (the exploration wells of the 1990s, then the field "
     "wells from 2007 to 2016): each activity with its time, depth and a free-text line."},
    {"id": "f3", "origin": "earlier", "name": "F3 seismic", "path": "seismic/f3", "profile": "seismic",
     "licence": "CC BY 4.0", "source": "https://zenodo.org/records/3755060", "what": "A 3D seismic cube from the "
     "Dutch North Sea with every sample labelled by rock unit: the benchmark for teaching models to read seismic."},
]


def _has(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None


def dir_size(p) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def r(x, d=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


def hist(s: pd.Series, bins, log=False) -> dict:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if log:
        s = np.log10(s[s > 0])
    c, e = np.histogram(s, bins=bins)
    return {"counts": c.tolist(), "edges": [round(float(x), 3) for x in e], "log": log}


def counts(s: pd.Series, n=20) -> list:
    return [{"k": str(k), "n": int(v)} for k, v in s.value_counts().head(n).items()]


# -- profiles --


def p_factpages() -> dict:
    one = lambda sql: rows(sql)[0]  # noqa: E731
    k = one("""select (select count(*) from wellbore_exploration) expl, (select count(*) from wellbore_development) dev,
        (select count(*) from field where fldCurrentActivitySatus = 'Producing') producing, (select count(*) from field) fields,
        (select count(*) from discovery) discoveries, (select count(*) from licence) licences,
        (select count(*) from facility_fixed) facilities,
        (select sum(prfPrdOeNetMillSm3) from field_production_monthly) cum_oe,
        (select sum(fldRemainingOE) from (select * from field_reserves qualify row_number() over (partition by fldNpdidField order by fldVersion desc) = 1)) remaining_oe,
        (select min(prfYear) from field_production_monthly) first_year,
        (select max(fldVersion) from field_reserves) reserves_year""")
    tables = [{"table": t, "rows": n} for t, n in (
        (t, rows(f"select count(*) n from {t}")[0]["n"]) for t in
        [x["table_name"] for x in rows("select table_name from information_schema.tables order by 1")])]
    spud = rows("""select year(wlbEntryDate) y, wlbPurpose p, count(*) n from wellbore_exploration
        where wlbEntryDate is not null group by 1, 2 order by 1""")
    dev = rows("select year(wlbEntryDate) y, count(*) n from wellbore_development where wlbEntryDate is not null group by 1 order by 1")
    content = rows("select coalesce(wlbContent, 'UNKNOWN') k, count(*) n from wellbore_exploration group by 1 order by 2 desc")
    prod = rows("""select prfYear y, sum(prfPrdOilNetMillSm3) oil, sum(prfPrdGasNetBillSm3) gas,
        sum(prfPrdNGLNetMillSm3 + prfPrdCondensateNetMillSm3) ngl,
        case when prfYear >= 2000 then sum(prfPrdProducedWaterInFieldMillSm3) end water, count(distinct prfMonth) as n_months
        from field_production_monthly group by 1 order by 1""")
    prod = [x for x in prod if x["n_months"] == 12]  # whole years only: the current one is still being reported
    top = rows("""select r.fldName field, r.fldRemainingOE remaining, r.fldRecoverableOE recoverable, f.fldHcType hc,
        f.fldMainArea area, f.fldCurrentActivitySatus status, r.fldVersion version
        from (select * from field_reserves qualify row_number() over (partition by fldNpdidField order by fldVersion desc) = 1) r join field f using (fldNpdidField)
        order by r.fldRemainingOE desc limit 20""")
    status = rows("select fldCurrentActivitySatus k, count(*) n from field group by 1 order by 2 desc")
    area = rows("select coalesce(wlbMainArea, 'unknown') k, count(*) n from wellbore_exploration group by 1 order by 2 desc")
    pts = rows("""select wlbWellboreName name, round(wlbNsDecDeg, 4) lat, round(wlbEwDecDeg, 4) lon,
        coalesce(wlbContent, 'UNKNOWN') content, year(wlbEntryDate) y from wellbore_exploration
        where wlbNsDecDeg is not null""")
    disc = rows("""select d.dscCurrentActivityStatus k, count(*) n, sum(r.dscRecoverableOe) oe from discovery d
        left join discovery_reserves r using (dscNpdidDiscovery) group by 1 order by 2 desc""")
    return {"kpis": {k_: r(v, 0) if isinstance(v, float) else v for k_, v in k.items()}, "tables": tables,
            "spud": spud, "dev": dev, "content": content, "production": prod, "top_fields": top, "field_status": status,
            "areas": area, "points": pts, "discoveries": disc}


LITHO = {30000: "Sandstone", 65030: "Sandstone/Shale", 65000: "Shale", 80000: "Marl", 74000: "Dolomite",
         70000: "Limestone", 70032: "Chalk", 88000: "Halite", 86000: "Anhydrite", 99000: "Tuff", 90000: "Coal",
         93000: "Basement"}
CURVES = {"GR": "gamma ray", "RHOB": "bulk density", "NPHI": "neutron porosity", "RDEP": "deep resistivity",
          "RMED": "medium resistivity", "DTC": "compressional sonic", "DTS": "shear sonic", "PEF": "photoelectric factor",
          "CALI": "caliper", "SP": "spontaneous potential", "BS": "bit size", "ROP": "rate of penetration",
          "DRHO": "density correction", "MUDWEIGHT": "mud weight", "RSHA": "shallow resistivity", "SGR": "spectral gamma ray",
          "RMIC": "micro resistivity", "RXO": "flushed-zone resistivity", "DCAL": "differential caliper", "ROPA": "average ROP"}


def p_logs() -> dict:
    d = DATA_DIR / "force2020"
    tr = pd.read_csv(d / "train.csv", sep=";")
    te = pd.read_csv(d / "hidden_test.csv", sep=";")
    tr["set"], te["set"] = "train", "hidden test"
    df = pd.concat([tr, te], ignore_index=True)
    df["lith"] = df.FORCE_2020_LITHOFACIES_LITHOLOGY.map(LITHO)
    # the main curves of every well, small enough for the well lookup to read
    df.assign(WELL=df.WELL.map(norm))[["WELL", "DEPTH_MD", "GR", "RHOB", "NPHI", "RDEP", "lith"]].to_parquet(LOGS)
    avail = []
    for c in CURVES:
        if c in df:
            avail.append({"curve": c, "name": CURVES[c], "rows": round(float(df[c].notna().mean()) * 100, 1),
                          "wells": int(df.groupby("WELL")[c].apply(lambda s: s.notna().mean() > 0.5).sum())})
    wells = []
    for w, g in df.groupby("WELL"):
        wb = wellbore(w) or {}
        wells.append({"well": w, "set": g.set.iloc[0], "top": r(g.DEPTH_MD.min(), 0), "base": r(g.DEPTH_MD.max(), 0),
                      "rows": len(g), "lat": wb.get("lat"), "lon": wb.get("lon"),
                      "main": g.lith.mode().iloc[0] if g.lith.notna().any() else None,
                      "groups": int(g.GROUP.nunique())})
    by_lith = []
    for lith, g in df.groupby("lith"):
        q = lambda c: [r(x, 3) for x in g[c].quantile([0.1, 0.25, 0.5, 0.75, 0.9])]  # noqa: E731
        by_lith.append({"lith": lith, "rows": len(g), "GR": q("GR"), "RHOB": q("RHOB"), "NPHI": q("NPHI"),
                        "RDEP": [r(np.log10(x), 3) if x and x > 0 else None for x in g.RDEP.quantile([0.1, 0.25, 0.5, 0.75, 0.9])]})
    s = df.dropna(subset=["RHOB", "NPHI", "lith"]).sample(12000, random_state=1)
    groups = df.groupby("GROUP").agg(rows=("WELL", "size"), wells=("WELL", "nunique")).reset_index()
    return {"kpis": {"wells": int(df.WELL.nunique()), "train_wells": int(tr.WELL.nunique()),
                     "test_wells": int(te.WELL.nunique()), "rows": len(df), "curves": len(avail),
                     "classes": int(df.lith.nunique()), "deepest": r(df.DEPTH_MD.max(), 0),
                     "las_files": len(list((OFFICIAL / "force2020").rglob("*.las")) + list((OFFICIAL / "force2020").rglob("*.LAS")))},
            "lith": counts(df.lith), "availability": avail, "wells": wells, "by_lith": by_lith,
            "groups": groups.sort_values("rows", ascending=False).to_dict("records"),
            "crossplot": {"rhob": s.RHOB.round(3).tolist(), "nphi": s.NPHI.round(3).tolist(), "lith": s.lith.tolist()},
            "confidence": counts(df.FORCE_2020_LITHOFACIES_CONFIDENCE.dropna().astype(int).astype(str))}


def p_diskosqa() -> dict:
    from sketches import reports

    qa = pd.read_csv(DATA_DIR / "diskosqa" / "diskos_qa.csv")
    ch, _ = reports.corpus()
    wb = Counter(w for ws in ch.wellbores for w in ws)
    fm = Counter(f for fs in ch.formations for f in fs)
    fl = Counter(f for fs in ch.fields for f in fs)
    ex = []
    for _, q in qa[qa.Entailed == True].sample(8, random_state=3).iterrows():  # noqa: E712
        ids = [str(x) for x in reports.lists(q.Chunk_IDs)]
        p = ch[ch.chunk_id.astype(str).isin(ids)]
        ex.append({"q": q.Question, "a": q.Answer, "topic": q.Topic, "kind": q.Filter_type,
                   "passage": p.text.iloc[0][:1500] if len(p) else "", "doc": p.doc_name.iloc[0] if len(p) else ""})
    score = load_json(DATA_DIR / "diskosqa" / "scorecard.json", {})
    return {"kpis": {"questions": len(qa), "supported": int((qa.Entailed == True).sum()),  # noqa: E712
                     "passages": len(ch), "documents": int(ch.doc_name.nunique()), "wellbores": len(wb),
                     "fields": len(fl), "formations": len(fm), "median_chars": int(ch.text.str.len().median())},
            "topics": counts(qa.Topic), "filter_type": counts(qa.Filter_type), "evolutions": counts(qa.Evolutions.fillna("none")),
            "top_wellbores": [{"k": k, "n": n} for k, n in wb.most_common(20)],
            "top_formations": [{"k": k, "n": n} for k, n in fm.most_common(15)],
            "length": hist(ch.text.str.len(), 30), "examples": ex,
            "scorecard": {k: score.get(k) for k in ("retrieval", "answers", "model", "updated")}}


def p_volve() -> dict:
    from sketches import losttime

    a = losttime.activities()
    d = pd.read_parquet(DATA_DIR / "volve" / "ddr.parquet")
    d["day"] = pd.to_datetime(d.dTimStart, utc=True, errors="coerce")
    d = d[d.day.dt.year >= 1990]  # a few reports carry a placeholder date (1979); the exploration wells are from the 1990s
    per_wb = a.groupby("wellbore").agg(hours=("hours", "sum"), npt=("npt", lambda s: 0), days=("report", "nunique"),
                                       md=("md", "max")).reset_index()
    per_wb["npt"] = a[a.npt].groupby("wellbore").hours.sum().reindex(per_wb.wellbore).fillna(0).values
    major = a.groupby("major").hours.sum().sort_values(ascending=False)
    minor = a.groupby(["major", "minor"]).hours.sum().sort_values(ascending=False).head(25)
    month = d.groupby(d.day.dt.strftime("%Y-%m")).size()
    wb = per_wb.sort_values("days", ascending=False).wellbore.iloc[0]
    curve = a[a.wellbore == wb].dropna(subset=["md", "start"]).sort_values("start")
    # the first campaign only: later workovers come years after and would flatten the curve
    gap = curve.start.diff().dt.days.fillna(0) > 30
    curve = curve[gap.cumsum() == 0]
    curve = curve.assign(days=(curve.start - curve.start.min()).dt.total_seconds() / 86400)
    ex = a[a.comments.notna()].sample(12, random_state=2) if "comments" in a else a.head(0)
    return {"kpis": {"reports": len(d), "wellbores": int(a.wellbore.nunique()), "activities": len(a),
                     "hours": r(a.hours.sum(), 0), "npt_share": r(a[a.npt].hours.sum() / a.hours.sum() * 100),
                     "first": str(d.day.min())[:10], "last": str(d.day.max())[:10], "deepest": r(a.md.max(), 0)},
            "major": [{"k": k, "hours": r(v, 0)} for k, v in major.items()],
            "minor": [{"major": k[0], "minor": k[1], "hours": r(v, 0)} for k, v in minor.items()],
            "wellbores": per_wb.round(0).sort_values("days", ascending=False).to_dict("records"),
            "months": [{"m": k, "n": int(v)} for k, v in month.items()],
            "curve": {"wellbore": wb, "days": curve.days.round(2).tolist(), "md": curve.md.round(0).tolist(),
                      "major": curve.major.tolist()},
            "examples": [{"wellbore": e.wellbore, "start": str(e.start)[:16], "hours": r(e.hours), "code": e.proprietaryCode,
                          "md": r(e.md, 0), "text": str(e.comments)[:300]} for e in ex.itertuples()]}


PERM_COLS = ["Permeability horizontal ka  (air)", "Permeability horizontal ke  (klinkenberg corrected)  also called kl. KL",
             "Permeability horizontal kg  (gas) KG HOR", "Nitrogen Permeability. Hor.", "Klinkenberg corrected gas perm. Hor.",
             "Permeabilty without correction specified KH horizontal 1/pm"]


def realpore() -> pd.DataFrame:
    """The plugs in one tidy table (converted once from the xlsx): well, depth, porosity %, permeability mD, rock."""
    if not REALPORE.exists():
        x = pd.read_excel(REALPORE_XLSX)
        perm = pd.concat([pd.to_numeric(x[c], errors="coerce") for c in PERM_COLS], axis=1).bfill(axis=1).iloc[:, 0]
        t = pd.DataFrame({
            "wellbore": x["Data source file name"].astype(str).map(norm), "npdid": pd.to_numeric(x.NPDID, errors="coerce"),
            "md": pd.to_numeric(x["Measured Depth"], errors="coerce"),
            "porosity": pd.to_numeric(x["porosity best of available"], errors="coerce"),
            "perm": perm, "sw": pd.to_numeric(x["Pore Sturation Water Sw  Sw. S wtr. WTR."], errors="coerce"),
            "grain_density": pd.to_numeric(x["gain density gr/cm3"], errors="coerce"),
            "rock": x["clean lithology"].astype("string"), "grain": x["grain size"].astype("string"),
            "cement": x["cement"].astype("string").str.lower(), "description": x["Formation description original"].astype("string"),
        })
        # the file's own names are spelt many ways; Sodir's wellbore id (NPDID) gives the official name
        names = {w["npdid"]: norm(w["name"]) for w in rows("""select wlbNpdidWellbore npdid, wlbWellboreName name
            from wellbore_exploration union all select wlbNpdidWellbore, wlbWellboreName from wellbore_development""")}
        t["wellbore"] = t.npdid.map(names).fillna(t.wellbore)
        t.loc[(t.porosity <= 0) | (t.porosity > 50), "porosity"] = np.nan
        t.loc[t.grain_density > 3.5, "grain_density"] = np.nan
        t.to_parquet(REALPORE)
    return pd.read_parquet(REALPORE)


def p_realpore() -> dict:
    t = realpore()
    by_wb = t.groupby("npdid").agg(plugs=("md", "size"), top=("md", "min"), base=("md", "max"), por=("porosity", "median"))
    pos = {w["npdid"]: w for w in rows("""select wlbNpdidWellbore npdid, wlbWellboreName name, wlbNsDecDeg lat,
        wlbEwDecDeg lon from wellbore_exploration union all select wlbNpdidWellbore, wlbWellboreName, wlbNsDecDeg,
        wlbEwDecDeg from wellbore_development""")}
    wells = [{"name": pos[k]["name"], "lat": r(pos[k]["lat"], 4), "lon": r(pos[k]["lon"], 4), "plugs": int(v.plugs),
              "por": r(v.por)} for k, v in by_wb.iterrows() if k in pos and pos[k]["lat"] is not None]
    pp = t.dropna(subset=["porosity", "perm"])
    pp = pp[pp.perm > 0]
    top_rocks = t.rock.value_counts().head(6).index.tolist()
    s = pp[pp.rock.isin(top_rocks)].sample(min(15000, len(pp)), random_state=1)
    depth = t.dropna(subset=["porosity", "md"])
    depth = depth[depth.rock == "Sandstone"].assign(band=lambda x: (x.md // 250) * 250)
    depth = depth[depth.groupby("band").md.transform("size") >= 200]  # bands with too few plugs say little
    depth = depth.groupby("band").porosity.quantile([0.1, 0.5, 0.9]).unstack().reset_index()
    return {"kpis": {"plugs": len(t), "wellbores": int(t.npdid.nunique()), "with_perm": int(t.perm.notna().sum()),
                     "with_porosity": int(t.porosity.notna().sum()), "median_porosity": r(t.porosity.median()),
                     "median_perm": r(t.perm.median()), "deepest": r(t.md.max(), 0), "on_map": len(wells)},
            "rocks": counts(t.rock), "grain": counts(t.grain, 12), "cement": counts(t.cement, 12),
            "porosity": hist(t.porosity, 40), "perm": hist(t.perm, 40, log=True),
            "crossplot": {"por": s.porosity.round(2).tolist(), "perm": s.perm.round(4).tolist(), "rock": s.rock.tolist()},
            "depth": [{"md": r(b, 0), "p10": r(q[0.1]), "p50": r(q[0.5]), "p90": r(q[0.9])} for b, q in depth.set_index("band").iterrows() if b <= 5500],
            "wells": wells}


def p_text() -> dict:
    out = {}
    for key, fname in TEXT_SOURCES.items():
        f = TEXT / fname
        if not f.exists():
            continue
        docs, pages, natural, chars, lang = set(), 0, 0, [], Counter()
        tags, wb = Counter(), Counter()
        samples = {"text": [], "gibberish": []}
        rng = np.random.default_rng(4)
        cols = ["filename", "page", "content", "possible_language", "content_could_be_natural_language"]
        extra = ["summary_tag", "wellbore"] if key == "uk" else []
        for c in pd.read_csv(f, usecols=cols + extra, chunksize=50000, dtype={"content": "string"}):
            docs.update(c.filename.dropna().unique())
            pages += len(c)
            nat = c.content_could_be_natural_language.astype(str).str.lower() == "true"
            natural += int(nat.sum())
            n = c.content.str.len().fillna(0)
            chars.append(n.sample(min(len(n), 2000), random_state=1).to_numpy())
            lang.update(c.possible_language.fillna("?"))
            if extra:
                tags.update(c.summary_tag.dropna())
                wb.update(c.wellbore.dropna())
            for kind, mask in (("text", nat), ("gibberish", ~nat)):
                pool = c[mask & (n > 300)]
                if len(samples[kind]) < 6 and len(pool) and rng.random() < 0.5:
                    s = pool.sample(1, random_state=int(rng.integers(1e6))).iloc[0]
                    samples[kind].append({"file": s.filename, "page": int(s.page), "text": str(s.content)[:1200]})
        ch = np.concatenate(chars)
        out[key] = {"file": fname, "bytes": f.stat().st_size, "documents": len(docs), "pages": pages,
                    "natural_share": r(natural / pages * 100), "median_chars": int(np.median(ch)),
                    "chars": hist(pd.Series(ch[ch > 0]), 30, log=True), "languages": [{"k": k, "n": v} for k, v in lang.most_common(6)],
                    "samples": samples, "tags": [{"k": k, "n": v} for k, v in tags.most_common(15)],
                    "wellbores": len(wb)}
        if key == "relinquishment":
            pl = sorted({m.group(1) for d in docs if (m := re.search(r"PL[_ ]?0*(\d+)", d, re.I))}, key=int)
            lic = {re.sub(r"\D", "", x["prlName"]): x for x in rows(
                "select prlName, prlDateGranted, prlDateValidTo, prlMainArea, prlStatus from licence")}
            yrs = Counter(y if y <= time.strftime("%Y") else "still held" for p in pl if p in lic and lic[p]["prlDateValidTo"]
                          for y in [str(lic[p]["prlDateValidTo"])[:4]])
            area = Counter(lic[p]["prlMainArea"] for p in pl if p in lic)
            out[key]["licences"] = len(pl)
            out[key]["matched"] = sum(p in lic for p in pl)
            out[key]["ended"] = [{"k": k, "n": v} for k, v in sorted(yrs.items())]
            out[key]["areas"] = [{"k": k, "n": v} for k, v in area.most_common()]
    cat = TEXT / "annotated text categories.xls"
    if cat.exists():
        x = pd.read_excel(cat, engine="calamine") if _has("python_calamine") else pd.read_excel(cat)
        x["cat"] = x["cat"].astype(str)
        ex = [{"k": k, "text": str(g.content.dropna().iloc[0])[:500] if g.content.notna().any() else ""} for k, g in x.groupby("cat")]
        out["annotated"] = {"pages": len(x), "categories": counts(x["cat"]), "types": counts(x["INFO ITEM TYPE"].astype(str), 12),
                            "examples": sorted(ex, key=lambda e: -int((x["cat"] == e["k"]).sum()))}
    return out


def p_completion() -> dict:
    m = pd.read_csv(COMPLETION_META, encoding="utf-8-sig")
    pdf = m[m.Format.str.upper() == "PDF"]
    js = m[m.Format.str.upper() == "JSON"]
    pdf_mb = pd.to_numeric(pdf["File Size (MB)"], errors="coerce")
    created = pd.to_datetime(pdf["Create Date"], errors="coerce", utc=True).dt.year
    released = pd.to_datetime(pdf["Release Date"], errors="coerce", utc=True).dt.year
    names = {norm(w) for w in m["Wellbore Name"].dropna()}
    known = sum(wellbore(w) is not None for w in names)
    spud = Counter()
    for w in names:
        wb = wellbore(w)
        if wb and wb.get("entry"):
            spud[str(wb["entry"])[:3] + "0s"] += 1
    out = {"kpis": {"wellbores": len(names), "pdf": len(pdf), "json": len(js), "pdf_gb": r(pdf_mb.sum() / 1024),
                    "median_mb": r(pdf_mb.median()), "companies": int(pdf["Delivery Company"].nunique()),
                    "in_factpages": known},
           "types": counts(m.drop_duplicates("Wellbore Name")["Wellbore Type"]), "datasets": counts(pdf["Dataset Name"], 12),
           "companies": counts(pdf["Delivery Company"], 15), "size": hist(pdf_mb[pdf_mb > 0], 30, log=True),
           "created": counts(created.dropna().astype(int).astype(str), 60), "released": counts(released.dropna().astype(int).astype(str), 60),
           "decade": [{"k": k, "n": v} for k, v in sorted(spud.items())],
           "columns": [{"k": c, "example": str(m[c].dropna().iloc[0])[:80] if m[c].notna().any() else ""} for c in m.columns]}
    out["unpacked"] = json_profile()
    return out


def json_files():
    return sorted(COMPLETION.rglob("*.json")) + sorted(COMPLETION.rglob("*.JSON"))


def json_profile(limit: int = 400) -> dict | None:
    """The structured reports, once unpacked: their shape from a sample of files."""
    files = json_files()
    if not files:
        return None
    rng = np.random.default_rng(5)
    pick = [files[i] for i in rng.choice(len(files), min(limit, len(files)), replace=False)]
    keys, sizes, pages = Counter(), [], []
    for f in pick:
        sizes.append(f.stat().st_size)
        try:
            d = json.loads(f.read_text(errors="replace"))
        except ValueError:
            continue
        if isinstance(d, dict):
            keys.update(d.keys())
            for v in d.values():
                if isinstance(v, list):
                    pages.append(len(v))
                    break
    pdfs = len(list(COMPLETION.rglob("*.pdf")) + list(COMPLETION.rglob("*.PDF")))
    return {"json_files": len(files), "pdf_files": pdfs, "sampled": len(pick), "top_keys": [{"k": k, "n": v} for k, v in keys.most_common(20)],
            "kb": hist(pd.Series(sizes) / 1024, 30, log=True), "items": hist(pd.Series(pages), 30) if pages else None}


def p_seismic() -> dict:
    from sketches import seismic

    out = {"f3": None, "adele": None}
    try:
        s, l = seismic.cube("train")
        lab = np.asarray(l[::10])
        out["f3"] = {"shape": list(s.shape), "facies": [{"k": n, "n": int((lab == i).sum())} for i, n in enumerate(seismic.NAMES)],
                     "gb": r(dir_size(DATA_DIR / "seismic" / "f3") / 1e9, 2)}
    except HTTPException:
        pass
    if ADELE.exists():
        import segyio

        with segyio.open(str(ADELE), ignore_geometry=True) as f:
            n, ns = f.tracecount, len(f.samples)
            il = f.attributes(segyio.TraceField.INLINE_3D)[:]
            xl = f.attributes(segyio.TraceField.CROSSLINE_3D)[:]
            dt = segyio.tools.dt(f) / 1000
            mid = int(np.median(np.unique(il)))
            idx = np.where(il == mid)[0]
            sec = np.stack([f.trace[int(i)] for i in idx[:: max(1, len(idx) // 500)]]).T
            sec = sec[:: max(1, ns // 400)]
            amp = np.concatenate([f.trace[int(i)] for i in np.linspace(0, n - 1, 300).astype(int)])
            text = segyio.tools.wrap(f.text[0])[:3200]
        scale = float(np.percentile(np.abs(sec), 99)) or 1.0
        out["adele"] = {"traces": int(n), "samples": ns, "dt_ms": dt, "inlines": [int(il.min()), int(il.max())],
                        "crosslines": [int(xl.min()), int(xl.max())], "n_inlines": int(len(np.unique(il))),
                        "n_crosslines": int(len(np.unique(xl))), "record_ms": r(ns * dt, 0), "gb": r(ADELE.stat().st_size / 1e9, 2),
                        "amplitude": hist(pd.Series(amp), 60), "header": text,
                        "section": {"inline": mid, "shape": list(sec.shape), "scale": scale, "data": seismic.pack(sec.astype(np.float32), scale)}}
    return out


def p_links() -> dict:
    """Which wellbores each dataset covers, joined on the normalised wellbore name: the glue between them."""
    from sketches import reports

    sets = {"factpages": {norm(w["name"]) for w in rows("select wlbWellboreName name from wellbore_exploration union all "
                                                       "select wlbWellboreName from wellbore_development")}}
    sets["logs"] = set(pd.concat([pd.read_csv(DATA_DIR / "force2020" / f, sep=";", usecols=["WELL"]).WELL.map(norm)
                                  for f in ("train.csv", "hidden_test.csv")]).unique())
    ch, _ = reports.corpus()
    sets["diskosqa"] = {w for ws in ch.wellbores for w in ws}
    sets["volve"] = set(pd.read_parquet(DATA_DIR / "volve" / "ddr.parquet").nameWellbore.map(norm))
    if REALPORE_XLSX.exists():
        sets["realpore"] = set(realpore().wellbore.dropna())
    if COMPLETION_META.exists():
        sets["completion"] = set(pd.read_csv(COMPLETION_META, encoding="utf-8-sig", usecols=["Wellbore Name"])["Wellbore Name"].dropna().map(norm))
    fp = sets["factpages"]
    out = {"sets": {k: {"wellbores": len(v), "in_factpages": len(v & fp)} for k, v in sets.items()}, "pairs": []}
    keys = [k for k in sets if k != "factpages"]
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            out["pairs"].append({"a": a, "b": b, "n": len(sets[a] & sets[b])})
    allk = Counter(w for k in keys for w in sets[k])
    best = [w for w, n in allk.most_common(40) if n >= 3]
    out["richest"] = [{"wellbore": w, "in": [k for k in keys if w in sets[k]]} for w in best[:25]]
    save_json(OUT / "sets.json", {k: sorted(v) for k, v in sets.items() if k != "factpages"})
    return out


PROFILES = {"factpages": p_factpages, "logs": p_logs, "diskosqa": p_diskosqa, "volve": p_volve, "realpore": p_realpore,
            "text": p_text, "completion": p_completion, "seismic": p_seismic, "links": p_links}


def build(names: list[str]) -> None:
    for n in names:
        t = time.time()
        try:
            save_json(OUT / f"{n}.json", safe({"built": time.strftime("%Y-%m-%d %H:%M"), **PROFILES[n]()}))
            print(f"{n}: {time.time() - t:.0f} s", flush=True)
        except FileNotFoundError as e:
            print(f"{n}: skipped, {e}", flush=True)


# -- the page and its API --


@router.get("")
def slash():
    return RedirectResponse("atlas/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("atlas.html")


@router.get("/api/catalog")
def catalog():
    out = []
    for c in CATALOG:
        p = DATA_DIR / c["path"]
        prof = OUT / f"{c['profile']}.json"
        pending = list(p.rglob("*.part")) if p.is_dir() else []
        out.append({**c, "present": p.exists() and dir_size(p) > 0, "bytes": dir_size(p),
                    "downloading": bool(pending), "profiled": bool(c["profile"]) and prof.exists(),
                    "built": (load_json(prof, {}) or {}).get("built") if c["profile"] and prof.exists() else None})
    return {"datasets": out, "links": load_json(OUT / "links.json")}


@router.get("/api/profile/{name}")
def profile(name: str):
    if name not in PROFILES:
        raise HTTPException(404, "no such dataset")
    d = load_json(OUT / f"{name}.json")
    if d is None:
        raise HTTPException(404, f"not profiled yet: uv run python -m sketches.atlas {name}")
    return d


def safe(o):
    """NaN and infinity as null, so any profile or record serialises."""
    if isinstance(o, float):
        return None if not np.isfinite(o) else o
    if isinstance(o, dict):
        return {k: safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [safe(v) for v in o]
    return o


@lru_cache(maxsize=1)
def _logs() -> pd.DataFrame:
    return pd.read_parquet(LOGS)


@lru_cache(maxsize=1)
def _sets() -> dict:
    return {k: set(v) for k, v in (load_json(OUT / "sets.json", {}) or {}).items()}


@router.get("/api/well/{name:path}")
def well(name: str):
    """One wellbore through every dataset."""
    w = wellbore(name)
    key = norm(name)
    if not w and not any(key in s for s in _sets().values()):
        raise HTTPException(404, f"no wellbore {name}")
    out = {"name": w["name"] if w else key, "header": {k: (str(v) if v is not None else None) for k, v in (w or {}).items()}}
    q = lambda sql: rows(sql, out["name"])  # noqa: E731
    out["tops"] = q("""select lsuName unit, lsuTopDepth top, lsuBottomDepth base, lsuLevel level
        from wellbore_formation_top where wlbName = ? order by lsuTopDepth""")
    out["casing"] = q("""select wlbCasingType type, wlbCasingDiameter diameter, wlbCasingDepth depth, wlbHoleDepth hole,
        wlbLotMudDencity lot from wellbore_casing_and_lot where wlbName = ? order by wlbCasingDepth""")
    out["cores"] = q("""select wlbCoreNumber n, wlbCoreIntervalTop top, wlbCoreIntervalBottom base, wlbCoreIntervalUom uom
        from wellbore_core where wlbName = ? order by wlbCoreIntervalTop""")
    out["documents"] = q("select wlbDocumentType type, wlbDocumentName name, wlbDocumentUrl url from wellbore_document where wlbName = ?")
    s = _sets()
    out["in"] = {k: key in v for k, v in s.items()}
    if out["in"].get("realpore"):
        t = realpore()
        t = t[t.wellbore == key].dropna(subset=["md"]).sort_values("md")
        out["plugs"] = {"md": t.md.round(1).tolist(), "porosity": t.porosity.round(2).tolist(),
                        "perm": t.perm.round(3).tolist(), "rock": t.rock.fillna("").tolist()}
    if out["in"].get("diskosqa"):
        from sketches import reports

        ch, _ = reports.corpus()
        hit = ch[ch.wellbores.map(lambda ws: key in ws)]
        out["passages"] = [{"doc": p.doc_name, "text": p.text[:600]} for p in hit.head(6).itertuples()]
        out["passage_count"] = len(hit)
    if out["in"].get("completion"):
        m = pd.read_csv(COMPLETION_META, encoding="utf-8-sig", usecols=["Wellbore Name", "Format", "Dataset Name", "File Size (MB)", "FolderFileName"])
        m = m[m["Wellbore Name"].map(norm) == key]
        out["completion"] = m.fillna("").to_dict("records")
    if out["in"].get("logs") and LOGS.exists():
        lw = _logs()
        lw = lw[lw.WELL == key].sort_values("DEPTH_MD")
        lw = lw.iloc[:: max(1, len(lw) // 1500)]
        col = lambda c: [None if pd.isna(v) else round(float(v), 4) for v in lw[c]]  # noqa: E731
        out["logs"] = {"depth": col("DEPTH_MD"), **{c: col(c) for c in ("GR", "RHOB", "NPHI", "RDEP") if lw[c].notna().any()},
                       "lith": lw.lith.fillna("").tolist()}
    return safe(out)


@router.get("/api/report/{name:path}")
def report(name: str):
    """The structured completion report(s) for a wellbore, once unpacked: the first file's shape and opening items."""
    key = norm(name)
    files = [f for f in json_files() if norm(f.parent.name.replace("_", "/", 1)) == key or key.replace("/", "_") in f.name]
    if not files:
        raise HTTPException(404, "no unpacked JSON report for this wellbore yet")
    d = json.loads(files[0].read_text(errors="replace"))
    return {"file": str(files[0].relative_to(COMPLETION)), "files": len(files), "preview": json.dumps(d, indent=1)[:12000]}


if __name__ == "__main__":
    build(sys.argv[1:] or list(PROFILES))
