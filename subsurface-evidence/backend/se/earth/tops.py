"""Datums and formation tops in true vertical depth (PLAN P1.2, P1.3; LOG L055).

Datum check per wellbore: the shallowest top (MD below rig floor) should equal KB + water depth (the seabed), as found in L030.
Tops: every FactPages top and bottom converted to TVDSS with sigma and lateral radius from the frame; no row is dropped silently.
"""
import json

import duckdb
import numpy as np
import pandas as pd

from se.config import DATA, EARTH
from se.earth import manifest
from se.earth.frame import Frame
from se.ingest.names import norm

SEABED_TOL_M = 5.0  # shallowest top within 5 m of KB + water depth counts as consistent


def raw_tops() -> pd.DataFrame:
    c = duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True)
    t = c.execute("select wlbName, lsuName name, lsuLevel level, lsuTopDepth top_md, lsuBottomDepth bot_md from wellbore_formation_top").df()
    t["wellbore"] = t.wlbName.map(norm)
    return t.drop(columns="wlbName")


def datum_checks(fr: Frame, t: pd.DataFrame) -> pd.DataFrame:
    w = fr.w
    first = t.groupby("wellbore").top_md.min()
    d = pd.DataFrame({"wellbore": w.index, "kb": w.kb.to_numpy(), "wd": w.wd.to_numpy(), "pilot": w.pilot.to_numpy()}).set_index("wellbore")
    d["first_top_md"] = first.reindex(d.index)
    d["seabed_md"] = d.kb + d.wd
    d["seabed_gap_m"] = d.first_top_md - d.seabed_md
    d["status"] = np.select([d.kb.isna(), d.wd.isna(), d.first_top_md.isna(), d.seabed_gap_m.abs() <= SEABED_TOL_M],
                            ["no KB", "no water depth", "no tops", "consistent"], "inconsistent")
    return d.reset_index()


def check_on_force(fr: Frame, tp: pd.DataFrame) -> dict:
    """Acceptance (P1.3): at the real formation tops of FORCE wells, does the FactPages-only TVDSS fall within its 90 percent interval?"""
    f = tp[tp.source == "force"]
    err, inside, wells = [], [], set()
    for wb, g in f.groupby("wellbore"):
        force = fr.force.pop(wb)  # hide the true path for this well
        try:
            a = fr.at(wb, g.top_md.to_numpy())
        finally:
            fr.force[wb] = force
        if a["source"] != "factpages":
            continue
        e = a["tvdss"] - g.top_tvdss.to_numpy()
        err += list(e); inside += list(np.abs(e) <= 1.645 * np.hypot(a["sigma_z"], g.sigma_z.to_numpy())); wells.add(wb)
    e = np.array(err)
    return {"wells": len(wells), "tops": int(len(e)), "rmse_m": round(float(np.sqrt(np.mean(e ** 2))), 2) if len(e) else None,
            "median_abs_m": round(float(np.median(np.abs(e))), 2) if len(e) else None, "cover90": round(float(np.mean(inside)), 3) if len(e) else None}


def build(pilot_only: bool = True) -> dict:
    EARTH.mkdir(parents=True, exist_ok=True)
    fr = Frame(json.loads((EARTH / "frame_calibration.json").read_text()))
    t = raw_tops()
    dc = datum_checks(fr, t)
    dc.to_parquet(EARTH / "datums.parquet")
    n0 = len(t)
    t = t.merge(fr.w[["pilot", "kb"]], left_on="wellbore", right_index=True, how="left")
    diag = {"tops_in_registry": n0, "no_wellhead": int(t.pilot.isna().sum())}
    if pilot_only:
        t = t[t.pilot.fillna(False).astype(bool)]
    diag["tops_in_scope"] = int(len(t))
    diag["no_kb"] = int(t.kb.isna().sum())
    out = []
    for wb, g in t.groupby("wellbore"):
        a, b = fr.at(wb, g.top_md.to_numpy()), fr.at(wb, g.bot_md.fillna(g.top_md).to_numpy())
        out.append(g.assign(x=a["x"], y=a["y"], top_tvdss=a["tvdss"], bot_tvdss=np.where(g.bot_md.notna(), b["tvdss"], np.nan),
                            sigma_z=a["sigma_z"], sigma_z_bot=b["sigma_z"], r_lat=a["r_lat"], source=a["source"]))
    tp = pd.concat(out).reset_index(drop=True)
    tp["thick_tvd"] = tp.bot_tvdss - tp.top_tvdss
    diag["converted"] = int(tp.top_tvdss.notna().sum())
    diag["not_converted_no_kb"] = int(tp.top_tvdss.isna().sum())
    diag["by_source"] = tp.source.value_counts().to_dict()
    diag["negative_thickness"] = int((tp.thick_tvd < -1).sum())
    pd_ = dc[dc.pilot]
    diag["datums_pilot"] = pd_.status.value_counts().to_dict()
    diag["seabed_gap_m_pilot"] = {"median": round(float(pd_.seabed_gap_m.median()), 2), "p10": round(float(pd_.seabed_gap_m.quantile(0.1)), 2), "p90": round(float(pd_.seabed_gap_m.quantile(0.9)), 2)}
    diag["check_force_tops"] = check_on_force(fr, tp)
    tp.to_parquet(EARTH / "tops.parquet")
    (EARTH / "tops_diagnostics.json").write_text(json.dumps(diag, indent=1, default=int))
    manifest.write(EARTH / "tops.parquet", [DATA / "ncs.duckdb", EARTH / "wells.parquet", EARTH / "frame_calibration.json"], {"pilot_only": pilot_only, "seabed_tol_m": SEABED_TOL_M}, {"diagnostics": diag})
    return diag


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=int))
