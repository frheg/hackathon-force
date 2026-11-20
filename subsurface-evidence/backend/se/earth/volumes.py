"""Porosity per cell and CO2 storage capacity, with an outside check (PLAN P10.4, LOG L076).

Porosity: the adopted P3.2 / P9.2 model (compaction trend + unit offset + neighbouring wells) in every cell, sigma from its held-out error.
Capacity, as in Petrel volumetrics and the Sodir CO2 Storage Atlas: M = bulk volume x net-to-gross x porosity x CO2 density x E x w, where
  bulk      cell area x thickness (grid), thickness sd = half the group-top sigma (top and base errors assumed strongly correlated, rho 0.875)
  NTG       the cell's sand share (lithology, P3.1), sd 0.1
  porosity  above, sd = held-out RMSE
  density   NIST Span-Wagner CO2 density at the cell's temperature (P3.4) and hydrostatic pressure at its mid depth (data/nist_co2)
  E         storage efficiency, lognormal through the NETL clastic saline-formation P10 / P50 / P90 of 0.51 / 2.0 / 5.4 percent, one draw per
            unit and realisation (the efficiency of an aquifer is one unknown number, not independent per cell)
  w         P(reservoir) x P(T > 31.1 C) x P(P > 7.38 MPa) x P(seal >= 50 m) x (1 - P(overpressure)), as the CO2 target: only rock of
            reservoir quality (porosity > 15 %, permeability > 10 mD) with dense CO2 and a seal counts. Without P(reservoir) the Barents
            total came out near 300 Gt, every pore of thick tight Triassic units, against a few Gt in the atlas.
Uncertainty: N_REAL realisations with spatially correlated errors (Matern fields over the columns, P10.3); P10 / P50 / P90 per unit.
Check: the atlas's evaluated aquifers (data/sodir/co2_atlas). Their outlines are not our region boxes, so totals are compared with that
caveat; the intensive numbers (pore volume / bulk volume, density) compare directly. A capacity with the atlas's own efficiency and no w
is reported beside ours so the comparison is like for like.
"""
import json

import numpy as np
import pandas as pd

from se.config import DATA, EARTH
from se.earth import atomic, manifest

RHO = DATA / "nist_co2" / "co2_density.csv"
ATLAS = DATA / "sodir" / "co2_atlas" / "north_sea_aquifers.csv"
E_P10, E_P50, E_P90 = 0.0051, 0.020, 0.054
N_REAL, NTG_SD = 200, 0.1
OUT_T = EARTH / "targets"


def rho_co2(T, P) -> np.ndarray:
    """CO2 density (kg/m3) at T (C) and P (MPa), bilinear in the NIST table (clipped to its 0-200 C, 1-80 MPa range)."""
    from scipy.interpolate import RegularGridInterpolator

    t = pd.read_csv(RHO); t = t[np.isclose(t.P_MPa, t.P_MPa.round())]  # the regular 1 MPa steps; phase-boundary rows have their own pressures
    t = t.drop_duplicates(["T_C", "P_MPa"], keep="last").pivot(index="T_C", columns="P_MPa", values="rho_kg_m3")
    f = RegularGridInterpolator((t.index.to_numpy(float), t.columns.to_numpy(float)), t.to_numpy(float))
    return f(np.c_[np.clip(np.ravel(T), 0, 200), np.clip(np.ravel(P), 1, 80)]).reshape(np.shape(T))


def porosity(C: pd.DataFrame) -> tuple[np.ndarray, float]:
    from se.earth.poroperm import Model

    r = json.loads((EARTH / "poroperm_report.json").read_text()); m = Model(r.get("adopted_trend", "athy")).fit(pd.read_parquet(EARTH / "poroperm_wells.parquet"))
    phi = np.empty(len(C))
    for u, ix in C.groupby("unit").groups.items():
        q = C.loc[ix]; k = C.index.get_indexer(ix)
        phi[k] = m.predict(q[["x", "y"]].to_numpy(), q.zb.to_numpy(), u, "unit_athy", q.T_C.to_numpy())[0]
    return np.clip(phi, 0, 45), float(r["sigma_phi_pct"])


def realise(C, phi, sd_phi, rho, w, area, ntg_sd=NTG_SD, th_frac=0.5, eff=(E_P10, E_P50, E_P90), n=N_REAL) -> tuple[np.ndarray, pd.Index]:
    """Capacity realisations (n x units, Mt) with correlated errors in porosity, net-to-gross and thickness and one efficiency draw per
    unit. The constants are arguments so the sensitivity study (P12.1) can vary them."""
    from se.earth.folds import device
    from se.earth.gp import prior_field

    th, ntg = C.thick.to_numpy(), np.clip(C.sand.fillna(0).to_numpy(), 0, 1); sd_th = th_frac * C.zsd.to_numpy()
    col = pd.factorize(pd.Series(list(zip(C.i, C.j))))[0]; xy = C.groupby(col)[["x", "y"]].first().to_numpy()
    uid, units = pd.factorize(C.unit); nu = len(units)
    Fp, Fn, Ft = (prior_field(xy, ell, n, seed=s, features=1000, device=device()) for ell, s in ((15.0, 1), (25.0, 2), (20.0, 3)))
    rng = np.random.default_rng(0); s_ln = (np.log(eff[2]) - np.log(eff[0])) / (2 * 1.2816)
    cap = np.zeros((n, nu))
    for k in range(n):
        # thickness varies multiplicatively (lognormal, mean kept): clipping a normal draw at zero biased every total upwards, more so for a
        # larger sigma (found by the sensitivity study, P12.1: Barents P50 88 -> 155 Gt as the sigma doubled)
        sr = np.minimum(sd_th / np.maximum(th, 1.0), 1.0); t_ = th * np.exp(sr * Ft[col, k] - sr ** 2 / 2)
        ph = np.clip(phi + sd_phi * Fp[col, k], 0, 45) / 100; ng = np.clip(ntg + ntg_sd * Fn[col, k], 0, 1)
        E = np.exp(np.log(eff[1]) + s_ln * rng.standard_normal(nu))[uid]
        cap[k] = np.bincount(uid, area * t_ * ng * ph * rho * E * w, minlength=nu) / 1e9  # Mt
    return cap, units


def inputs(C):
    g = np.load(EARTH / "grid.npz"); area = float(np.diff(g["x"][:2])[0] * np.diff(g["y"][:2])[0]) * 1e6  # m2 per column
    mid = 0.5 * (C.top + C.base).to_numpy(); P = 0.1013 + 0.00981 * 1.03 * mid
    return area, rho_co2(C.T_C.to_numpy(), P), C.w_co2.to_numpy() * np.load(OUT_T / "reservoir.npz")["p"]


def build() -> dict:
    C = pd.read_parquet(OUT_T / "cells.parquet")
    phi, sd_phi = porosity(C)
    atomic.savez(OUT_T / "porosity.npz", value=phi.astype(np.float32), sd=np.full(len(C), sd_phi, np.float32))
    area, rho, w = inputs(C); th, ntg = C.thick.to_numpy(), np.clip(C.sand.fillna(0).to_numpy(), 0, 1)
    cap, units = realise(C, phi, sd_phi, rho, w, area); uid = pd.factorize(C.unit)[0]; nu = len(units)
    bulk = np.bincount(uid, area * th, minlength=nu); pore = np.bincount(uid, area * th * ntg * phi / 100, minlength=nu)
    dens = np.bincount(uid, area * th * ntg * phi / 100 * rho, minlength=nu) / np.maximum(pore, 1)
    elig = np.bincount(uid, area * th * ntg * phi / 100 * w, minlength=nu) / np.maximum(pore, 1)
    mean_cell = area * th * ntg * phi / 100 * rho * E_P50 * w / 1e6  # kt per cell at the median efficiency
    atomic.savez(OUT_T / "co2_capacity.npz", value=mean_cell.astype(np.float32), sd=np.zeros(len(C), np.float32))
    per = pd.DataFrame({"unit": units, "bulk_km3": bulk / 1e9, "pore_volume_rm3": pore, "pore_over_bulk": pore / np.maximum(bulk, 1), "density_t_rm3": dens / 1000,
                        "eligible_share": elig, "p10_mt": np.percentile(cap, 10, axis=0), "p50_mt": np.percentile(cap, 50, axis=0), "p90_mt": np.percentile(cap, 90, axis=0)})
    per = per[per.p90_mt > 0.5].sort_values("p50_mt", ascending=False)
    atlas = []
    if ATLAS.exists():
        a = pd.read_csv(ATLAS)
        for r in a.dropna(subset=["units"]).itertuples():
            names = r.units.split("|"); m = (C.unit.isin(names) | C.group.isin(names)).to_numpy()  # a name is a formation or a group
            if not m.any():
                continue
            us = sorted(set(C.unit[m])); pv = float((area * th * ntg * phi / 100)[m].sum())
            atlas.append({"aquifer": r.aquifer, "our_units": sorted(set(us)), "atlas_pore_volume_rm3": r.pore_volume_rm3, "our_pore_volume_rm3": round(pv, -8),
                          "atlas_pore_over_bulk": round(r.pore_volume_rm3 / r.bulk_volume_rm3, 3) if r.bulk_volume_rm3 == r.bulk_volume_rm3 else None,
                          "our_pore_over_bulk": round(pv / max(float((area * th)[m].sum()), 1), 3),
                          "atlas_density_t_rm3": r.density_t_rm3, "our_density_t_rm3": round(float((area * th * ntg * phi / 100 * rho)[m].sum() / max(pv, 1) / 1000), 3),
                          "atlas_capacity_gt": r.capacity_gt, "our_capacity_at_atlas_E_gt": round(float((area * th * ntg * phi / 100 * rho)[m].sum() * r.storage_eff_pct / 100 / 1e12), 2),
                          "our_capacity_p50_gt": round(float(cap[:, [list(units).index(u) for u in set(us)]].sum(1).mean() / 1000), 3)})
    out = {"realisations": N_REAL, "efficiency": {"p10": E_P10, "p50": E_P50, "p90": E_P90, "source": "NETL clastic saline formations (IEA 2009; Gorecki 2009)"},
           "total_mt": {"p10": round(float(np.percentile(cap.sum(1), 10))), "p50": round(float(np.percentile(cap.sum(1), 50))), "p90": round(float(np.percentile(cap.sum(1), 90)))},
           "units": per.head(15).round(4).to_dict("records"), "atlas": atlas, "porosity_sigma_pct": sd_phi,
           "caveat": "atlas aquifer outlines differ from the region box: compare pore/bulk and density directly, totals only as orders of magnitude"}
    atomic.write_json(OUT_T / "co2_capacity.json", out, indent=1, default=float)
    manifest.write(OUT_T / "co2_capacity.npz", [OUT_T / "cells.parquet", RHO, ATLAS], {"n_real": N_REAL, "E": [E_P10, E_P50, E_P90]})
    return out


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=float)[:3000])
