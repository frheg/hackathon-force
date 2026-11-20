"""Pore pressure, mud weight and fracture pressure in the pilot (PLAN P3.3, LOG L060).

Units: pressure MPa; equivalent mud weight (EMW) g/cm3 referenced to sea level, EMW = P / (0.00981 * TVDSS).
Sources (FactPages): DST bottom-hole or final shut-in pressure = pore pressure in a flowing zone; mud weight while drilling = an
upper bound (wells drill overbalanced); LOT / FIT EMW at the casing shoe = fracture pressure (lower bound for FIT).
Hydrostatic reference: brine of 1.03 g/cm3 from sea level (assumption, tested here on DST data: P4 rule R-HYD).
Tests: (a) a held-out DST predicted from mud weight in the same well at the same depth, with the overbalance ratio fitted on other
40 km blocks; (b) a 3D GP of excess EMW (DST hard, mud-derived soft) on held-out blocks, vs hydrostatic and vs a depth trend.
"""
import json

import duckdb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from se.config import DATA, EARTH
from se.earth import manifest
from se.earth.folds import blocks
from se.earth.frame import Frame
from se.earth.gp import GP
from se.ingest.names import norm

G = 0.00981  # MPa per m per g/cm3
RHO_HYD = 1.03
P_ATM = 0.1013
Z90 = 1.645
VSCALE = (5.0, 20.0, 80.0)  # 1 km of depth counts as this many km laterally in the 3D kernel; chosen by CV


def hydro(z):
    return P_ATM + G * RHO_HYD * np.asarray(z, float)


def _interval(tops: pd.DataFrame):
    """wellbore -> list of (top_md, bot_md, name, level), formations first so the finer unit wins."""
    t = tops.dropna(subset=["top_md"]).sort_values(["wellbore", "level"], ascending=[True, False])
    return {wb: list(zip(g.top_md, g.bot_md.fillna(np.inf), g.name, g.level)) for wb, g in t.groupby("wellbore")}


def unit_at(iv, wb, md):
    best = (None, None)
    for a, b, n, lv in iv.get(wb, []):
        if a <= md < b:
            if lv == "FORMATION":
                return (n, lv)
            best = (n, lv)
    return best


def observations() -> pd.DataFrame:
    w = pd.read_parquet(EARTH / "wells.parquet"); pw = set(w[w.pilot].wellbore); kb = w.set_index("wellbore").kb
    cal = json.loads((EARTH / "frame_calibration.json").read_text()); fr = Frame(cal)
    tops = pd.read_parquet(EARTH / "tops.parquet"); iv = _interval(tops)
    c = duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True)
    d = c.execute("select * from wellbore_dst").df(); d["wb"] = d.wlbName.map(norm); d = d[d.wb.isin(pw)]
    d["P"] = np.where(d.wlbDstBottomHolePress > 0, d.wlbDstBottomHolePress, np.where(d.wlbDstFinShutInPress > 0, d.wlbDstFinShutInPress, np.nan))
    d["src"] = np.where(d.wlbDstBottomHolePress > 0, "DST bottom-hole", "DST final shut-in")
    d = d[d.P.notna() & (d.wlbDstFromDepth > 0)]
    m = c.execute("select * from wellbore_mud where wlbMudWeightAtMD > 0.9").df(); m["wb"] = m.wlbName.map(norm); m = m[m.wb.isin(pw)]
    l = c.execute("select * from wellbore_casing_and_lot where wlbLotMudDencity > 0").df(); l["wb"] = l.wlbName.map(norm); l = l[l.wb.isin(pw)]
    kb = kb[~kb.index.duplicated()]
    recs = []  # (kind, src, wellbore, md, P or None, emw_rkb or None, extra)
    for r in d.itertuples():
        recs.append(("pore", r.src, r.wb, 0.5 * (r.wlbDstFromDepth + r.wlbDstToDepth), float(r.P), None,
                     {"oil_Sm3": float(r.wlbDstOilProd or 0), "gas_Sm3": float(r.wlbDstGasProd or 0), "temp_C": float(r.wlbDstDownholeTemperatur or 0) or np.nan}))
    for r in m.itertuples():
        recs.append(("mud", "mud weight", r.wb, float(r.wlbMD), None, float(r.wlbMudWeightAtMD), {}))
    for r in l.itertuples():
        recs.append(("frac", (r.wlbFormationTestType or "").strip() or "LOT", r.wb, float(r.wlbCasingDepth), None, float(r.wlbLotMudDencity), {}))
    R = pd.DataFrame(recs, columns=["kind", "src", "wellbore", "md", "P", "emw_rkb", "extra"])
    R = R[np.isfinite(R.md) & (R.md > 0)]
    rows = []
    for wb, g in R.groupby("wellbore"):  # one frame lookup per well (vectorised along MD)
        a = fr.at(wb, g.md.to_numpy())
        z = np.asarray(a["tvdss"], float); k = float(kb.get(wb, np.nan))
        # mud / LOT EMW is referenced to the rig floor: P = 0.00981 * EMW * TVD below RKB
        P = np.where(g.P.notna(), g.P.astype(float), G * g.emw_rkb.astype(float) * (z + k))
        for i, r in enumerate(g.itertuples()):
            if not (np.isfinite(z[i]) and z[i] > 10 and np.isfinite(P[i])):
                continue
            u, lv = unit_at(iv, wb, r.md)
            rows.append({"kind": r.kind, "src": r.src, "wellbore": wb, "md": float(r.md), "tvdss": float(z[i]), "x": float(np.asarray(a["x"])[i]), "y": float(np.asarray(a["y"])[i]),
                         "sigma_z": float(np.asarray(a["sigma_z"])[i]), "P": float(P[i]), "emw_ss": float(P[i] / (G * z[i])), "excess_MPa": float(P[i] - hydro(z[i])),
                         "unit": u, "unit_level": lv, **r.extra})
    return pd.DataFrame(rows)




def mud_test(o: pd.DataFrame, win_m=150.0, folds=5) -> tuple[dict, pd.DataFrame]:
    """(a) DST pressure from the mud weight in the same well at the nearest MD within win_m: P_pore = P_mud * r, r fitted on other blocks."""
    dst, mud = o[o.kind == "pore"], o[o.kind == "mud"]
    pairs = []
    for wb, g in dst.groupby("wellbore"):
        mm = mud[mud.wellbore == wb]
        if mm.empty:
            continue
        for r in g.itertuples():
            j = (mm.md - r.md).abs().idxmin()
            if abs(mm.md[j] - r.md) <= win_m:
                pairs.append({"wellbore": wb, "x": r.x, "y": r.y, "tvdss": r.tvdss, "P": r.P, "P_mud_same_depth": mm.P[j] * r.tvdss / mm.tvdss[j]})
    p = pd.DataFrame(pairs)
    if len(p) < 15:
        return {"pairs": int(len(p)), "skipped": "too few DST with mud weight nearby"}, p
    bl = blocks(p.x.to_numpy(), p.y.to_numpy()); e_mud, e_hyd, ratios = [], [], []
    for tr, te in GroupKFold(min(folds, len(np.unique(bl)))).split(p, groups=bl):
        r = float(np.median(p.P.iloc[tr] / p.P_mud_same_depth.iloc[tr])); ratios.append(r)
        e_mud += list(p.P_mud_same_depth.iloc[te] * r - p.P.iloc[te]); e_hyd += list(hydro(p.tvdss.iloc[te]) - p.P.iloc[te])
    e_mud, e_hyd = np.array(e_mud), np.array(e_hyd)
    return {"pairs": int(len(p)), "wells": int(p.wellbore.nunique()), "ratio_pore_over_mud_median": round(float(np.median(p.P / p.P_mud_same_depth)), 4),
            "fold_ratios": [round(x, 4) for x in ratios],
            "mud_bias_MPa": round(float(e_mud.mean()), 2), "mud_rmse_MPa": round(float(np.sqrt((e_mud ** 2).mean())), 2), "mud_p90_abs_MPa": round(float(np.percentile(np.abs(e_mud), 90)), 2),
            "hydrostatic_bias_MPa": round(float(e_hyd.mean()), 2), "hydrostatic_rmse_MPa": round(float(np.sqrt((e_hyd ** 2).mean())), 2)}, p


def field_test(o: pd.DataFrame, ratio: float, mud_sd: float, folds=5) -> dict:
    """(b) 3D GP of excess EMW over hydrostatic: DST as hard data, mud-derived pore EMW as soft (variance mud_sd^2), held-out DST blocks."""
    dst = o[o.kind == "pore"].copy()
    mud = o[o.kind == "mud"].copy()
    mud = mud.assign(zb=(mud.tvdss // 100)).drop_duplicates(["wellbore", "zb"])  # one sample per 100 m per well
    def y_of(d, P):  # target: excess EMW (named ex: y is the northing)
        return P / (G * d.tvdss) - RHO_HYD
    dst["ex"] = y_of(dst, dst.P); dst["v"] = (0.01) ** 2
    mud["ex"] = y_of(mud, mud.P * ratio); mud["v"] = (mud_sd / (G * mud.tvdss)) ** 2
    mud = mud.sample(min(len(mud), 1500), random_state=0)  # exact GP cost grows with n^3; 1,500 soft points keep a fold fit to seconds
    bl = blocks(dst.x.to_numpy(), dst.y.to_numpy()); out = {}
    for vs in VSCALE:
        A = pd.concat([dst, mud])  # hyperparameters once per scale on all data (they set smoothness only); the fold fits reuse them
        hp = GP(1, ell_bounds=(1.0, 300.0)).fit(np.c_[A.x, A.y, A.tvdss / 1000 * vs], A.ex.to_numpy(), A.v.to_numpy())
        hp = (hp.ell, hp.s2, hp.nug)
        e = {"gp3d": [], "hydro": [], "trend": []}; zs, fo = [], []
        for tr, te in GroupKFold(min(folds, len(np.unique(bl)))).split(dst, groups=bl):
            held = set(blocks(dst.x.iloc[te].to_numpy(), dst.y.iloc[te].to_numpy()))
            mtr = mud[~np.isin(blocks(mud.x.to_numpy(), mud.y.to_numpy()), list(held))]
            T = pd.concat([dst.iloc[tr], mtr])
            X = np.c_[T.x, T.y, T.tvdss / 1000 * vs]; Xt = np.c_[dst.x.iloc[te], dst.y.iloc[te], dst.tvdss.iloc[te] / 1000 * vs]
            gp = GP(1, ell_bounds=(1.0, 300.0)).fit(X, T.ex.to_numpy(), T.v.to_numpy(), params=hp)
            mu, var = gp.predict(Xt, latent=False)
            yt = dst.ex.iloc[te].to_numpy()
            e["gp3d"] += list(mu - yt); zs += list((mu - yt) / np.sqrt(var + 0.01 ** 2)); fo += [len(set(fo))] * len(yt)
            e["hydro"] += list(-yt)
            b = np.polyfit(T.tvdss, T.ex, 2); e["trend"] += list(np.polyval(b, dst.tvdss.iloc[te]) - yt)
        zs, fo = np.array(zs), np.array(fo); inside = []
        for f in np.unique(fo):  # nested: the sigma inflation of a fold is fitted on the other folds
            kf = max(1.0, float(np.percentile(np.abs(zs[fo != f]), 90)) / Z90); inside += list(np.abs(zs[fo == f]) <= Z90 * kf)
        out[vs] = {m: round(float(np.sqrt(np.mean(np.square(v)))), 4) for m, v in e.items()} | {"cover90_raw": round(float(np.mean(np.abs(zs) <= Z90)), 3),
                   "cover90_nested": round(float(np.mean(inside)), 3), "inflation": round(max(1.0, float(np.percentile(np.abs(zs), 90)) / Z90), 3)}
    best = min(out, key=lambda k: out[k]["gp3d"])
    return {"by_vertical_scale": out, "vertical_scale": best, "units": "EMW g/cm3 excess over 1.03", "dst": int(len(dst)), "mud_soft": int(len(mud))}


EMW_OK = (0.95, 2.3)  # a pore pressure lies between about hydrostatic and the overburden (about 2.3 g/cm3): physical QC (L060)


def qc(o: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """DST pressures outside EMW_OK are not reservoir pressures: below = likely a wellhead reading (minus the fluid column),
    above = likely bar recorded as MPa or a typing error. They are flagged and excluded, never rescaled."""
    pore = o.kind == "pore"
    lo, hi = pore & (o.emw_ss < EMW_OK[0]), pore & (o.emw_ss > EMW_OK[1])
    o = o.assign(qc=np.where(lo, "below hydrostatic: likely wellhead pressure", np.where(hi, "above overburden: likely unit or entry error", "ok")))
    return o, {"dst_total": int(pore.sum()), "excluded_low": int(lo.sum()), "excluded_high": int(hi.sum()),
               "examples": o[lo | hi][["wellbore", "src", "md", "P", "emw_ss", "qc"]].head(10).round(3).to_dict("records")}


def build() -> dict:
    o, q = qc(observations())
    o.to_parquet(EARTH / "pressure_obs.parquet")
    o = o[o.qc == "ok"]
    a, pairs = mud_test(o)
    dst = o[o.kind == "pore"]
    hyd_ok = dst[dst.excess_MPa.abs() < 1.0]
    out = {"qc": q, "counts": o.kind.value_counts().to_dict(), "dst_wells": int(dst.wellbore.nunique()),
           "dst_emw_median": round(float(dst.emw_ss.median()), 3), "dst_share_overpressured_gt_1MPa": round(float((dst.excess_MPa > 1).mean()), 3),
           "normally_pressured_dst_emw_median": round(float(hyd_ok.emw_ss.median()), 4) if len(hyd_ok) else None,
           "mud_vs_dst": a}
    if "mud_rmse_MPa" in a:
        out["field"] = field_test(o, a["ratio_pore_over_mud_median"], a["mud_rmse_MPa"])
    frac = o[o.kind == "frac"]
    out["fracture_emw_median"] = round(float(frac.emw_ss.median()), 3)
    (EARTH / "pressure_report.json").write_text(json.dumps(out, indent=1, default=str))
    manifest.write(EARTH / "pressure_obs.parquet", [DATA / "ncs.duckdb", EARTH / "tops.parquet", EARTH / "wells.parquet"], {"rho_hydrostatic": RHO_HYD, "vscale": VSCALE})
    return out


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=str))
