"""Build the unit table: one row per wellbore x formation interval, with position, label and coverage.

Run: uv run python -m se.ingest.units   (LOG L008, L009)
Needs: data/ncs.duckdb (FactPages) and data/atlas/greenclay/descriptions.parquet (hackathon-force: python -m sketches.greenclay).
"""
import json

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
    return t[ok].drop(columns="wlbName").drop_duplicates(["wellbore", "name", "level", "top", "bot"]).reset_index(drop=True)


def rows_in_metres(d: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    """Description rows have no unit. A depth beyond the well's total depth is read as feet; if it still does not fit, it is dropped."""
    d = d.merge(w[["wellbore", "td"]], on="wellbore")
    d = d[d.td.notna()].copy()
    far = d.depth_from > d.td * 1.05
    d.loc[far, "depth_from"] = d.loc[far, "depth_from"] / FT
    d["depth_to"] = d.depth_to.where(~far, d.depth_to / FT)
    return d[d.depth_from <= d.td * 1.05].drop(columns="td")


def unit_ids(t: pd.DataFrame) -> pd.Series:
    """Stable, unambiguous public identity for repeated names and repeated formation tops."""
    depth = lambda x: f"{float(x):.6f}".rstrip("0").rstrip(".")
    return (t.wellbore.astype(str) + " | " + t.level.astype(str) + " | " + t.name.astype(str) + " [" +
            t.top.map(depth) + "," + t.bot.map(depth) + "]")


def with_unit_group(t: pd.DataFrame) -> pd.DataFrame:
    """Attach the containing group without using groups for formation row assignment."""
    t = t.drop_duplicates(["wellbore", "name", "level", "top", "bot"]).reset_index(drop=True).copy()
    t["uid"] = np.arange(len(t))
    t["group"] = np.where(t.level == "GROUP", t.name, None)
    fs, gs = t[t.level == "FORMATION"], t[t.level == "GROUP"]
    if len(fs) and len(gs):
        f = fs[["uid", "wellbore", "top", "bot"]].copy()
        g = gs[["uid", "wellbore", "name", "top", "bot"]].rename(columns={"uid": "gid", "name": "group", "top": "g_top", "bot": "g_bot"})
        candidates = f.merge(g, on="wellbore")
        candidates = candidates[(candidates.top <= candidates.g_bot) & (candidates.bot >= candidates.g_top)].copy()
        candidates["overlap"] = np.minimum(candidates.bot, candidates.g_bot) - np.maximum(candidates.top, candidates.g_top)
        candidates["width"] = candidates.g_bot - candidates.g_top
        chosen = candidates.sort_values(["uid", "overlap", "width", "g_top", "g_bot", "group", "gid"],
                                       ascending=[True, False, True, True, True, True, True]).drop_duplicates("uid")
        t.loc[t.uid.isin(chosen.uid), "group"] = chosen.set_index("uid").group
    t["unit"] = unit_ids(t)
    return t.drop(columns="uid")


def assign_intervals(r: pd.DataFrame, t: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Assign each source row once: formation first, otherwise group; overlap ties are narrowest then shallowest."""
    t = with_unit_group(t).reset_index(drop=True)
    r = r[["wellbore", "depth_from", "has_green"]].reset_index(drop=True).copy()
    r["row_id"] = np.arange(len(r))
    intervals = t[["wellbore", "name", "level", "top", "bot"]].reset_index().rename(columns={"index": "uid"}).copy()
    candidates = intervals.merge(r[["row_id", "wellbore", "depth_from"]], on="wellbore")
    candidates = candidates[(candidates.depth_from >= candidates.top) & (candidates.depth_from <= candidates.bot)].copy()
    if candidates.empty:
        selected = candidates.assign(candidate_count=0)
    else:
        candidates["level_rank"] = (candidates.level != "FORMATION").astype(int)
        candidates["width"] = candidates.bot - candidates.top
        best_level = candidates.groupby("row_id").level_rank.transform("min")
        preferred = candidates[candidates.level_rank == best_level].copy()
        counts = preferred.groupby("row_id").size().rename("candidate_count")
        selected = preferred.sort_values(["row_id", "width", "top", "bot", "name", "uid"]).drop_duplicates("row_id")
        selected = selected.join(counts, on="row_id")
    selected = selected[["row_id", "uid", "candidate_count", "level"]] if len(selected) else selected
    rows = r.merge(selected, on="row_id", how="left")
    g = rows.groupby("uid").agg(coverage=("has_green", "size"), n_green=("has_green", "sum"))
    out = t.join(g).fillna({"coverage": 0, "n_green": 0})
    out[["coverage", "n_green"]] = out[["coverage", "n_green"]].astype(int)
    assigned = rows.uid.notna()
    ambiguous = int((rows.candidate_count.fillna(0) > 1).sum())
    conflicts = []
    if ambiguous and len(selected):
        for rid in rows.loc[rows.candidate_count > 1, "row_id"].head(50):
            c = candidates[candidates.row_id == rid]
            c = c[c.level_rank == c.level_rank.min()].sort_values(["width", "top", "bot", "name", "uid"])
            chosen = int(selected[selected.row_id == rid].uid.iloc[0])
            conflicts.append({"row_id": int(rid), "wellbore": r.iloc[int(rid)].wellbore,
                              "depth_from": float(r.iloc[int(rid)].depth_from), "chosen_unit": out.loc[chosen, "unit"],
                              "candidates": c.assign(unit=unit_ids(t.loc[c.uid]).to_numpy())[["unit", "level", "top", "bot"]].to_dict("records")})
    diag = {"source_rows": len(r), "assigned_once": int(assigned.sum()), "unassigned": int((~assigned).sum()),
            "formation_assigned": int((rows.level == "FORMATION").sum()), "group_fallback": int((rows.level == "GROUP").sum()),
            "ambiguous_candidates": ambiguous, "conflicts": conflicts,
            "conflicts_shown": len(conflicts), "conflicts_omitted": max(0, ambiguous - len(conflicts))}
    return out, diag


def build() -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    w = wellbores()
    t = tops(w)
    source = pd.read_parquet(DATA / "atlas" / "greenclay" / "descriptions.parquet")
    source = source[source.lith.isin(TARGET["lith"])]  # trials = rows of the target lithology only (L019)
    d = rows_in_metres(source.copy(), w)
    t, assignment = assign_intervals(d, t)
    # L009: positive = a green mention inside; negative = enough description and none; else unlabelled
    t["label"] = np.where(t.n_green > 0, 1, np.where(t.coverage >= MIN_COVERAGE, 0, -1))
    t["thickness"] = t.bot - t.top
    diagnostics = {"total_source_rows": len(source), "depth_normalization_rows": len(d),
                   "dropped_before_assignment": int(len(source) - len(d)), **assignment}
    diagnostics["unassigned"] += diagnostics["dropped_before_assignment"]
    diagnostics["source_rows"] = diagnostics["total_source_rows"]
    (OUT / "unit_diagnostics.json").write_text(json.dumps(diagnostics, indent=2, default=float))
    t.to_parquet(OUT / "units.parquet")
    return t


if __name__ == "__main__":
    u = build()
    lab = u[u.label >= 0]
    print(f"{len(u)} units in {u.wellbore.nunique()} wellbores; labelled {len(lab)} ({lab.label.mean():.1%} positive) in {lab.wellbore.nunique()} wellbores")
    print(lab.groupby("name").label.agg(["size", "mean"]).sort_values("size", ascending=False).head(12).round(2).to_string())
