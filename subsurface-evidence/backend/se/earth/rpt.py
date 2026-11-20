"""Rock physics template on the FORCE wells with shear logs (PLAN P11.1, LOG L077).

A rock physics template (Odegaard and Avseth 2004) is the cross-plot of acoustic impedance (AI = Vp x density) against Vp/Vs with model
lines for porosity, cementation and pore fluid. Here it is built from published models and used to test two things the earth model could
not settle from depth alone:
  cementation  measured shear modulus (Vs is almost blind to the pore fluid) against two dry-rock end members at the sample's porosity:
               friable sand (Hertz-Mindlin contact theory at critical porosity + modified lower Hashin-Shtrikman, the "soft sand" model)
               and contact cement (Dvorkin and Nur 1996, quartz cement at the grain contacts). Cement index = where the sample lies between
               them (0 friable, 1 cemented). Test R-RPT-CEMENT: the index rises above about 70-80 C (quartz cement, R-QTZ).
  fluid        the sample's dry frame (from its shear modulus and the K/G ratio of the end members at its cement index) with brine by
               Gassmann (1951); the softening against that brine prediction, dAI = AI_obs - AI_brine, is the fluid signal. Test R-RPT-FLUID:
               well-units with hydrocarbons (FactPages HC formations, DST) are softer than dry ones, resampling whole wells.
Validity: both end members describe clean, high-porosity sands, so the tests use sandstone samples with density porosity 15-37 percent
and clay share below 0.3 (VALID); tight or shaly samples (cracks, clay coats) fall below the friable line and are only plotted.
Inputs per sample: DTC, DTS (us/ft), RHOB (g/cm3), GR (clay share by a per-well linear GR index), TVDSS from FORCE Z, temperature from
P3.4 for the brine. Sandstone samples only (FORCE lithology 65000 and 65030) for the tests; all lithologies on the plot.
Mineral and fluid moduli are textbook values (Mavko, Mukerji and Dvorkin, The Rock Physics Handbook): quartz K 36.6, G 45 GPa, 2.65 g/cm3;
clay K 21, G 7, 2.58; brine K 2.6 GPa, 1.04 g/cm3; oil K 1.0, 0.80; gas K 0.1, 0.25. Critical porosity 0.40, coordination number 8.6,
effective pressure (2.3 - 1.03) g z below the seabed. Sonic logs read the invaded zone near the hole, so oil is muted; gas shows most.
"""
import json

import numpy as np
import pandas as pd

from se.config import EARTH
from se.earth import atomic, manifest

QZ, CL = (36.6, 45.0, 2.65), (21.0, 7.0, 2.58)
FLUIDS = {"brine": (2.6, 1.04), "oil": (1.0, 0.80), "gas": (0.1, 0.25)}
PHI_C, N_C = 0.40, 8.6
SAND = (65000, 65030)  # FORCE lithofacies: sandstone, sandstone/shale
VALID = {"phi": (0.15, 0.37), "clay_max": 0.35}
T_COOL, T_HOT = 70.0, 90.0  # set from the theory before testing (cement onset 70-80 C, Walderhaug 1996), not from the data
US_FT = 304800.0  # us/ft -> m/s


def vrh(f_cl):
    """Voigt-Reuss-Hill mineral moduli (GPa) and density of a quartz-clay mix."""
    f = np.clip(f_cl, 0, 1); fq = 1 - f
    Kv, Gv = fq * QZ[0] + f * CL[0], fq * QZ[1] + f * CL[1]; Kr, Gr = 1 / (fq / QZ[0] + f / CL[0]), 1 / (fq / QZ[1] + f / CL[1])
    return (Kv + Kr) / 2, (Gv + Gr) / 2, fq * QZ[2] + f * CL[2]


def hertz_mindlin(K, G, P):
    """Contact moduli (GPa) of a random pack at critical porosity; P is the effective pressure in MPa (converted: the moduli are in GPa)."""
    P = np.asarray(P, float) / 1000.0
    nu = (3 * K - 2 * G) / (2 * (3 * K + G))
    Kh = (N_C ** 2 * (1 - PHI_C) ** 2 * G ** 2 * P / (18 * np.pi ** 2 * (1 - nu) ** 2)) ** (1 / 3)
    Gh = (5 - 4 * nu) / (5 * (2 - nu)) * (3 * N_C ** 2 * (1 - PHI_C) ** 2 * G ** 2 * P / (2 * np.pi ** 2 * (1 - nu) ** 2)) ** (1 / 3)
    return Kh, Gh


def friable(phi, K, G, P):
    """Soft-sand dry moduli: Hertz-Mindlin at critical porosity, modified lower Hashin-Shtrikman bound to the mineral."""
    Kh, Gh = hertz_mindlin(K, G, P); a = np.clip(phi / PHI_C, 0, 1); z = Gh / 6 * (9 * Kh + 8 * Gh) / (Kh + 2 * Gh)
    Kd = 1 / (a / (Kh + 4 / 3 * Gh) + (1 - a) / (K + 4 / 3 * Gh)) - 4 / 3 * Gh
    Gd = 1 / (a / (Gh + z) + (1 - a) / (G + z)) - z
    return Kd, Gd


def contact_cement(phi, K, G):
    """Dvorkin-Nur contact-cement dry moduli, quartz cement deposited evenly on the grains (scheme 2), porosity reduced from critical."""
    Kc, Gc = QZ[0], QZ[1]; nu = (3 * K - 2 * G) / (2 * (3 * K + G)); nuc = (3 * Kc - 2 * Gc) / (2 * (3 * Kc + Gc))
    alpha = np.sqrt(np.clip(2 / 3 * (PHI_C - phi) / (1 - PHI_C), 1e-6, None))
    Ln = 2 * Gc * (1 - nu) * (1 - nuc) / (np.pi * G * (1 - 2 * nuc)); Lt = Gc / (np.pi * G)
    Sn = -0.024153 * Ln ** -1.3646 * alpha ** 2 + 0.20405 * Ln ** -0.89008 * alpha + 0.00024649 * Ln ** -1.9864
    At = -1e-2 * (2.26 * nu ** 2 + 2.07 * nu + 2.3) * Lt ** (0.079 * nu ** 2 + 0.1754 * nu - 1.342)
    Bt = (0.0573 * nu ** 2 + 0.0937 * nu + 0.202) * Lt ** (0.0274 * nu ** 2 + 0.0529 * nu - 0.8765)
    Ct = 1e-4 * (9.654 * nu ** 2 + 4.945 * nu + 3.1) * Lt ** (0.01867 * nu ** 2 + 0.4011 * nu - 1.8186)
    St = At * alpha ** 2 + Bt * alpha + Ct; Mc = Kc + 4 / 3 * Gc
    Kd = N_C * (1 - PHI_C) * Mc * Sn / 6; Gd = 3 / 5 * Kd + 3 / 20 * N_C * (1 - PHI_C) * Gc * St
    return Kd, Gd


def gassmann(Kd, K, phi, Kf):
    return Kd + (1 - Kd / K) ** 2 / (phi / Kf + (1 - phi) / K - Kd / K ** 2)


def velocities(Kd, Gd, K, rho_m, phi, fluid):
    Kf, rf = FLUIDS[fluid] if isinstance(fluid, str) else fluid; Ks = gassmann(Kd, K, phi, Kf); rho = rho_m * (1 - phi) + rf * phi
    return np.sqrt((Ks + 4 / 3 * Gd) / rho) * 1000, np.sqrt(Gd / rho) * 1000, rho  # m/s, g/cm3


def template(P=25.0, clay=(0.0, 0.3)) -> list[dict]:
    """Model lines for the plot: porosity 5-40 percent, friable and contact cement, brine / oil / gas, clean and shaly sand."""
    phi = np.linspace(0.05, 0.39, 18); out = []
    for c in clay:
        K, G, rm = vrh(np.full_like(phi, c))
        for model, (Kd, Gd) in (("friable sand", friable(phi, K, G, P)), ("contact cement", contact_cement(phi, K, G))):
            for fl in FLUIDS:
                vp, vs, rho = velocities(Kd, Gd, K, rm, phi, fl)
                out.append({"model": model, "fluid": fl, "clay": c, "phi": phi.round(3).tolist(), "ai": (vp * rho / 1000).round(3).tolist(), "vpvs": (vp / vs).round(3).tolist()})
    return out


def samples() -> pd.DataFrame:
    from se.earth.frame import FORCE_TRAIN, UTM31_TO_3035
    from se.ingest.names import norm

    f = pd.read_csv(FORCE_TRAIN, sep=";", usecols=["WELL", "DEPTH_MD", "X_LOC", "Y_LOC", "Z_LOC", "DTC", "DTS", "RHOB", "GR", "FORMATION", "GROUP", "FORCE_2020_LITHOFACIES_LITHOLOGY"])
    f = f.dropna(subset=["DTC", "DTS", "RHOB", "GR", "X_LOC", "Y_LOC", "Z_LOC"]); f["wellbore"] = f.WELL.map(norm)
    w = pd.read_parquet(EARTH / "wells.parquet").set_index("wellbore"); f = f[f.wellbore.isin(set(w.index[w.pilot]))]
    f = f[(f.DTC.between(40, 200)) & (f.DTS.between(60, 600)) & (f.RHOB.between(1.6, 3.0))]  # physical ranges (bad-hole and spikes out)
    f = f.assign(m=(f.DEPTH_MD / 2).round()).drop_duplicates(["wellbore", "m"])  # one sample per 2 m: neighbouring samples are not independent
    x, y = UTM31_TO_3035.transform(f.X_LOC.to_numpy(), f.Y_LOC.to_numpy())
    from se.earth.lithology import unit_name

    g = f.groupby("wellbore").GR; lo, hi = g.transform(lambda s: s.quantile(0.05)), g.transform(lambda s: s.quantile(0.95))
    d = pd.DataFrame({"wellbore": f.wellbore.to_numpy(), "md": f.DEPTH_MD.to_numpy(), "x": x / 1000, "y": y / 1000, "tvdss": -f.Z_LOC.to_numpy(),
                      "vp": US_FT / f.DTC.to_numpy(), "vs": US_FT / f.DTS.to_numpy(), "rho": f.RHOB.to_numpy(), "clay": np.clip((f.GR - lo) / (hi - lo).clip(lower=1), 0, 1).to_numpy(),
                      "lith": f.FORCE_2020_LITHOFACIES_LITHOLOGY.to_numpy(), "unit": f.FORMATION.map(unit_name).fillna(f.GROUP.map(unit_name)).to_numpy()})
    d["wd"] = d.wellbore.map(w.wd); d["zb"] = d.tvdss - d.wd
    return d[d.zb > 100].reset_index(drop=True)


def place(d: pd.DataFrame) -> pd.DataFrame:
    """Porosity, cement index and fluid signal per sample (see the module doc)."""
    from se.earth.temperature import predict

    K, G, rm = vrh(d.clay.to_numpy()); T = predict(d.x.to_numpy(), d.y.to_numpy(), d.zb.to_numpy(), d.wd.to_numpy())[0]
    rf = FLUIDS["brine"][1]; phi = np.clip((rm - d.rho.to_numpy()) / (rm - rf), 0.01, PHI_C - 0.01)  # density porosity, brine-filled assumption
    P = (2.3 - 1.03) * 9.81 * d.zb.to_numpy() / 1000  # MPa
    G_obs = d.rho.to_numpy() * (d.vs.to_numpy() / 1000) ** 2  # GPa: the frame's shear modulus (fluid does not carry shear)
    Kf_, Gf_ = friable(phi, K, G, P); Kc_, Gc_ = contact_cement(phi, K, G)
    ci = np.clip((G_obs - Gf_) / np.maximum(Gc_ - Gf_, 1e-6), -0.5, 1.5)
    w = np.clip(ci, 0, 1); kg = (1 - w) * Kf_ / Gf_ + w * Kc_ / Gc_  # dry K/G ratio between the end members
    vp_b, _, rho_b = velocities(kg * G_obs, G_obs, K, rm, phi, "brine")
    ai, ai_b = d.vp.to_numpy() * d.rho.to_numpy() / 1000, vp_b * rho_b / 1000
    return d.assign(T=T, phi=phi, ai=ai, vpvs=d.vp / d.vs, cement=ci, ai_brine=ai_b, dai=(ai - ai_b) / ai_b, sand=d.lith.isin(SAND))


def build() -> dict:
    from se.earth.rules import boot_median_diff, verdict_from

    d = samples()
    if d.wellbore.nunique() < 5:
        from se.earth.run import Skip
        raise Skip(f"only {d.wellbore.nunique()} FORCE wells with shear logs in this region")
    d = place(d); d["valid"] = d.sand & d.phi.between(*VALID["phi"]) & (d.clay < VALID["clay_max"]); s = d[d.valid]
    # cementation against temperature: whole wells resampled; median cement index hot (> 80 C) minus cool (< 60 C)
    hot, cool = s[s["T"] >= T_HOT], s[s["T"] <= T_COOL]
    cem = boot_median_diff(hot, cool, "cement") if len(hot) > 100 and len(cool) > 100 and hot.wellbore.nunique() >= 3 and cool.wellbore.nunique() >= 3 else None
    bins = pd.cut(s["T"], [0, 40, 60, 70, 80, 90, 100, 120, 200])
    by_T = s.groupby(bins, observed=True).agg(n=("cement", "size"), wells=("wellbore", "nunique"), cement=("cement", "median"), phi=("phi", "median"), dai=("dai", "median")).reset_index()
    by_T["T"] = by_T["T"].astype(str)
    # fluid: per well-unit median softening against the FactPages / DST hydrocarbon label of that unit
    fl = pd.read_parquet(EARTH / "fluids.parquet"); fl = fl[fl.source.isin(["fp_hc_unit", "dst_flow", "fp_dry", "dst_no_flow", "fp_not_listed"])]
    lab = fl.groupby(["wellbore", "unit"]).agg(hc=("hc", "max"), fluid=("fluid", "first")).reset_index()
    wu = s.groupby(["wellbore", "unit"]).agg(dai=("dai", "median"), cement=("cement", "median"), n=("dai", "size")).reset_index().merge(lab, on=["wellbore", "unit"], how="inner")
    wu = wu[wu.n >= 10]
    fluid = None
    if (wu.hc == 1).sum() >= 8 and (wu.hc == 0).sum() >= 8:
        diff, lo_, hi_ = boot_median_diff(wu[wu.hc == 1], wu[wu.hc == 0], "dai")
        from sklearn.metrics import roc_auc_score

        fluid = {"hc_units": int((wu.hc == 1).sum()), "dry_units": int((wu.hc == 0).sum()), "median_dai_hc": round(float(wu[wu.hc == 1].dai.median()), 4),
                 "median_dai_dry": round(float(wu[wu.hc == 0].dai.median()), 4), "diff": round(diff, 4), "p05": round(lo_, 4), "p95": round(hi_, 4),
                 "auc_softer_means_hc": round(float(roc_auc_score(wu.hc, -wu.dai)), 3), "verdict": verdict_from(lo_, hi_, want="-"),
                 "gas_units": int((wu.fluid == "gas").sum()), "median_dai_gas": round(float(wu[wu.fluid == "gas"].dai.median()), 4) if (wu.fluid == "gas").any() else None}
    out = {"wells": int(d.wellbore.nunique()), "samples": int(len(d)), "sand_samples": int(d.sand.sum()), "valid_samples": int(len(s)), "valid_wells": int(s.wellbore.nunique()),
           "validity": VALID, "share_sand_softer_than_friable_outside_validity": round(float((d[d.sand & ~d.valid].cement < 0).mean()), 3) if (d.sand & ~d.valid).any() else None,
           "template_pressure_MPa": 25.0,
           "cement_index": {"median": round(float(s.cement.median()), 3), "share_cemented_gt_0.5": round(float((s.cement > 0.5).mean()), 3)},
           "cement_vs_temperature": by_T.round(4).to_dict("records"),
           "cement_test": ({"hot_minus_cool": round(cem[0], 3), "p05": round(cem[1], 3), "p95": round(cem[2], 3), "hot_samples": int(len(hot)), "cool_samples": int(len(cool)),
                            "verdict": verdict_from(cem[1], cem[2])} if cem else {"verdict": "not_testable", "why": f"too few samples on one side of {T_COOL:g} / {T_HOT:g} C in this region"}),
           "fluid_test": fluid or {"verdict": "not_testable", "why": "fewer than 8 labelled well-units on one side"},
           "phi_check": {"median_density_porosity_sand": round(float(s.phi.median()), 3)}}
    keep = d.sample(min(len(d), 40000), random_state=0) if len(d) > 40000 else d
    keep[["wellbore", "md", "tvdss", "unit", "lith", "sand", "valid", "clay", "phi", "T", "ai", "vpvs", "cement", "dai"]].to_parquet(EARTH / "rpt_samples.parquet")
    atomic.write_json(EARTH / "rpt_report.json", {**out, "template": template()}, indent=1, default=float)
    manifest.write(EARTH / "rpt_samples.parquet", [EARTH / "wells.parquet", EARTH / "fluids.parquet"], {"phi_c": PHI_C, "n": N_C})
    out["pooled"] = {k: v.get("verdict") for k, v in pooled().items() if isinstance(v, dict) and "verdict" in v}  # all FORCE wells together (the tests' main result)
    return out


def pooled(regions=("pilot", "north_sea_south")) -> dict:
    """The same tests on the FORCE wells of all regions together (the rock physics does not depend on the region; each sample keeps its own
    region's temperature and labels). Written to <OUT>/earth/rpt_pooled.json; the API shows it beside each region's own numbers."""
    from se.config import OUT
    from se.earth.rules import boot_median_diff, verdict_from

    parts = [pd.read_parquet(OUT / "earth" / r / "rpt_samples.parquet").assign(region=r) for r in regions if (OUT / "earth" / r / "rpt_samples.parquet").exists()]
    labs = []
    for r in regions:
        f = OUT / "earth" / r / "fluids.parquet"
        if f.exists():
            fl = pd.read_parquet(f); fl = fl[fl.source.isin(["fp_hc_unit", "dst_flow", "fp_dry", "dst_no_flow", "fp_not_listed"])]
            labs.append(fl.groupby(["wellbore", "unit"]).agg(hc=("hc", "max"), fluid=("fluid", "first")).reset_index())
    if not parts:
        return {}
    d = pd.concat(parts).drop_duplicates(["wellbore", "md"]); s = d[d.valid]; out = {"regions": [p.region.iat[0] for p in parts], "wells": int(d.wellbore.nunique()), "valid_samples": int(len(s)),
                                                                                   "valid_wells": int(s.wellbore.nunique())}
    hot, cool = s[s["T"] >= T_HOT], s[s["T"] <= T_COOL]
    if len(hot) > 50 and len(cool) > 50 and hot.wellbore.nunique() >= 3 and cool.wellbore.nunique() >= 3:
        dlt, lo, hi = boot_median_diff(hot, cool, "cement")
        out["cement_test"] = {"hot_C": T_HOT, "cool_C": T_COOL, "median_hot": round(float(hot.cement.median()), 3), "median_cool": round(float(cool.cement.median()), 3), "hot_minus_cool": round(dlt, 3),
                              "p05": round(lo, 3), "p95": round(hi, 3), "hot_samples": int(len(hot)), "hot_wells": int(hot.wellbore.nunique()), "cool_samples": int(len(cool)),
                              "cool_wells": int(cool.wellbore.nunique()), "verdict": verdict_from(lo, hi)}
    else:
        out["cement_test"] = {"verdict": "not_testable", "why": "too few samples or wells on one side"}
    if labs:
        lab = pd.concat(labs).drop_duplicates(["wellbore", "unit"])
        wu = s.groupby(["wellbore", "unit"]).agg(dai=("dai", "median"), n=("dai", "size")).reset_index().merge(lab, on=["wellbore", "unit"])
        wu = wu[wu.n >= 5]
        if (wu.hc == 1).sum() >= 8 and (wu.hc == 0).sum() >= 8:
            from sklearn.metrics import roc_auc_score

            dlt, lo, hi = boot_median_diff(wu[wu.hc == 1], wu[wu.hc == 0], "dai")
            out["fluid_test"] = {"hc_units": int((wu.hc == 1).sum()), "dry_units": int((wu.hc == 0).sum()), "median_dai_hc": round(float(wu[wu.hc == 1].dai.median()), 4),
                                 "median_dai_dry": round(float(wu[wu.hc == 0].dai.median()), 4), "diff": round(dlt, 4), "p05": round(lo, 4), "p95": round(hi, 4),
                                 "auc_softer_means_hc": round(float(roc_auc_score(wu.hc, -wu.dai)), 3), "verdict": verdict_from(lo, hi, want="-")}
        else:
            out["fluid_test"] = {"verdict": "not_testable", "why": f"labelled well-units: {int((wu.hc == 1).sum())} with HC, {int((wu.hc == 0).sum())} dry (need 8 each)"}
    T = pd.cut(s["T"], [0, 60, 70, 80, 90, 100, 120, 200])
    out["cement_vs_temperature"] = s.groupby(T, observed=True).agg(n=("cement", "size"), wells=("wellbore", "nunique"), cement=("cement", "median"), phi=("phi", "median")).reset_index().assign(T=lambda x: x["T"].astype(str)).round(3).to_dict("records")
    atomic.write_json(OUT / "earth" / "rpt_pooled.json", out, indent=1, default=float)
    return out


if __name__ == "__main__":
    import sys

    print(json.dumps(pooled() if "pooled" in sys.argv else build(), indent=1, default=float))
