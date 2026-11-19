"""Target builder: a recipe (spec) turns a FactPages table into the unit table the engine already understands.

Three modes. All end in the same columns as units.parquet: wellbore, name (grouping for the formation layer), lat, lon, top, bot,
coverage (= trials), n_green (= successes; the column keeps its name so the layers and validation run unchanged), label, unit.

  well      one unit per wellbore from a wellbore table. trials = 1; success = the success filters hold. name = the group column
            (area, age at TD, purpose...). Example: found oil or gas in a wildcat well.
  interval  one unit per wellbore x formation (FactPages tops). Rows of an interval table (DST, mud, cores) fall in a unit by depth.
            trials = rows that pass the population filters; successes = those that also pass the success filters.

  text      like interval, but the rows are rock-description lines from the well reports (data/atlas/reporttext, LOG L034): success = the
            line contains one of the keywords; trials = lines of the chosen lithologies. Effort bias stays visible: trials = lines described.

Filters are strings "column|op|value", the same as the explorer. Extra ops here: in / notin (comma-separated list).
"""
import hashlib
import json
import re
from functools import lru_cache

import duckdb
import numpy as np
import pandas as pd

from se.config import DATA, OUT
from se.ingest.names import norm
from se.ingest.units import tops, wellbores, rows_in_metres

WELL_TABLES = {"wellbore_exploration": "wlbWellboreName", "wellbore_development": "wlbWellboreName"}
# interval table -> (wellbore column, depth column in metres MD)
INTERVAL_TABLES = {"wellbore_dst": ("wlbName", "wlbDstFromDepth"), "wellbore_mud": ("wlbName", "wlbMD"), "wellbore_core": ("wlbName", "wlbCoreIntervalTop"), "wellbore_casing_and_lot": ("wlbName", "wlbCasingDepth")}
NUMERIC_OPS = {"gt": lambda s, v: s > v, "lt": lambda s, v: s < v, "ge": lambda s, v: s >= v, "le": lambda s, v: s <= v}


def spec_id(spec: dict) -> str:
    """Same recipe, same id: results are cached and comparable."""
    key = json.dumps({k: spec.get(k) for k in ("mode", "table", "population", "success", "group", "keywords", "lith")}, sort_keys=True)
    return hashlib.sha1(key.encode()).hexdigest()[:10]


def apply(df: pd.DataFrame, filters: list) -> pd.Series:
    m = pd.Series(True, index=df.index)
    for f in filters or []:
        col, op, *v = f.split("|", 2)
        if col not in df.columns:
            raise ValueError(f"no column {col}")
        val = v[0] if v else ""
        s = df[col]
        if op in NUMERIC_OPS:
            m &= NUMERIC_OPS[op](pd.to_numeric(s, errors="coerce"), float(val)).fillna(False)
        elif op == "eq":
            m &= (s.astype(str) == val)
        elif op == "ne":
            m &= (s.astype(str) != val)
        elif op == "has":
            m &= s.astype(str).str.contains(val, case=False, regex=False)
        elif op in ("in", "notin"):
            hit = s.astype(str).isin([x.strip() for x in val.split(",")])
            m &= hit if op == "in" else ~hit
        elif op == "null":
            m &= s.isna()
        elif op == "notnull":
            m &= s.notna()
        else:
            raise ValueError(f"bad op {op}")
    return m


def table(name: str) -> pd.DataFrame:
    return duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True).execute(f'select * from "{name}"').df()


TEXT_FILE = DATA / "atlas" / "reporttext" / "descriptions_text.parquet"
LITHS = ("clay", "sand", "carbonate", "other")


@lru_cache(maxsize=1)
def text_lines() -> pd.DataFrame:
    return pd.read_parquet(TEXT_FILE)


def keyword_regex(keywords) -> re.Pattern:
    """Keywords are plain words or phrases, matched case-insensitively at a word start (so 'calc' finds calcareous and calcite)."""
    ks = [k.strip() for k in keywords if k and k.strip()]
    if not ks:
        raise ValueError("give at least one keyword")
    return re.compile(r"\b(?:" + "|".join(re.escape(k) for k in ks) + ")", re.I)


def text_rows(spec: dict) -> pd.DataFrame:
    t = text_lines()
    t = t[t.lith.isin(spec.get("lith") or LITHS)]
    rx = keyword_regex(spec["keywords"])
    return t.assign(has_green=t.text.str.contains(rx))[["wellbore", "depth_from", "depth_to", "has_green"]]


def intervals(r: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    """Rows (wellbore, depth_from, depth_to, has_green) -> one unit per well x formation interval; trials = rows, successes = rows with has_green."""
    r = rows_in_metres(r, w)  # a depth beyond total depth is read as feet; if it still does not fit, the row is dropped
    tp = tops(w)
    m = tp[["wellbore", "name", "level", "top", "bot"]].reset_index().rename(columns={"index": "uid"}).merge(r[["wellbore", "depth_from", "has_green"]], on="wellbore")
    m = m[(m.depth_from >= m.top) & (m.depth_from <= m.bot)]
    g = m.groupby("uid").agg(coverage=("has_green", "size"), n_green=("has_green", "sum"))
    u = tp.join(g).fillna({"coverage": 0, "n_green": 0})
    u[["coverage", "n_green"]] = u[["coverage", "n_green"]].astype(int)
    return u


def build(spec: dict) -> pd.DataFrame:
    w = wellbores()
    if spec["mode"] == "well":
        t = table(spec["table"])
        t = t[apply(t, spec.get("population"))].copy()
        t["wellbore"] = t[WELL_TABLES[spec["table"]]].map(norm)
        ok = apply(t, spec["success"])
        g = spec.get("group") or "wlbMainArea"
        u = pd.DataFrame({"wellbore": t.wellbore, "name": t[g].astype(str).where(t[g].notna(), "UNKNOWN"), "coverage": 1, "n_green": ok.astype(int)}).merge(w[["wellbore", "lat", "lon", "td", "kb", "wd"]], on="wellbore")
        u = u[u.lat.notna()].drop_duplicates("wellbore")
        u["level"], u["top"], u["bot"] = "WELL", 0.0, u.td.fillna(0.0)
    elif spec["mode"] == "text":
        u = intervals(text_rows(spec), w)
    else:
        cw, cd = INTERVAL_TABLES[spec["table"]]
        t = table(spec["table"])
        t = t[apply(t, spec.get("population"))].copy()
        t["wellbore"], t["success"] = t[cw].map(norm), apply(t, spec["success"])
        r = pd.DataFrame({"wellbore": t.wellbore, "depth_from": pd.to_numeric(t[cd], errors="coerce").astype(float), "has_green": t.success}).dropna(subset=["depth_from"])
        u = intervals(r.assign(depth_to=r.depth_from), w)  # tables are in metres; the guard drops depths beyond total depth
    u["label"] = np.where(u.n_green > 0, 1, np.where(u.coverage >= 1, 0, -1)).astype(int)
    u["unit"] = u.wellbore + " | " + u.name.astype(str)
    u["thickness"] = u.bot - u.top
    return u.reset_index(drop=True)
