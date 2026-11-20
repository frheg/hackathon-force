"""Frame: where each sample really is. Measured depth (MD, m below rig floor) -> x, y (EPSG:3035 km), TVDSS (m below sea level, + down), sigmas.

Sources, best first (PLAN P1.1, LOG L055):
  force    FORCE 2020 train logs: X/Y (ED50 UTM 31N, checked: 6 m median from FactPages wellheads) and Z = -TVDSS per sample.
  factpages  wellhead (ED50), rig-floor height (KB), TD, TVD at TD, kick-off point. Direction is unknown, so the position stays at the
           wellhead and the lateral offset becomes an uncertainty radius. The depth model is chosen by measured error on FORCE wells.
  estimated no TVD at TD (1,032 NCS wellbores, mostly sidetracks): TVD at TD estimated from FactPages wells that have both (P10, owner
           question on 25/1-14 G: MD 10,444 m, drawn 10 km deep while the reservoir is at about 2.2 km).
           sidetrack of a parent with a known or estimated TVD: parent TVD + the median sidetrack-parent difference (1,798 pairs: -58 m,
           5-95 percent -432 to +317 m); else TVD = MD x the median TVD/MD ratio of wells of the same kind, sidetrack or not, and MD band.
           sigma from the 5-95 percent spread of the calibration set (/ 3.29). Then the 'kop' / 'ratio' path to that TVD.
  vertical  no TVD and no estimate (no TD): TVD = MD, with a sigma calibrated on FORCE wells; flagged.
TVDSS = TVD below rig floor - KB (checked: FORCE MD + Z = KB, median 0.0 m).
"""
import json
import time

import duckdb
import numpy as np
import pandas as pd
from pyproj import Transformer

from se.config import DATA, EARTH, in_pilot
from se.earth import manifest
from se.ingest.names import norm

FORCE_TRAIN = DATA / "force2020" / "train.csv"  # train only: the hidden-test file is never read
ED50_GEO_TO_3035 = Transformer.from_crs("EPSG:4230", "EPSG:3035", always_xy=True)
UTM31_TO_3035 = Transformer.from_crs("EPSG:23031", "EPSG:3035", always_xy=True)
Z90 = 1.645  # a 90 percent interval is +-1.645 sigma for a normal error


def wellheads() -> pd.DataFrame:
    """One row per wellbore: wellhead position, datums, TD, TVD at TD, kick-off point, kind."""
    c = duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True)
    q = """select wlbWellboreName n, wlbNsDecDeg lat, wlbEwDecDeg lon, wlbKellyBushElevation kb, wlbWaterDepth wd, wlbTotalDepth td,
                  wlbFinalVerticalDepth tvd_td, {kop} kop, '{kind}' kind from {t}"""
    w = pd.concat([c.execute(q.format(kop="null", kind="exploration", t="wellbore_exploration")).df(),
                   c.execute(q.format(kop="wlbKickOffPoint", kind="development", t="wellbore_development")).df()])
    w["wellbore"] = w.n.map(norm)
    w = w.drop_duplicates("wellbore").drop(columns="n").dropna(subset=["lat", "lon"]).reset_index(drop=True)
    for col in ("kb", "wd", "td", "tvd_td", "kop"):
        w[col] = pd.to_numeric(w[col], errors="coerce")
    x, y = ED50_GEO_TO_3035.transform(w.lon.to_numpy(), w.lat.to_numpy())
    w["x"], w["y"] = x / 1000.0, y / 1000.0
    w["pilot"] = in_pilot(w.lat, w.lon)
    return w


SIDETRACK = r"^(.*?\d)\s*([A-Z]{1,2}\d?)$"  # "25/1-14 G" -> parent "25/1-14"
MD_BINS = [0, 2000, 3000, 4000, 5000, 7000, 1e6]


def estimate_tvd(w: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """TVD at TD (m below rig floor) and its sigma for wellbores without one, calibrated on FactPages wellbores with both TD and TVD."""
    w = w.copy(); w["parent"] = w.wellbore.str.extract(SIDETRACK)[0]; w["side"] = w.parent.notna()
    w["bin"] = pd.cut(w.td, MD_BINS, labels=False)
    k = w.dropna(subset=["td", "tvd_td"]); k = k[(k.td > 300) & (k.tvd_td <= k.td + 1)].assign(ratio=lambda d: d.tvd_td / d.td)
    q = k.groupby(["kind", "side", "bin"]).ratio.quantile([0.05, 0.5, 0.95]).unstack()
    known = k.set_index("wellbore").tvd_td; sp = k[k.side & k.parent.isin(known.index)]; dp = sp.tvd_td - sp.parent.map(known)
    d05, d50, d95 = (float(dp.quantile(x)) for x in (0.05, 0.5, 0.95))
    w["tvd_est"], w["tvd_sd"], w["tvd_how"] = w.tvd_td, 0.0, np.where(w.tvd_td.notna(), "factpages", "none")
    miss = w.tvd_td.isna() & w.td.notna()
    for i in w.index[miss]:  # by class first (parents too), then sidetracks from their parent
        key = (w.at[i, "kind"], w.at[i, "side"], w.at[i, "bin"])
        if key in q.index:
            r05, r50, r95 = q.loc[key]; w.loc[i, ["tvd_est", "tvd_sd", "tvd_how"]] = w.at[i, "td"] * r50, w.at[i, "td"] * (r95 - r05) / 3.29, "class"
    est = w.set_index("wellbore")
    for i in w.index[miss & w.side]:
        pa = w.at[i, "parent"]
        if pa in est.index and np.isfinite(est.at[pa, "tvd_est"]):
            psd = float(est.at[pa, "tvd_sd"]); t = min(float(est.at[pa, "tvd_est"]) + d50, float(w.at[i, "td"]))
            w.loc[i, ["tvd_est", "tvd_sd", "tvd_how"]] = t, float(np.hypot(psd, (d95 - d05) / 3.29)), "parent"
    cal = {"sidetrack_minus_parent_m": {"p05": round(d05), "p50": round(d50), "p95": round(d95), "pairs": int(len(dp))},
           "ratio_classes": int(len(q)), "estimated": {h: int((w.tvd_how[miss] == h).sum()) for h in ("parent", "class", "none")}}
    return w.drop(columns=["bin"]), cal


def force_paths() -> pd.DataFrame:
    """FORCE 2020 train samples as (wellbore, md, x, y, tvdss), thinned to one per metre of MD."""
    f = pd.read_csv(FORCE_TRAIN, sep=";", usecols=["WELL", "DEPTH_MD", "X_LOC", "Y_LOC", "Z_LOC"]).dropna()
    f["wellbore"] = f.WELL.map(norm)
    f = f.assign(m=f.DEPTH_MD.round()).drop_duplicates(["wellbore", "m"]).sort_values(["wellbore", "DEPTH_MD"])
    x, y = UTM31_TO_3035.transform(f.X_LOC.to_numpy(), f.Y_LOC.to_numpy())
    return pd.DataFrame({"wellbore": f.wellbore.to_numpy(), "md": f.DEPTH_MD.to_numpy(), "x": x / 1000.0, "y": y / 1000.0, "tvdss": -f.Z_LOC.to_numpy()})


def approx_tvd(md, td, tvd_td, kop, model: str):
    """TVD below rig floor from FactPages numbers only, and the horizontal offset (m) the model implies (direction unknown).

    model 'ratio': constant inclination from the surface, TVD = MD * TVD_TD / TD.
    model 'kop':   vertical to the kick-off point, then constant inclination to TD (needs a kick-off point; else 'ratio').
    model 'vertical': TVD = MD.
    """
    md = np.asarray(md, float)
    if model == "vertical" or not (np.isfinite(td) and np.isfinite(tvd_td) and td > 0) or tvd_td > td + 1:
        return md.copy(), np.zeros_like(md)
    k0 = kop if (model == "kop" and np.isfinite(kop) and 0 < kop < min(td, tvd_td)) else 0.0
    seg = max(td - k0, 1e-6)
    c = np.clip((tvd_td - k0) / seg, 0.0, 1.0)  # cosine of the inclination
    below = np.clip(md - k0, 0.0, None)
    tvd = np.where(md <= k0, md, k0 + below * c)
    h = below * np.sqrt(1 - c * c)
    return tvd, h


class Frame:
    """Lookup: wellbore + MD -> position, TVDSS and sigmas. Built once; FactPages sigmas calibrated on FORCE wells (calibrate())."""

    def __init__(self, cal: dict | None = None):
        w, self.est_cal = estimate_tvd(wellheads()); self.w = w.set_index("wellbore")
        self.fp = force_paths()
        self.force = {k: g for k, g in self.fp.groupby("wellbore")}
        self.cal = cal or {"model": "ratio", "sz_a": 0.0, "sz_b": 5.0, "vert_frac90": 0.05}

    def source(self, wb: str) -> str:
        if wb in self.force:
            return "force"
        r = self.w.loc[wb] if wb in self.w.index else None
        if r is not None and np.isfinite(r.tvd_td) and np.isfinite(r.td):
            return "factpages"
        return "estimated" if r is not None and np.isfinite(r.tvd_est) and np.isfinite(r.td) else "vertical"

    def at(self, wb: str, md) -> dict:
        """Arrays for the given MDs. sigma_z: 1-sigma vertical error (m); r_lat: lateral uncertainty radius (m, ~90 percent)."""
        md = np.atleast_1d(np.asarray(md, float))
        r = self.w.loc[wb] if wb in self.w.index else None
        kb = float(r.kb) if r is not None and np.isfinite(r.kb) else np.nan
        src = self.source(wb)
        if src == "force":
            g = self.force[wb]
            m, x, y, z = g.md.to_numpy(), g.x.to_numpy(), g.y.to_numpy(), g.tvdss.to_numpy()
            tv = np.interp(md, m, z)
            above, below = md < m[0], md > m[-1]  # outside the logged range: vertical from the nearest logged sample
            tv = np.where(above, z[0] - (m[0] - md), np.where(below, z[-1] + (md - m[-1]), tv))
            xs, ys = np.interp(md, m, x), np.interp(md, m, y)
            out = {"x": xs, "y": ys, "tvdss": tv, "sigma_z": np.where(above | below, 5.0 + 0.02 * np.abs(np.where(above, m[0] - md, md - m[-1])), 1.0),
                   "r_lat": np.where(above | below, 0.05 * np.abs(np.where(above, m[0] - md, md - m[-1])), 0.0)}
        elif src == "factpages":
            kop = float(r.kop) if np.isfinite(r.kop) else np.nan
            # development wells: vertical to the kick-off point by definition, then straight (untested: no true paths; LOG L055)
            tvd, h = approx_tvd(md, float(r.td), float(r.tvd_td), kop, "kop" if np.isfinite(kop) else self.cal["model"])
            out = {"x": np.full_like(md, r.x), "y": np.full_like(md, r.y), "tvdss": tvd - kb,
                   "sigma_z": self.cal["sz_b"] + self.cal["sz_a"] * h, "r_lat": h}
        elif src == "estimated":
            kop = float(r.kop) if np.isfinite(r.kop) else np.nan
            tvd, h = approx_tvd(md, float(r.td), float(r.tvd_est), kop, "kop" if np.isfinite(kop) else self.cal["model"])
            frac = np.clip(md / max(float(r.td), 1.0), 0, 1)  # the TVD error grows along the well, from 0 at the rig floor to tvd_sd at TD
            out = {"x": np.full_like(md, r.x), "y": np.full_like(md, r.y), "tvdss": tvd - kb, "sigma_z": self.cal["sz_b"] + float(r.tvd_sd) * frac, "r_lat": h}
        else:
            f = self.cal["vert_frac90"]  # 90th percentile of (MD - TVD) / MD on FORCE wells
            out = {"x": np.full_like(md, r.x if r is not None else np.nan), "y": np.full_like(md, r.y if r is not None else np.nan), "tvdss": md - kb,
                   "sigma_z": 5.0 + f * md / Z90, "r_lat": md * np.sqrt(max(0.0, 1 - (1 - f) ** 2))}
        out["source"] = src
        return out


def calibrate(fr: Frame) -> dict:
    """Compare FactPages-only depth models with the true FORCE paths; choose the best and fit the vertical sigma (sigma = b + a * h)."""
    rows = []
    for wb, g in fr.force.items():
        if wb not in fr.w.index:
            continue
        r = fr.w.loc[wb]
        if not (np.isfinite(r.kb) and np.isfinite(r.td) and np.isfinite(r.tvd_td)):
            continue
        g = g.iloc[:: max(1, len(g) // 300)]
        tvd_true = g.tvdss.to_numpy() + r.kb
        horiz = 1000 * np.hypot(g.x.to_numpy() - r.x, g.y.to_numpy() - r.y)  # true offset from the wellhead (m)
        for model in ("vertical", "ratio"):
            tvd, h = approx_tvd(g.md.to_numpy(), float(r.td), float(r.tvd_td), np.nan, model)
            rows.append(pd.DataFrame({"wellbore": wb, "model": model, "md": g.md.to_numpy(), "err": tvd - tvd_true, "h": h, "dev": g.md.to_numpy() - tvd_true, "horiz": horiz}))
    d = pd.concat(rows)
    by = {}
    for model, g in d.groupby("model"):
        w = g.groupby("wellbore").err.apply(lambda e: float(np.sqrt(np.mean(e ** 2))))  # per-well RMSE, so long wells do not dominate
        by[model] = {"rmse_m_median_well": round(float(w.median()), 2), "rmse_m_p90_well": round(float(w.quantile(0.9)), 2), "wells": int(len(w)), "samples": int(len(g))}
    best = min(by, key=lambda k: by[k]["rmse_m_median_well"])
    g = d[d.model == best].reset_index(drop=True)

    def fit(t):  # sigma = s * (1 + a * h): shape a from the 90th percentile of |err| in bins of h, scale s so 90 percent of |err| fall inside
        bins = pd.qcut(t.h.rank(method="first"), 10, labels=False)
        q = t.groupby(bins).agg(h=("h", "median"), e90=("err", lambda e: np.percentile(np.abs(e), 90)))
        sl, ic = np.polyfit(q.h, q.e90, 1) if q.h.std() > 1e-6 else (0.0, float(q.e90.mean()))
        a = max(float(sl), 0.0) / max(float(ic), 1.0)
        s = float(np.percentile(np.abs(t.err) / (1 + a * t.h), 90)) / Z90
        return a, max(s, 0.5)

    # whole-well 5-fold: coverage is measured on wells not used for the fit
    wells = np.array(sorted(g.wellbore.unique())); rng = np.random.default_rng(0); rng.shuffle(wells)
    held = []
    for k in range(5):
        te = set(wells[k::5]); tr = g[~g.wellbore.isin(te)]; ts = g[g.wellbore.isin(te)]
        a, s = fit(tr)
        held.append(ts.assign(inside=np.abs(ts.err) <= Z90 * s * (1 + a * ts.h)))
    held = pd.concat(held)
    a, s = fit(g)
    pilot = set(fr.w.index[fr.w.pilot])
    hp = held[held.wellbore.isin(pilot)]
    cover = float(held.groupby("wellbore").inside.mean().mean())  # mean over wells, so long wells do not dominate
    cover_p = float(hp.groupby("wellbore").inside.mean().mean()) if len(hp) else float("nan")
    lat_cover = float((g.horiz.to_numpy() <= np.maximum(g.h.to_numpy(), 50.0)).mean())  # within the radius (50 m floor: wellhead coordinate precision)
    vf = float(np.percentile(np.clip(g.dev / g.md, 0, None), 90))
    pw = g[g.wellbore.isin(pilot)].groupby("wellbore").err.apply(lambda e: float(np.sqrt(np.mean(e ** 2))))
    by["pilot_" + best] = {"rmse_m_median_well": round(float(pw.median()), 2), "rmse_m_p90_well": round(float(pw.quantile(0.9)), 2), "wells": int(len(pw))}
    sz_b, sz_a = s, s * a
    cover, lat_cover = round(cover, 3), round(lat_cover, 3)
    return {"model": best, "sz_a": sz_a, "sz_b": sz_b, "vert_frac90": vf, "compare": by, "cover90_z_heldout_wells": cover, "cover90_z_heldout_pilot_wells": round(cover_p, 3), "cover_lat_radius": lat_cover,
            "note": "FORCE wells are mostly near-vertical exploration wells; the 'kop' model for development wells cannot be tested here (no development wells with true paths)."}


def build() -> dict:
    """Calibrate, then write wells.parquet (every wellbore with its frame source) and force_paths.parquet, with manifests."""
    EARTH.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    fr = Frame()
    fr.cal = calibrate(fr) | {"estimate": fr.est_cal}
    w = fr.w.reset_index()
    w["source"] = [fr.source(b) for b in w.wellbore]
    w.to_parquet(EARTH / "wells.parquet")
    fr.fp.to_parquet(EARTH / "force_paths.parquet")
    (EARTH / "frame_calibration.json").write_text(json.dumps(fr.cal, indent=1))
    p = w[w.pilot]
    summary = {"wellbores": int(len(w)), "pilot": int(len(p)), "pilot_by_source": p.source.value_counts().to_dict(), "calibration": fr.cal, "seconds": round(time.time() - t0, 1)}
    manifest.write(EARTH / "wells.parquet", [DATA / "ncs.duckdb", FORCE_TRAIN], {"calibration": fr.cal}, {"summary": summary})
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
