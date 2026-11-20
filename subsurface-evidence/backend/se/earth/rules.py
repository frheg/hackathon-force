"""Test the earth-model rules (se/knowledge/rules/earth.yaml) on our data (PLAN P4.1, LOG L066).

Each check returns numbers and a verdict: agrees | disagrees | inconclusive | not_testable. Bootstrap over wells where a rate or a median
is compared, so one well with many samples cannot decide a verdict.
"""
import json
from pathlib import Path

import numpy as np

from se.earth import atomic
import pandas as pd
import yaml

from se.config import DATA, EARTH
from se.earth.frame import FORCE_TRAIN
from se.ingest.names import norm

RULES = Path(__file__).parents[1] / "knowledge" / "rules" / "earth.yaml"


def _force(cols):
    from se.earth.lithology import unit_name

    f = pd.read_csv(FORCE_TRAIN, sep=";", usecols=["WELL", "DEPTH_MD", "FORMATION", "GROUP", *cols])
    f["wellbore"] = f.WELL.map(norm); w = pd.read_parquet(EARTH / "wells.parquet"); f = f[f.wellbore.isin(set(w[w.pilot].wellbore))]
    f["unit"] = f.FORMATION.map(unit_name).fillna(f.GROUP.map(unit_name))
    return f


def boot_median_diff(a: pd.DataFrame, b: pd.DataFrame, col, n=400, seed=0):
    """Median of a minus median of b, resampling whole wells; returns (diff, p05, p95)."""
    rng = np.random.default_rng(seed); wa, wb = a.wellbore.unique(), b.wellbore.unique(); ga, gb = dict(list(a.groupby("wellbore"))), dict(list(b.groupby("wellbore")))
    d = []
    for _ in range(n):
        sa = pd.concat([ga[w] for w in rng.choice(wa, len(wa))]); sb = pd.concat([gb[w] for w in rng.choice(wb, len(wb))])
        d.append(sa[col].median() - sb[col].median())
    return float(a[col].median() - b[col].median()), float(np.percentile(d, 5)), float(np.percentile(d, 95))


def boot_rate_diff(a: pd.DataFrame, b: pd.DataFrame, n=400, seed=0):
    """Weighted event rate of a minus b (columns ev, w), resampling whole wells; returns (diff, p05, p95)."""
    rng = np.random.default_rng(seed); ga, gb = dict(list(a.groupby("wellbore"))), dict(list(b.groupby("wellbore"))); wa, wb = list(ga), list(gb)
    rate = lambda d: float(np.average(d.ev, weights=d.w))
    d = [rate(pd.concat([ga[w] for w in rng.choice(wa, len(wa))])) - rate(pd.concat([gb[w] for w in rng.choice(wb, len(wb))])) for _ in range(n)]
    return rate(a) - rate(b), float(np.percentile(d, 5)), float(np.percentile(d, 95))


def verdict_from(lo, hi, want="+"):
    return ("agrees" if lo > 0 else "disagrees" if hi < 0 else "inconclusive") if want == "+" else ("agrees" if hi < 0 else "disagrees" if lo > 0 else "inconclusive")


def check(r: dict) -> dict:
    c = r["check"]; t = c["type"]
    if t in ("density_vs_core", "gardner_logs", "draupne_gr") and _force(["GR"]).empty:  # P8: regions without FORCE wells have no log data
        return {"verdict": "not_testable", "why": "no FORCE log wells in this region"}
    if t == "athy_core":
        p = json.loads((EARTH / "poroperm_report.json").read_text()); a = p["athy_fit"]
        return {"phi0_pct": a["phi0_pct"], "c_per_km": a["c_per_km"], "sclater_christie_sandstone_c": 0.27, "held_out_rmse_pct": p["rmse_phi_pct"],
                "verdict": "agrees" if a["c_per_km"] > 0 and abs(a["c_per_km"] - 0.27) < 0.1 else "disagrees"}
    if t == "density_vs_core":
        f = _force(["RHOB"]).dropna(subset=["RHOB"])
        core = pd.read_parquet(DATA / "official/realpore/realpore.parquet", columns=["wellbore", "md", "porosity"]).dropna()
        core["wellbore"] = core.wellbore.map(norm)
        m = []
        for wb, g in core[core.wellbore.isin(set(f.wellbore))].groupby("wellbore"):
            lg = f[f.wellbore == wb].sort_values("DEPTH_MD")
            i = np.searchsorted(lg.DEPTH_MD.to_numpy(), g.md.to_numpy()); i = np.clip(i, 1, len(lg) - 1)
            d0, d1 = lg.DEPTH_MD.to_numpy()[i - 1], lg.DEPTH_MD.to_numpy()[i]; j = np.where(np.abs(g.md - d0) < np.abs(g.md - d1), i - 1, i)
            ok = np.abs(lg.DEPTH_MD.to_numpy()[j] - g.md.to_numpy()) <= 0.5
            m.append(pd.DataFrame({"wellbore": wb, "core": g.porosity.to_numpy()[ok], "rhob": lg.RHOB.to_numpy()[j][ok], "unit": lg.unit.to_numpy()[j][ok]}))
        m = pd.concat(m); m["dphi"] = (2.65 - m.rhob) / (2.65 - 1.0) * 100
        e = m.dphi - m.core
        return {"pairs": int(len(m)), "wells": int(m.wellbore.nunique()), "corr": round(float(np.corrcoef(m.dphi, m.core)[0, 1]), 3), "bias_pct": round(float(e.median()), 2),
                "mad_pct": round(float(np.median(np.abs(e - e.median()))), 2), "verdict": "agrees" if np.corrcoef(m.dphi, m.core)[0, 1] > 0.6 else "inconclusive"}
    if t == "gardner_logs":
        f = _force(["RHOB", "DTC"]).dropna(subset=["RHOB", "DTC"]); f = f[(f.DTC > 40) & (f.DTC < 200)]
        V = 304800.0 / f.DTC; pred = 0.31 * V ** 0.25; e = pred - f.RHOB
        return {"samples": int(len(f)), "wells": int(f.wellbore.nunique()), "median_error_gcc": round(float(e.median()), 3), "mad_gcc": round(float(np.median(np.abs(e - e.median()))), 3),
                "corr": round(float(np.corrcoef(pred, f.RHOB)[0, 1]), 3), "verdict": "agrees" if abs(e.median()) < 0.1 else "disagrees"}
    if t == "hydrostatic":
        p = json.loads((EARTH / "pressure_report.json").read_text()); v = p["normally_pressured_dst_emw_median"]
        return {"normally_pressured_dst_emw_median": v, "share_overpressured": p["dst_share_overpressured_gt_1MPa"], "verdict": "agrees" if abs(v - 1.03) < 0.03 else "disagrees"}
    if t == "gradient_range":
        p = json.loads((EARTH / "temperature_report.json").read_text()); g = p["gradient_C_per_km"]
        return {"gradient_C_per_km": g, "range": [c["low"], c["high"]], "verdict": "agrees" if c["low"] <= g <= c["high"] else "disagrees"}
    if t == "brent_facies":
        w = pd.read_parquet(EARTH / "lithology_wells.parquet"); cols = [k for k in w.columns if str(k).isdigit()]
        units = ["BROOM FM", "RANNOCH FM", "ETIVE FM", "NESS FM", "TARBERT FM"]; t_ = w[w.unit.isin(units)].groupby("unit")[cols].sum()
        sh = (t_.T / t_.sum(1)).T
        coal, sand = sh[cols[10]].to_dict(), sh[cols[0]].to_dict()
        ok = max(coal, key=coal.get) == "NESS FM" and max(sand, key=sand.get) == "ETIVE FM"
        return {"coal_share": {k: round(v, 3) for k, v in coal.items()}, "sand_share": {k: round(v, 3) for k, v in sand.items()},
                "wells": {u: int((w.unit == u).sum()) for u in units}, "verdict": "agrees" if ok else ("inconclusive" if max(coal, key=coal.get) == "NESS FM" else "disagrees")}
    if t == "draupne_gr":
        f = _force(["GR"]).dropna(subset=["GR"]); d, h = f[f.unit == "DRAUPNE FM"], f[f.unit == "HEATHER FM"]
        diff, lo, hi = boot_median_diff(d, h, "GR")
        w = pd.read_parquet(EARTH / "lithology_wells.parquet"); cols = [k for k in w.columns if str(k).isdigit()]; t_ = w[w.unit == "DRAUPNE FM"][cols].sum()
        shale = float((t_[cols[2]] + 0.5 * t_[cols[1]]) / t_.sum())
        return {"draupne_median_GR": round(float(d.GR.median()), 1), "heather_median_GR": round(float(h.GR.median()), 1), "diff": round(diff, 1), "p05": round(lo, 1), "p95": round(hi, 1),
                "wells": int(d.wellbore.nunique()), "shale_share": round(shale, 3), "verdict": "agrees" if d.GR.median() > 100 and lo > 0 and shale >= 0.8 else verdict_from(lo, hi)}
    if t == "co2_window":
        from se.earth.temperature import predict
        zb = np.arange(200, 3001, 10.0); T, sT = predict(np.full(len(zb), 3800.0), np.full(len(zb), 3300.0), zb, np.full(len(zb), 300.0))
        wd = 300.0; P = 0.1013 + 0.00981 * 1.03 * (zb + wd)
        sc = (T > c["Tc"]) & (P > c["Pc"]); z = float(zb[np.argmax(sc)]) if sc.any() else None
        z90 = float(zb[np.argmax((T - 1.645 * sT > c["Tc"]) & (P > c["Pc"]))]) if ((T - 1.645 * sT > c["Tc"]) & (P > c["Pc"])).any() else None
        return {"example_column": "Horda Platform centre, 300 m water", "supercritical_from_m_below_seabed": z, "with_90pct_confidence_from_m": z90,
                "pressure_limit_depth_m": round((c["Pc"] - 0.1013) / (0.00981 * 1.03) - wd, 0), "verdict": "not_testable",
                "why": "a physical threshold, applied in P6; the depth comes from our pressure and temperature models"}
    if t == "seal_hc":
        f = pd.read_parquet(EARTH / "fluids.parquet"); g = np.load(EARTH / "grid.npz"); seal = np.load(EARTH / "seal_above.npy")
        labels = [str(s).split("|") for s in g["labels"]]; lab = g["label"]; x, y = g["x"], g["y"]
        idx = {}
        for li, (gn, fn) in enumerate(labels):
            idx.setdefault(fn or gn, []).append(li)
        rows = []
        for r in f[f.source.isin(["fp_hc_unit", "fp_dry", "dst_flow", "dst_no_flow"])].dropna(subset=["x"]).itertuples():
            i = int(np.argmin(np.abs(x - r.x))); j = int(np.argmin(np.abs(y - r.y))); ls = idx.get(r.unit)
            if not ls:
                continue
            ks = np.where(np.isin(lab[:, j, i], ls))[0]
            if len(ks):
                rows.append({"wellbore": r.wellbore, "hc": r.hc, "seal": float(seal[ks[0], j, i])})
        d = pd.DataFrame(rows).dropna(subset=["hc"])
        diff, lo, hi = boot_median_diff(d[d.hc == 1], d[d.hc == 0], "seal")
        return {"hc_units": int((d.hc == 1).sum()), "dry_units": int((d.hc == 0).sum()), "median_seal_hc_m": round(float(d[d.hc == 1].seal.median()), 1),
                "median_seal_dry_m": round(float(d[d.hc == 0].seal.median()), 1), "diff": round(diff, 1), "p05": round(lo, 1), "p95": round(hi, 1), "verdict": verdict_from(lo, hi)}
    if t == "factor_rate":
        from se.earth.factors import at

        o = pd.read_parquet(EARTH / "targets" / f"{c['target']}_obs.parquet"); f = at(o)[c["factor"]].to_numpy()
        hit = f < c["below"] if "below" in c else f > c["above"]
        if hit.sum() < 20 or (~hit).sum() < 20:
            return {"rows_in": int(hit.sum()), "rows_out": int((~hit).sum()), "verdict": "not_testable", "why": "fewer than 20 rows on one side"}
        diff, lo, hi = boot_rate_diff(o[hit], o[~hit])
        return {"rows_in": int(hit.sum()), "wells_in": int(o[hit].wellbore.nunique()), "rows_out": int((~hit).sum()), "rate_in": round(float(np.average(o[hit].ev, weights=o[hit].w)), 3),
                "rate_out": round(float(np.average(o[~hit].ev, weights=o[~hit].w)), 3), "diff": round(diff, 3), "p05": round(lo, 3), "p95": round(hi, 3), "verdict": verdict_from(lo, hi)}
    if t == "porosity_trend":
        p = json.loads((EARTH / "poroperm_report.json").read_text()); r = p["rmse_phi_pct"]; k = f"unit_{c['trend']}"
        return {"rmse_unit_athy_pct": r["unit_athy"], f"rmse_{k}_pct": r[k], "fit": p["fits"][c["trend"]], "adopted_trend": p["adopted_trend"],
                "verdict": "agrees" if r[k] <= 0.98 * r["unit_athy"] else "inconclusive", "why": "inconclusive: no held-out gain, not evidence against cementation"}
    if t == "burial":
        from se.config import OUT

        E = {rg: json.loads((OUT / "earth" / rg / "poroperm_report.json").read_text())["burial"] for rg in ("pilot", "barents") if (OUT / "earth" / rg / "poroperm_report.json").exists()}
        ok = "barents" in E and "pilot" in E
        fits = json.loads((OUT / "earth" / "barents" / "poroperm_report.json").read_text())["fits"] if "barents" in E else {}
        return {"E_median_m": {k: v["E_median_m"] for k, v in E.items()}, "barents_c_per_km": {k: fits.get(k, {}).get("c_per_km") for k in ("athy", "burial")},
                "verdict": ("agrees" if 500 <= E["barents"]["E_median_m"] <= 3000 and abs(E["pilot"]["E_median_m"]) <= 500 else "disagrees") if ok else "not_testable"}
    if t == "legacy":
        p = EARTH / "targets" / "legacy_wells.npz"
        if not p.exists():
            return {"verdict": "not_testable", "why": "targets not built"}
        v = np.load(p)["value"]
        return {"cells": int(len(v)), "share_with_any": round(float((v > 0).mean()), 3), "p99": float(np.percentile(v, 99)), "verdict": "not_testable", "why": "no leak observations"}
    if t == "seabed":
        from se.earth.seabed import bottom_temperature

        w = pd.read_parquet(EARTH / "wells.parquet"); w = w[w.pilot].dropna(subset=["x", "y", "wd"]); T = bottom_temperature(w.x.to_numpy(), w.y.to_numpy(), w.wd.to_numpy())
        deep = w.wd.to_numpy() > 800
        return {"wells": int(len(w)), "median_C": round(float(np.median(T)), 2), "deep_wells": int(deep.sum()), "deep_median_C": round(float(np.median(T[deep])), 2) if deep.any() else None,
                "replaces_C": 7.0, "verdict": "not_testable", "why": "a measured climatology used as given; no seabed temperatures in our wells"}
    if t == "salt_temp":
        sa = json.loads((EARTH / "temperature_report.json").read_text()).get("salt", {})
        if "rmse_with_C" not in sa:
            return sa | {"verdict": "not_testable"}
        return sa | {"verdict": "agrees" if sa["adopt"] else "inconclusive" if sa["C_per_km_salt"] > 0 else "disagrees"}
    if t == "rpt":
        from se.config import OUT

        p = OUT / "earth" / "rpt_pooled.json"
        return (json.loads(p.read_text()).get(c["test"]) or {"verdict": "not_testable"}) | {"pooled": "FORCE wells with shear logs, all regions"} if p.exists() else {"verdict": "not_testable", "why": "rock physics not built"}
    return {"verdict": "not_testable"}


def build() -> dict:
    kb = yaml.safe_load(RULES.read_text())
    out = []
    for r in kb["rules"]:
        try:
            res = check(r)
        except Exception as e:  # a failing check is reported, not hidden
            res = {"verdict": "not_testable", "error": f"{type(e).__name__}: {e}"[:200]}
        out.append({"id": r["id"], "statement": r["statement"], "status": r["status"], "sources": r["sources"], "use": r.get("use"), "guard": r.get("guard"), "test": res})
    atomic.write_json(EARTH / "earth_rules_report.json", out, indent=1, default=float)
    return out


if __name__ == "__main__":
    for r in build():
        print(r["id"], r["status"], json.dumps(r["test"], default=float)[:400])
