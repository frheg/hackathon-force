"""Build the unit table: one row per wellbore x formation interval, with position, label and coverage.

Run: uv run python -m se.ingest.units   (LOG L008, L009)
Needs: data/ncs.duckdb (FactPages) and data/atlas/greenclay/descriptions.parquet (hackathon-force: python -m sketches.greenclay).
"""
import duckdb
import numpy as np
import pandas as pd

from se.config import DATA, MIN_COVERAGE, OUT, TARGET
from se.ingest.names import norm

FT = 3.28084
LEVELS = ("FORMATION", "GROUP")


def wellbores() -> pd.DataFrame:
    """Position, total depth and reference heights per wellbore (FactPages exploration + development)."""
    con = duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True)
    cols = "wlbWellboreName n, wlbNsDecDeg lat, wlbEwDecDeg lon, wlbTotalDepth td, wlbKellyBushElevation kb, wlbWaterDepth wd"
    w = con.execute(f"select {cols} from wellbore_exploration union all select {cols} from wellbore_development").df()
    w["wellbore"] = w.n.map(norm)
    return w.drop_duplicates("wellbore").drop(columns="n")


def tops(w: pd.DataFrame) -> pd.DataFrame:
    """Formation and group intervals in measured depth, with a sane thickness and inside the well."""
    con = duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True)
    t = con.execute("select wlbName, lsuName name, lsuLevel level, lsuTopDepth top, lsuBottomDepth bot from wellbore_formation_top "
                    "where lsuTopDepth is not null and lsuBottomDepth is not null").df()
    t = t[t.level.isin(LEVELS)].copy()
    t["wellbore"] = t.wlbName.map(norm)
    t = t.merge(w, on="wellbore")
    ok = (t.bot > t.top) & ((t.bot - t.top) <= 3000) & t.lat.notna() & t.td.notna() & (t.bot <= t.td * 1.05)
    return t[ok].drop(columns="wlbName").reset_index(drop=True)


def rows_in_metres(d: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    """Description rows have no unit. A depth beyond the well's total depth is read as feet; if it still does not fit, it is dropped."""
    d = d.merge(w[["wellbore", "td"]], on="wellbore")
    d = d[d.td.notna()].copy()
    far = d.depth_from > d.td * 1.05
    d.loc[far, "depth_from"] = d.loc[far, "depth_from"] / FT
    d["depth_to"] = d.depth_to.where(~far, d.depth_to / FT)
    return d[d.depth_from <= d.td * 1.05].drop(columns="td")


def build() -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    w = wellbores()
    t = tops(w)
    d = pd.read_parquet(DATA / "atlas" / "greenclay" / "descriptions.parquet")
    d = rows_in_metres(d[d.lith.isin(TARGET["lith"])], w)  # trials = rows of the target lithology only (L019)
    # rows inside each unit: join on wellbore, keep the ones whose depth falls in [top, bot]
    m = t[["wellbore", "name", "level", "top", "bot"]].reset_index().rename(columns={"index": "uid"}).merge(
        d[["wellbore", "depth_from", "has_green"]], on="wellbore")
    m = m[(m.depth_from >= m.top) & (m.depth_from <= m.bot)]
    g = m.groupby("uid").agg(coverage=("has_green", "size"), n_green=("has_green", "sum"))
    t = t.join(g).fillna({"coverage": 0, "n_green": 0})
    t[["coverage", "n_green"]] = t[["coverage", "n_green"]].astype(int)
    # L009: positive = a green mention inside; negative = enough description and none; else unlabelled
    t["label"] = np.where(t.n_green > 0, 1, np.where(t.coverage >= MIN_COVERAGE, 0, -1))
    t["unit"] = t.wellbore + " | " + t.name
    t["thickness"] = t.bot - t.top
    t.to_parquet(OUT / "units.parquet")
    return t


if __name__ == "__main__":
    u = build()
    lab = u[u.label >= 0]
    print(f"{len(u)} units in {u.wellbore.nunique()} wellbores; labelled {len(lab)} ({lab.label.mean():.1%} positive) in {lab.wellbore.nunique()} wellbores")
    print(lab.groupby("name").label.agg(["size", "mean"]).sort_values("size", ascending=False).head(12).round(2).to_string())
