"""Temperature: geothermal gradient map with sigma (PLAN P3.4, LOG L062).

Data: FactPages DST downhole temperatures in the pilot (pressure_obs.parquet, any pressure QC: temperature does not depend on it).
Model: T(z) = T0 + g(x, y) * (z - water depth), z TVDSS, fitted over the DST depth range (about 1.0-4.8 km below the seabed). T0 is an
intercept, not the seabed temperature: a fixed 4-10 deg C seabed value fits worse on held-out blocks (12.7-13.6 vs 11.3 deg C), because the
gradient is steeper in the shallow, shale-rich section. Above Z_MIN the profile is linear from the seabed temperature: the bottom-water
value of the World Ocean Atlas at the water depth (se/earth/seabed.py, P9.4); a fixed SEABED_C only when no water depth is given.
The lateral variation of g by a GP. Test: held-out 40 km blocks vs one constant gradient. Report BHT (P5) would add many more points.
Salt (P9.7): rock salt conducts heat about three times better than shale, so the section above a thick salt is warmer. Candidate: a
term in the Zechstein thickness of the column (km); adopted only if it lowers the held-out error by 5 percent.
"""
import json

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from se.config import EARTH
from se.earth import manifest
from se.earth.folds import blocks
from se.earth.gp import GP

Z90 = 1.645
SEABED_C = 7.0  # North Sea bottom water, assumption used only above the DST depth range
Z_MIN = 1000.0




def observations() -> pd.DataFrame:
    o = pd.read_parquet(EARTH / "pressure_obs.parquet")
    w = pd.read_parquet(EARTH / "wells.parquet").set_index("wellbore").wd
    t = o[(o.kind == "pore") & (o.temp_C > 0)].copy()
    t["wd"] = t.wellbore.map(w)
    t["zb"] = t.tvdss - t.wd  # depth below seabed
    t = t[t.zb > 50]
    # one value per well and depth: repeated tests at one interval are not independent
    return t.groupby(["wellbore", t.md.round(-1)]).agg(x=("x", "first"), y=("y", "first"), zb=("zb", "mean"), T=("temp_C", "mean")).reset_index()


def fit_const(t):
    A = np.c_[np.ones(len(t)), t.zb]
    T0, g = np.linalg.lstsq(A, t["T"].to_numpy(), rcond=None)[0]
    return float(T0), float(g)


def salt_km(x, y) -> np.ndarray:
    """Zechstein (rock salt) thickness of the nearest grid column, km (0 where there is none)."""
    from se.earth.grid import at_columns, thickness_map

    th = thickness_map(lambda s: s.startswith("ZECHSTEIN GP"))
    return at_columns(th, np.asarray(x, float), np.asarray(y, float)) / 1000 if th.any() else np.zeros(np.shape(x))


def salt_test(t, bl) -> dict:
    """Held-out blocks: constant-gradient model with and without a linear term in salt thickness (only points above the salt)."""
    s = salt_km(t.x.to_numpy(), t.y.to_numpy())
    if (s > 0.05).sum() < 10:
        return {"salt_points": int((s > 0.05).sum()), "adopt": False, "why": "fewer than 10 temperature points over salt"}
    e0, e1 = [], []
    for tr, te in GroupKFold(min(5, len(np.unique(bl)))).split(t, groups=bl):
        a, b = t.iloc[tr], t.iloc[te]
        A = np.c_[np.ones(len(a)), a.zb, s[tr]]; c = np.linalg.lstsq(A, a["T"].to_numpy(), rcond=None)[0]
        T0f, gf = fit_const(a)
        e0 += list(T0f + gf * b.zb - b["T"]); e1 += list(c[0] + c[1] * b.zb + c[2] * s[te] - b["T"])
    A = np.c_[np.ones(len(t)), t.zb, s]; c = np.linalg.lstsq(A, t["T"].to_numpy(), rcond=None)[0]
    r0, r1 = float(np.sqrt(np.mean(np.square(e0)))), float(np.sqrt(np.mean(np.square(e1))))
    return {"salt_points": int((s > 0.05).sum()), "rmse_without_C": round(r0, 2), "rmse_with_C": round(r1, 2), "C_per_km_salt": round(float(c[2]), 2),
            "adopt": bool(r1 <= 0.95 * r0 and c[2] > 0)}


def build() -> dict:
    t = observations()
    T0, g = fit_const(t)
    bl = blocks(t.x.to_numpy(), t.y.to_numpy())
    e_c, e_g, zs, fo = [], [], [], []
    for f, (tr, te) in enumerate(GroupKFold(min(5, len(np.unique(bl)))).split(t, groups=bl)):
        a, b = t.iloc[tr], t.iloc[te]
        T0f, gf = fit_const(a)
        e_c += list(T0f + gf * b.zb - b["T"])
        ga = (a["T"] - T0f) / a.zb  # local gradient (deg C per m) at each training point
        gp = GP(0, ell_bounds=(5.0, 300.0)).fit(a[["x", "y"]].to_numpy(), ga.to_numpy() * 1000, np.full(len(a), (3.0 / a.zb.to_numpy() * 1000) ** 2))  # 3 deg C reading error
        m, v = gp.predict(b[["x", "y"]].to_numpy(), latent=False)
        pred = T0f + m / 1000 * b.zb; sd = np.sqrt(v) / 1000 * b.zb
        e_g += list(pred - b["T"]); zs += list((pred - b["T"]) / np.sqrt(sd ** 2 + 9.0)); fo += [f] * len(b)
    zs, fo = np.array(zs), np.array(fo); inside = []
    for f in np.unique(fo):
        kf = max(1.0, float(np.percentile(np.abs(zs[fo != f]), 90)) / Z90); inside += list(np.abs(zs[fo == f]) <= Z90 * kf)
    rm = lambda e: round(float(np.sqrt(np.mean(np.square(e)))), 2)
    out = {"points": int(len(t)), "wells": int(t.wellbore.nunique()), "T0_C": round(T0, 2), "gradient_C_per_km": round(g * 1000, 2),
           "rmse_const_C": rm(e_c), "rmse_gp_C": rm(e_g), "cover90_nested": round(float(np.mean(inside)), 3),
           "inflation": round(max(1.0, float(np.percentile(np.abs(zs), 90)) / Z90), 3),
           "adopt_gp": bool(rm(e_g) <= 0.95 * rm(e_c)), "depth_range_below_seabed_m": [round(float(t.zb.min())), round(float(t.zb.max()))],
           "salt": salt_test(t, bl)}
    (EARTH / "temperature_report.json").write_text(json.dumps(out, indent=1))
    t.to_parquet(EARTH / "temperature_obs.parquet")
    manifest.write(EARTH / "temperature_obs.parquet", [EARTH / "pressure_obs.parquet", EARTH / "wells.parquet"], {"reading_sd_C": 3.0})
    return out


def predict(x, y, zb, wd=None) -> tuple[np.ndarray, np.ndarray]:
    """Temperature (deg C) and sigma at points (3035 km, depth below seabed m, water depth m), from the adopted model."""
    t = pd.read_parquet(EARTH / "temperature_obs.parquet"); r = json.loads((EARTH / "temperature_report.json").read_text())
    T0, g = r["T0_C"], r["gradient_C_per_km"] / 1000
    zb = np.asarray(zb, float); zc = np.maximum(zb, Z_MIN)
    if not r["adopt_gp"]:
        T, sd = T0 + g * zc, np.full(zb.shape, r["rmse_const_C"] * r["inflation"])
    else:
        gp = GP(0, ell_bounds=(5.0, 300.0)).fit(t[["x", "y"]].to_numpy(), ((t["T"] - T0) / t.zb * 1000).to_numpy(), (3.0 / t.zb.to_numpy() * 1000) ** 2)
        m, v = gp.predict(np.c_[np.ravel(x), np.ravel(y)])
        T, sd = T0 + m.reshape(zb.shape) / 1000 * zc, np.sqrt(np.sqrt(v).reshape(zb.shape) ** 2 / 1e6 * zc ** 2 + 9.0) * r["inflation"]
    sa = r.get("salt", {})
    if sa.get("adopt"):
        T = T + sa["C_per_km_salt"] * salt_km(x, y)
    if wd is None:
        sb = SEABED_C
    else:
        from se.earth.seabed import bottom_temperature

        sb = bottom_temperature(np.broadcast_to(x, zb.shape), np.broadcast_to(y, zb.shape), np.broadcast_to(wd, zb.shape))
    shallow = zb < Z_MIN  # above the data: straight line from the seabed temperature to the model value at Z_MIN
    return np.where(shallow, sb + (T - sb) * zb / Z_MIN, T), sd


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
