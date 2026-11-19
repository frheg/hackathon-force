"""Data catalog and explorer over the FactPages database. Read-only; identifiers come from information_schema, values are bound parameters."""
import duckdb
import numpy as np
from fastapi import APIRouter, HTTPException, Query

from se.config import DATA

router = APIRouter(prefix="/api")
NUM = ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "FLOAT", "DOUBLE", "DECIMAL", "UBIGINT", "UINTEGER")
OPS = {"eq": "= ?", "ne": "<> ?", "gt": "> ?", "lt": "< ?", "ge": ">= ?", "le": "<= ?", "has": "ILIKE ?", "null": "IS NULL", "notnull": "IS NOT NULL"}

# What each dataset is, in one line, and whether the green-clay tool uses it. Sizes are measured, not guessed (LOG L027).
DATASETS = [
    {"name": "Completion reports", "source": 'Provided for the hackathon: 4,462 fully public completion reports from the Norwegian shelf (Diskos national data bank, Sodir regulator).', "path": "official/completion_reports", "size": "112 GB", "what": "4,462 end-of-well report PDFs: rock descriptions, depths, tests, shows, pressures. Text extracted to official/text (5.7 GB).", "used": "green words only"},
    {"name": "FactPages database", "source": 'Sodir (Norwegian Offshore Directorate) open FactPages register. Public.', "path": "ncs.duckdb", "size": "12 MB", "what": "Sodir register: wells, formation tops, cores, mud, casing, DST, fields, production, reserves, licences, facilities. Explorable below.", "used": "tops and positions"},
    {"name": "FORCE 2020 logs", "source": 'FORCE 2020 machine-learning competition, Zenodo 4351156, CC BY 4.0. Real NCS wells.', "path": "official/force2020", "size": "600 MB", "what": "Instrument readings along 106 wells (gamma, density, neutron, sonic, resistivity, PEF) with an expert lithology label per depth.", "used": "log layer (hurt)"},
    {"name": "Seismic cubes", "source": 'Public research cubes: Penobscot (Zenodo 3924682, CC BY 4.0), F3 (Dutch North Sea), Parihaka (NZ), FaultSeg3D (synthetic), ADELE (Australia). See docs/seismic-data.md.', "path": "seismic/", "size": "8.6 GB", "what": "F3 (Dutch North Sea), Penobscot, Parihaka, FaultSeg3D (synthetic), ADELE (Australia). 3D reflection data. None is over our NCS wells.", "used": "no"},
    {"name": "DiskosQA", "source": 'DISKOS-QA: 1,027 questions over 1,690 Diskos report passages, NLOD 2.0.', "path": "diskosqa/", "size": "12 MB", "what": "Question and answer pairs and text chunks from Norwegian well reports.", "used": "no"},
    {"name": "Green clay extraction", "source": 'Made here from the completion reports (greenclay.py, LOG L007 to L010).', "path": "atlas/greenclay", "size": "2.5 MB", "what": "Our own output: 209,707 rock-description rows (depth, lithology, green flag), 32,586 green mentions, 4,441 wells.", "used": "yes (the target)"},
    {"name": "RealPore / KSAT / Volve", "source": 'Hackathon-provided rock-physics sets; the Volve data share could not be opened (docs/seismic-data.md).', "path": "official/realpore, volve/", "size": "<50 MB", "what": "Rock-physics lab samples. Volve's data share never opened.", "used": "no"},
]


def con():
    return duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True)


def cols(c, table):
    r = c.execute("select column_name, data_type from information_schema.columns where table_name=? order by ordinal_position", [table]).fetchall()
    if not r:
        raise HTTPException(404, "no such table")
    return {n: t for n, t in r}


def where(c, table, filters, cs):
    sql, args = [], []
    for f in filters:
        col, op, *v = f.split("|", 2)
        if col not in cs or op not in OPS:
            raise HTTPException(400, f"bad filter {f}")
        if op in ("null", "notnull"):
            sql.append(f'"{col}" {OPS[op]}')
            continue
        val = v[0] if v else ""
        if cs[col].split("(")[0] in NUM and op != "has":
            val = float(val)
        sql.append(f'"{col}" {OPS[op]}'); args.append(f"%{val}%" if op == "has" else val)
    return (" where " + " and ".join(sql)) if sql else "", args


@router.get("/catalog")
def catalog():
    c = con()
    ts = [r[0] for r in c.execute("select table_name from information_schema.tables order by 1").fetchall()]
    tabs = [{"name": t, "rows": c.execute(f'select count(*) from "{t}"').fetchone()[0], "cols": len(cols(c, t))} for t in ts]
    return {"datasets": DATASETS, "tables": tabs}


@router.get("/table/columns")
def table_columns(name: str):
    c = con(); cs = cols(c, name)
    n = c.execute(f'select count(*) from "{name}"').fetchone()[0]
    out = []
    for k, t in cs.items():
        q = c.execute(f'select count(*) filter (where "{k}" is null), count(distinct "{k}"), min("{k}")::varchar, max("{k}")::varchar from "{name}"').fetchone()
        out.append({"name": k, "type": t, "numeric": t.split("(")[0] in NUM, "null_share": q[0] / max(n, 1), "distinct": q[1], "min": q[2], "max": q[3]})
    return {"table": name, "rows": n, "columns": out}


@router.get("/table/rows")
def table_rows(name: str, f: list[str] = Query([]), limit: int = 100, offset: int = 0, sort: str | None = None, desc: bool = False):
    c = con(); cs = cols(c, name); w, a = where(c, name, f, cs)
    order = f' order by "{sort}" {"desc" if desc else "asc"}' if sort in cs else ""
    n = c.execute(f'select count(*) from "{name}"{w}', a).fetchone()[0]
    df = c.execute(f'select * from "{name}"{w}{order} limit {int(min(limit, 500))} offset {int(offset)}', a).df()
    return {"total": n, "columns": list(df.columns), "rows": df.astype(object).where(df.notna(), None).values.tolist()}


@router.get("/table/chart")
def table_chart(name: str, x: str, y: str | None = None, agg: str = "count", f: list[str] = Query([]), bins: int = 40):
    """Histogram of a number, or top categories of anything, optionally with a mean/sum/median of y per group."""
    c = con(); cs = cols(c, name); w, a = where(c, name, f, cs)
    if x not in cs or (y and y not in cs) or agg not in ("count", "mean", "sum", "median"):
        raise HTTPException(400, "bad column or agg")
    fn = {"count": "count(*)", "mean": f'avg("{y}")', "sum": f'sum("{y}")', "median": f'median("{y}")'}[agg if y else "count"]
    if cs[x].split("(")[0] in NUM:
        lo, hi = c.execute(f'select min("{x}"), max("{x}") from "{name}"{w}', a).fetchone()
        if lo is None:
            return {"kind": "empty", "x": [], "y": []}
        step = (hi - lo) / bins or 1
        r = c.execute(f'select floor(("{x}" - ?) / ?)::int b, {fn} from "{name}"{w}{" and" if w else " where"} "{x}" is not null group by 1 order by 1', [lo, step] + a).fetchall()
        return {"kind": "hist", "x": [lo + (b + 0.5) * step for b, _ in r], "y": [v for _, v in r], "step": step, "lo": lo}
    r = c.execute(f'select "{x}"::varchar k, {fn} v from "{name}"{w} group by 1 order by 2 desc nulls last limit 30', a).fetchall()
    return {"kind": "cat", "x": [k for k, _ in r], "y": [v for _, v in r]}


@router.get("/table/points")
def table_points(name: str, f: list[str] = Query([]), color: str | None = None, limit: int = 6000):
    c = con(); cs = cols(c, name); w, a = where(c, name, f, cs)
    lat = next((k for k in cs if k.lower() in ("wlbnsdecdeg", "nsdecdeg", "lat", "latitude")), None)
    lon = next((k for k in cs if k.lower() in ("wlbewdecdeg", "ewdecdeg", "lon", "longitude")), None)
    if not (lat and lon):
        return {"points": [], "note": "this table has no latitude/longitude columns"}
    sel = f', "{color}" as c' if color in cs else ""
    df = c.execute(f'select "{lat}" lat, "{lon}" lon{sel} from "{name}"{w}{" and" if w else " where"} "{lat}" is not null limit {int(limit)}', a).df()
    return {"points": df.astype(object).where(df.notna(), None).to_dict("records"), "lat": lat, "lon": lon}
