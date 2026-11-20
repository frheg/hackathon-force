"""Seismic horizons tied to wells (PLAN P2.3, LOG L058).

Source: Smeaheia Key_Horizons_2010 (Equinor, Gassnova; Petrel export, ED50 UTM 31N points). Z is two-way time in ms, negative down:
the seabed is 1.32 x water depth (water at about 1,500 m/s), deeper horizons about 1.05 x pick depth. The shapefile says Domain "Unknown"; time is
inferred from those ratios (L058). Coverage: about 100 x 200 km over Troll and the Horda Platform.
Depth: water depth = vw * t_seabed / 2; rock depth below seabed = dt * (a + b * dt), dt = one-way rock time (s): average velocity linear in time.
vw, a and b are fitted on well ties; a GP on the tie residuals (pick minus seismic depth) corrects the velocity laterally: kriging with an
external drift. Tested on held-out 40 km blocks against the well-only surfaces. Caveat: the interpreter tied these horizons to wells,
so a held-out pick is not fully independent of the time pick near it (L049).
"""
import json
import zipfile

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from sklearn.model_selection import GroupKFold

from se.config import BLOCK_KM, DATA, EARTH
from se.earth import manifest
from se.earth.gp import GP

ARCHIVE = DATA / "seismic" / "smeaheia" / "horizons.zip"
MEMBER = "Horizons/data/Key_Horizons_2010/Shape files/{}.shp"
HORIZONS = {"Top Shetland Group": "SHETLAND GP", "Draupne Fm": "DRAUPNE FM", "Sognefjjord Fm": "SOGNEFJORD FM", "Fenfjord Fm": "FENSFJORD FM",
            "Johansen Fm": "JOHANSEN FM", "Dunlin Gp": "DUNLIN GP", "Statfjord Fm": "STATFJORD GP"}  # source spelling -> FactPages name
TIE_M = 250.0  # a well is tied when horizon points lie within this distance of its wellhead
TAPER_KM = 6.0  # seismic weight falls to zero over this distance outside coverage
Z90 = 1.645
UTM_TO_3035 = Transformer.from_crs("EPSG:23031", "EPSG:3035", always_xy=True)
GEO_TO_UTM = Transformer.from_crs("EPSG:4230", "EPSG:23031", always_xy=True)
PT = np.dtype([("h", ">i4", 2), ("t", "<i4"), ("x", "<f8"), ("y", "<f8"), ("z", "<f8"), ("m", "<f8")])


def read(name: str) -> np.ndarray:
    """(x, y, twt_ms positive down) of one PointZ shapefile, read from the archive without extracting."""
    with zipfile.ZipFile(ARCHIVE) as z:
        b = z.read(MEMBER.format(name))[100:]
    a = np.frombuffer(b[: len(b) // PT.itemsize * PT.itemsize], dtype=PT)
    if not (a["t"] == 11).all():
        raise ValueError(f"{name}: expected PointZ records only")
    p = np.c_[a["x"], a["y"], -a["z"]]
    return p[np.isfinite(p).all(1) & (p[:, 2] > 0)]


def sample(P: np.ndarray, kd: cKDTree, xy: np.ndarray, r: float = TIE_M) -> np.ndarray:
    """Median time of horizon points within r of each xy (nan if none)."""
    out = np.full(len(xy), np.nan)
    for i, nb in enumerate(kd.query_ball_point(xy, r)):
        if nb:
            out[i] = float(np.median(P[nb, 2]))
    return out


class Velocity:
    """depth = vw * t_sb / 2 + dt * (a + b * dt), dt = (t - t_sb) / 2000 s; residual GP for lateral correction."""

    def fit(self, tsb, wd, t, z, X, var):
        self.vw = float(np.median(2000.0 * wd / tsb))
        dt = (t - tsb) / 2000.0
        y = z - self.vw * tsb / 2000.0
        A = np.c_[dt, dt ** 2]
        self.ab = np.linalg.lstsq(A, y, rcond=None)[0]
        r = z - self.depth(tsb, t)
        self.gp = GP(0, ell_bounds=(2.0, 80.0)).fit(X, r, var) if len(r) >= 8 else None
        self.rmean = float(np.mean(r)) if len(r) else 0.0
        self.rsd = float(np.std(r)) if len(r) > 1 else 50.0
        return self

    def depth(self, tsb, t):
        dt = (t - tsb) / 2000.0
        return self.vw * tsb / 2000.0 + dt * (self.ab[0] + self.ab[1] * dt)

    def predict(self, tsb, t, X, latent=True):
        d = self.depth(tsb, t)
        if self.gp is None:
            return d + self.rmean, np.full(len(d), self.rsd)
        m, v = self.gp.predict(X, latent=latent)
        return d + m, np.sqrt(v)


def ties(tops: pd.DataFrame, wells: pd.DataFrame, P: dict, kd: dict) -> pd.DataFrame:
    """One row per (horizon, wellbore) with a pick and seismic within TIE_M: times, pick depth, water depth, sigma, 3035 km xy."""
    w = wells.set_index("wellbore")
    rows = []
    for src, name in HORIZONS.items():
        s = tops[tops.name == name].sort_values("top_tvdss").drop_duplicates("wellbore")
        s = s[s.wellbore.map(w.wd).notna()]
        e, n = GEO_TO_UTM.transform(s.wellbore.map(w.lon).to_numpy(), s.wellbore.map(w.lat).to_numpy())
        xy = np.c_[e, n]
        th, tsb = sample(P[src], kd[src], xy), sample(P["Seabed"], kd["Seabed"], xy)
        ok = np.isfinite(th) & np.isfinite(tsb)
        rows.append(pd.DataFrame({"horizon": name, "wellbore": s.wellbore.to_numpy()[ok], "x": s.x.to_numpy()[ok], "y": s.y.to_numpy()[ok],
                                  "t": th[ok], "tsb": tsb[ok], "wd": s.wellbore.map(w.wd).to_numpy()[ok], "z": s.top_tvdss.to_numpy()[ok],
                                  "var": (s.sigma_z.to_numpy()[ok]) ** 2}))
    return pd.concat(rows, ignore_index=True)


def lattice_times(P: dict, kd: dict, xs, ys, step: float) -> dict:
    """Median time per lattice node from horizon points within half a cell diagonal (nan where the horizon was not interpreted)."""
    XX, YY = np.meshgrid(xs, ys)
    e, n = Transformer.from_crs("EPSG:3035", "EPSG:23031", always_xy=True).transform(XX.ravel() * 1000, YY.ravel() * 1000)
    xy = np.c_[e, n]
    return {src: sample(P[src], kd[src], xy, r=step * 1000 / np.sqrt(2)).reshape(XX.shape) for src in ["Seabed"] + list(HORIZONS)}


def evaluate(T: pd.DataFrame, tops: pd.DataFrame, folds: int = 5) -> dict:
    """Held-out 40 km blocks: tied wells predicted by seismic + residual GP vs well-only (const and GP0 on all pilot picks of that horizon)."""
    from se.earth.surfaces import blocks

    out, oof = {}, {}
    for name, g in T.groupby("horizon", sort=False):
        bl = blocks(g.x.to_numpy(), g.y.to_numpy()); k = min(folds, len(np.unique(bl)))
        if k < 2 or len(g) < 6:
            out[name] = {"ties": int(len(g)), "skipped": "too few ties or blocks"}; continue
        allp = tops[tops.name == name].sort_values("top_tvdss").drop_duplicates("wellbore")
        e = {"seismic": [], "const": [], "gp0": []}; rock = []
        for f, (tr, te) in enumerate(GroupKFold(k).split(g, groups=bl)):
            a, b = g.iloc[tr], g.iloc[te]
            # every pick in a held-out block is withheld from all fits (not just the tied ones)
            heldb = set(blocks(b.x.to_numpy(), b.y.to_numpy()))
            ttr = T[~np.isin(blocks(T.x.to_numpy(), T.y.to_numpy()), list(heldb))]
            vel = Velocity().fit(ttr.tsb.to_numpy(), ttr.wd.to_numpy(), ttr.t.to_numpy(), ttr.z.to_numpy(), ttr[["x", "y"]].to_numpy(), ttr["var"].to_numpy())
            # the residual GP of this horizon only: other horizons calibrate the velocity function, not this surface's lateral correction
            aa = a[~np.isin(blocks(a.x.to_numpy(), a.y.to_numpy()), list(heldb))]
            r = aa.z.to_numpy() - vel.depth(aa.tsb.to_numpy(), aa.t.to_numpy())
            gp = GP(0, ell_bounds=(2.0, 80.0)).fit(aa[["x", "y"]].to_numpy(), r, aa["var"].to_numpy()) if len(aa) >= 6 else None
            d = vel.depth(b.tsb.to_numpy(), b.t.to_numpy())
            if gp is not None:
                m, v = gp.predict(b[["x", "y"]].to_numpy(), latent=False); pred, sd = d + m, np.sqrt(v)
            else:
                pred, sd = d + (r.mean() if len(r) else 0.0), np.full(len(d), r.std() if len(r) > 1 else 100.0)
            e["seismic"] += list(pred - b.z.to_numpy()); rock += list(pred - b.wd.to_numpy())
            wtr = allp[~np.isin(blocks(allp.x.to_numpy(), allp.y.to_numpy()), list(heldb))]
            e["const"] += list(np.full(len(b), wtr.top_tvdss.mean()) - b.z.to_numpy())
            wg = GP(0).fit(wtr[["x", "y"]].to_numpy(), wtr.top_tvdss.to_numpy(), wtr.sigma_z.to_numpy() ** 2)
            e["gp0"] += list(wg.predict(b[["x", "y"]].to_numpy())[0] - b.z.to_numpy())
        rm = {m: round(float(np.sqrt(np.mean(np.square(v)))), 1) for m, v in e.items()}
        out[name] = {"ties": int(len(g)), "wells_only_picks": int(len(allp)), **{f"rmse_{m}": v for m, v in rm.items()}}
        oof[name] = (np.array(e["seismic"]), np.array(rock))
    # sigma: the GP's own variance from 6-12 ties is far too small (coverage 0.43-0.78 in L058's first run). Use a relative error of the
    # rock column instead, sigma = q * (depth - water), q from held-out errors of the *other* horizons (leave-one-horizon-out).
    for name, (err, rk) in oof.items():
        others = np.concatenate([np.abs(e_) / np.maximum(r_, 50.0) for n_, (e_, r_) in oof.items() if n_ != name])
        q = float(np.percentile(others, 90)) / Z90
        cov = float(np.mean(np.abs(err) <= Z90 * q * np.maximum(rk, 50.0)))
        r = out[name]
        r.update({"rel_sigma_other_horizons": round(q, 4), "cover90_seismic": round(cov, 3),
                  "adopt": bool(r["rmse_seismic"] <= 0.95 * min(r["rmse_const"], r["rmse_gp0"]) and 0.85 <= cov <= 0.97)})
    allrel = np.concatenate([np.abs(e_) / np.maximum(r_, 50.0) for e_, r_ in oof.values()])
    out["_rel_sigma"] = round(float(np.percentile(allrel, 90)) / Z90, 4)
    return out


def build(xs=None, ys=None, step=None) -> dict:
    """Ties, held-out test, and seismic depth surfaces on the earth lattice (mean, sd, weight) for the horizons that earned it."""
    from se.earth.surfaces import STEP_KM, lattice

    if xs is None:
        xs, ys, *_ = lattice(); step = STEP_KM
    tops = pd.read_parquet(EARTH / "tops.parquet"); wells = pd.read_parquet(EARTH / "wells.parquet")
    P = {s: read(s) for s in ["Seabed"] + list(HORIZONS)}
    kd = {s: cKDTree(p[:, :2]) for s, p in P.items()}
    T = ties(tops, wells, P, kd)
    ev = evaluate(T, tops)
    vel = Velocity().fit(T.tsb.to_numpy(), T.wd.to_numpy(), T.t.to_numpy(), T.z.to_numpy(), T[["x", "y"]].to_numpy(), T["var"].to_numpy())
    lt = lattice_times(P, kd, xs, ys, step)
    XX, YY = np.meshgrid(xs, ys); X = np.c_[XX.ravel(), YY.ravel()]
    surf = {}
    for src, name in HORIZONS.items():
        r = ev.get(name, {})
        if not r.get("adopt"):
            continue
        g = T[T.horizon == name]
        res = g.z.to_numpy() - vel.depth(g.tsb.to_numpy(), g.t.to_numpy())
        gp = GP(0, ell_bounds=(2.0, 80.0)).fit(g[["x", "y"]].to_numpy(), res, g["var"].to_numpy())
        tsb, th = lt["Seabed"].ravel(), lt[src].ravel()
        ok = np.isfinite(tsb) & np.isfinite(th)
        m, v = gp.predict(X)
        mean = np.where(ok, vel.depth(np.where(ok, tsb, 1.0), np.where(ok, th, 1.0)) + m, np.nan)
        # weight 1 deep inside coverage, falling to 0 at its edge over TAPER_KM, so the seam to the well-only surface is smooth
        edge = cKDTree(X[~ok]).query(X)[0] if (~ok).any() else np.full(len(X), np.inf)
        wd_node = vel.vw * np.where(ok, tsb, 0.0) / 2000.0
        surf[name] = {"mean": mean.reshape(XX.shape), "sd": (ev["_rel_sigma"] * np.maximum(mean - wd_node, 50.0)).reshape(XX.shape),
                      "weight": np.where(ok, np.clip(edge / TAPER_KM, 0, 1), 0.0).reshape(XX.shape)}
    np.savez_compressed(EARTH / "seismic_surfaces.npz", names=np.array(list(surf)), mean=np.stack([s["mean"] for s in surf.values()]) if surf else np.zeros((0,)),
                        sd=np.stack([s["sd"] for s in surf.values()]) if surf else np.zeros((0,)), weight=np.stack([s["weight"] for s in surf.values()]) if surf else np.zeros((0,)))
    T.to_parquet(EARTH / "seismic_ties.parquet")
    out = {"source": "Smeaheia Key_Horizons_2010 (Equinor, Gassnova), two-way time", "tie_radius_m": TIE_M, "ties": int(len(T)),
           "velocity": {"water_mps": round(vel.vw, 1), "a_mps": round(float(vel.ab[0]), 1), "b_mps_per_s": round(float(vel.ab[1]), 1),
                        "tie_residual_sd_m": round(vel.rsd, 1)}, "held_out": ev, "adopted": list(surf),
           "nodes_with_seismic": {s: int(np.isfinite(lt[s]).sum()) for s in lt}}
    (EARTH / "seismic_report.json").write_text(json.dumps(out, indent=1))
    manifest.write(EARTH / "seismic_surfaces.npz", [ARCHIVE, EARTH / "tops.parquet", EARTH / "wells.parquet"], {"tie_radius_m": TIE_M, "block_km": BLOCK_KM})
    return out, surf


if __name__ == "__main__":
    o, _ = build()
    print("ties", o["ties"], "velocity", o["velocity"])
    for n, r in o["held_out"].items():
        print(f"{n:15s} {r}")
    print("adopted:", o["adopted"], "| nodes with seismic:", o["nodes_with_seismic"])
