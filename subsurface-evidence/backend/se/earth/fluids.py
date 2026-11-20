"""Fluid observations per well and unit (PLAN P3.5, LOG L065), and seal thickness per column (P3.6).

Fluids, one row per (well, unit, source), each with its strength of evidence:
  dst_flow       a DST in the unit flowed oil or gas                         hc = 1, strong
  dst_no_flow    a DST in the unit flowed no hydrocarbons                     hc = 0, strong (tested, but may be tight)
  fp_hc_unit     FactPages names the unit among the well's formations with HC hc = 1, strong
  fp_dry         the well is DRY: every penetrated unit                       hc = 0, medium
  fp_not_listed  the well found HC elsewhere, not in this penetrated unit      hc = 0, weak (FactPages lists at most 3)
  fp_shows       SHOWS wells: penetrated units                                shows, not counted as hc
Report shows from P5 are added there. Seal: per column, the shale-dominated thickness within 300 m above each layer.
"""
import json

import duckdb
import numpy as np
import pandas as pd

from se.config import DATA, EARTH
from se.earth import manifest
from se.ingest.names import norm

SEAL_WINDOW = 300.0  # m above a unit top in which shale-dominated rock counts as its seal
STRENGTH = {"dst_flow": 1.0, "dst_no_flow": 1.0, "fp_hc_unit": 1.0, "fp_dry": 0.6, "fp_not_listed": 0.3, "fp_shows": 0.0}


def fluid_type(content: str) -> str:
    c = (content or "").upper()
    return "oil and gas" if "OIL" in c and ("GAS" in c or "CONDENSATE" in c) else "oil" if "OIL" in c else "gas" if "GAS" in c else "none"


def build_fluids() -> pd.DataFrame:
    w = pd.read_parquet(EARTH / "wells.parquet"); w = w[w.pilot].set_index("wellbore")
    tops = pd.read_parquet(EARTH / "tops.parquet")
    pen = tops.groupby("wellbore").name.apply(set).to_dict()  # units each well penetrated
    c = duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True)
    e = c.execute("select wlbWellboreName, wlbContent, wlbFormationWithHc1, wlbFormationWithHc2, wlbFormationWithHc3 from wellbore_exploration").df()
    e["wellbore"] = e.wlbWellboreName.map(norm); e = e[e.wellbore.isin(w.index)]
    rows = []
    for r in e.itertuples():
        units = pen.get(r.wellbore, set()); hc = {u.strip() for u in (r.wlbFormationWithHc1, r.wlbFormationWithHc2, r.wlbFormationWithHc3) if isinstance(u, str) and u.strip()}
        content = r.wlbContent.upper() if isinstance(r.wlbContent, str) else ""; ft = fluid_type(content)
        for u in hc:
            rows.append((r.wellbore, u, 1, ft, "fp_hc_unit"))
        if content == "DRY":
            rows += [(r.wellbore, u, 0, "none", "fp_dry") for u in units]
        elif "SHOWS" in content:
            rows += [(r.wellbore, u, np.nan, "shows", "fp_shows") for u in units]
        elif hc:
            rows += [(r.wellbore, u, 0, "none", "fp_not_listed") for u in units - hc]
    p = pd.read_parquet(EARTH / "pressure_obs.parquet"); d = p[(p.kind == "pore") & p.unit.notna()]
    for r in d.itertuples():
        flow = (r.oil_Sm3 or 0) > 0 or (r.gas_Sm3 or 0) > 0
        ft = "oil and gas" if r.oil_Sm3 > 0 and r.gas_Sm3 > 0 else "oil" if r.oil_Sm3 > 0 else "gas" if r.gas_Sm3 > 0 else "none"
        rows.append((r.wellbore, r.unit, int(flow), ft, "dst_flow" if flow else "dst_no_flow"))
    f = pd.DataFrame(rows, columns=["wellbore", "unit", "hc", "fluid", "source"]).drop_duplicates()
    f["strength"] = f.source.map(STRENGTH); f["x"], f["y"] = f.wellbore.map(w.x), f.wellbore.map(w.y)
    return f


def seal_columns() -> dict:
    """Per column and group: thickness (m) of the shale-dominated units directly above the group top (contiguous from the group up).
    Shale-dominated: FORCE shale + half the heterolithic share >= 0.6 for that unit across pilot wells (lithology_wells.parquet)."""
    g = np.load(EARTH / "grid.npz"); zb, lab, labels = g["zb"], g["label"], [str(s).split("|") for s in g["labels"]]
    wt = pd.read_parquet(EARTH / "lithology_wells.parquet")
    cols = [c for c in wt.columns if isinstance(c, (int, np.integer)) or str(c).isdigit()]
    tot = wt.groupby("unit")[cols].sum(); sh = ((tot[cols[2]] + 0.5 * tot[cols[1]]) / tot[cols].sum(1)).to_dict()
    shale_lab = np.array([sh.get(f or gname, sh.get(gname, 0.0)) >= 0.6 for gname, f in labels])
    dz = np.diff(zb.astype(np.float64), axis=0)
    is_sh = shale_lab[lab]  # (k, j, i)
    # seal above each layer: shale-dominated thickness within SEAL_WINDOW m above its top (the seal may sit above other storage
    # units: at Aurora the Drake caprock lies above the Cook sand above the Johansen, L069). A contiguous-only measure gave 0 there.
    cum = np.concatenate([np.zeros((1,) + dz.shape[1:]), np.cumsum(dz * is_sh, axis=0)])  # shale thickness from the top, at each boundary
    run = np.zeros_like(dz)
    z = zb.astype(np.float64)
    for j in range(dz.shape[1]):
        for i in range(dz.shape[2]):
            zc, cc = z[:, j, i], cum[:, j, i]
            if not np.isfinite(zc).all():
                continue
            run[:, j, i] = cc[:-1] - np.interp(zc[:-1] - SEAL_WINDOW, zc, cc)
    np.save(EARTH / "seal_above.npy", run.astype(np.float32))
    return {"shale_dominated_units": sorted(u for u, v in sh.items() if v >= 0.6), "threshold": 0.6,
            "window_m": SEAL_WINDOW, "median_seal_above_m_inside": round(float(np.median(run[:, g["inside"]])), 1)}


def build() -> dict:
    f = build_fluids(); f.to_parquet(EARTH / "fluids.parquet")
    s = seal_columns()
    out = {"rows": int(len(f)), "wells": int(f.wellbore.nunique()), "by_source": f.source.value_counts().to_dict(),
           "hc_units_top": f[f.hc == 1].unit.value_counts().head(12).to_dict(), "seal": s}
    (EARTH / "fluids_report.json").write_text(json.dumps(out, indent=1))
    manifest.write(EARTH / "fluids.parquet", [DATA / "ncs.duckdb", EARTH / "tops.parquet", EARTH / "pressure_obs.parquet", EARTH / "grid.npz"], {"strength": STRENGTH})
    return out


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
