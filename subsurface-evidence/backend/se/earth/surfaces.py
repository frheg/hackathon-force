"""Surfaces: depth (TVDSS) and sigma of every modelled horizon on a 2 km lattice over the pilot (PLAN P2.2, LOG L056).

Observations: each well's shallowest pick of the horizon (TVDSS, sigma from the frame). Lateral uncertainty becomes depth uncertainty
through the local dip: sigma^2 = sigma_z^2 + (r_lat * |trend gradient|)^2. A group missing in a well that has groups above and below it
is a zero-thickness observation at the next deeper present group (absent, not unknown). Formations also get a presence probability
(indicator kriging) from wells where their group is picked and has formation picks.
Order: seabed, then group tops top-down, each clamped below the one above. Formations are clamped inside their group; their local
order is decided per column in the grid (Viking formations interfinger: 94.6 percent pairwise agreement, L056).
Validation: blocked spatial CV (40 km blocks) against a trend-only and a constant baseline; 90 percent coverage of held-out picks.
"""
import json
import time

import numpy as np
import pandas as pd
from pyproj import Transformer
from sklearn.model_selection import GroupKFold

from se.config import BLOCK_KM, EARTH, PILOT, in_pilot
from se.earth import manifest
from se.earth.gp import GP, design

STEP_KM = 2.0
QC: dict = {}
Z90 = 1.645
TO_3035 = Transformer.from_crs("EPSG:4230", "EPSG:3035", always_xy=True)
FROM_3035 = Transformer.from_crs("EPSG:3035", "EPSG:4230", always_xy=True)


def lattice(step=STEP_KM):
    lo, la = np.meshgrid(np.linspace(*PILOT["lon"], 60), np.linspace(*PILOT["lat"], 60))
    x, y = TO_3035.transform(lo.ravel(), la.ravel())
    xs = np.arange(np.floor(x.min() / 1000 / step) * step, x.max() / 1000 + step, step)
    ys = np.arange(np.floor(y.min() / 1000 / step) * step, y.max() / 1000 + step, step)
    X, Y = np.meshgrid(xs, ys)
    lon, lat = FROM_3035.transform(X.ravel() * 1000, Y.ravel() * 1000)
    return xs, ys, in_pilot(lat, lon).reshape(X.shape), lat.reshape(X.shape), lon.reshape(X.shape)


def _agg(o: pd.DataFrame) -> pd.DataFrame:
    """One observation per location (sidetracks share a wellhead): mean depth, combined variance, keep one wellbore id."""
    o = o.assign(kx=(o.x / 0.05).round(), ky=(o.y / 0.05).round())
    g = o.groupby(["kx", "ky"])
    return pd.DataFrame({"x": g.x.mean(), "y": g.y.mean(), "z": g.z.mean(), "var": g["var"].mean() / g.size() + g.z.var().fillna(0.0),
                         "wellbore": g.wellbore.first(), "kind": g.kind.first(), "n": g.size()}).reset_index(drop=True)


def observations(tops: pd.DataFrame, wells: pd.DataFrame, column: dict) -> tuple[dict, dict]:
    """{horizon: DataFrame(x, y, z, var, wellbore, kind)} plus presence observations for formations."""
    groups = [c["group"] for c in column["groups"]]
    gidx = {g: i for i, g in enumerate(groups)}
    wd = wells.set_index("wellbore").wd
    seabed = tops.wellbore.map(wd)
    bad = tops.top_tvdss < seabed - 10.0  # a rock top above the seabed is impossible: a datum or unit error in the pick (QC, L056)
    QC["picks_above_seabed_excluded"] = int(bad.sum()); QC["examples"] = tops[bad][["wellbore", "name", "top_md", "top_tvdss"]].head(8).to_dict("records")
    tops = tops[~bad]
    gt = tops[tops.level == "GROUP"].copy(); gt["gi"] = gt.name.map(gidx)
    obs, pres = {}, {}
    w = wells[wells.pilot & wells.wd.notna()]
    obs["SEABED"] = _agg(pd.DataFrame({"x": w.x, "y": w.y, "z": w.wd, "var": 2.0 ** 2, "wellbore": w.wellbore, "kind": "water depth"}))

    def present(name, level):
        t = tops[(tops.name == name) & (tops.level == level)].sort_values("top_tvdss").drop_duplicates("wellbore")
        return pd.DataFrame({"x": t.x, "y": t.y, "z": t.top_tvdss, "var": t.sigma_z ** 2, "r_lat": t.r_lat, "wellbore": t.wellbore, "kind": "pick"})

    for h in column["horizons"]:
        o = present(h["name"], h["level"])
        if h["level"] == "GROUP":
            i = gidx[h["name"]]
            per = gt.groupby("wellbore")
            ab = []
            for wb, g in per:
                if (g.name == h["name"]).any() or not ((g.gi < i).any() and (g.gi > i).any()):
                    continue
                d = g[g.gi > i].sort_values("top_tvdss").iloc[0]
                ab.append({"x": d.x, "y": d.y, "z": d.top_tvdss, "var": d.sigma_z ** 2, "r_lat": d.r_lat, "wellbore": wb, "kind": "absent (zero thickness)"})
            if ab:
                o = pd.concat([o, pd.DataFrame(ab)], ignore_index=True)
        else:
            G = h["group"]
            gw = set(gt[gt.name == G].wellbore)
            fw = tops[(tops.level == "FORMATION")].copy()
            fw = fw[fw.wellbore.isin(gw)]
            lex_members = {fm["name"] for c in column["groups"] if c["group"] == G for fm in c["formations"]}
            fw = fw[fw.name.isin(lex_members)]
            interp = set(fw.wellbore)  # wells whose group was split into formations
            has = set(fw[fw.name == h["name"]].wellbore)
            g = gt[(gt.name == G) & gt.wellbore.isin(interp)].drop_duplicates("wellbore")
            pres[h["name"]] = pd.DataFrame({"x": g.x, "y": g.y, "z": g.wellbore.isin(has).astype(float), "var": 0.0, "wellbore": g.wellbore, "kind": "presence"})
        obs[h["name"]] = o
    return obs, pres


def with_dip(o: pd.DataFrame) -> pd.DataFrame:
    """Add lateral position uncertainty as depth variance through the regional dip of a first linear fit."""
    o = o.copy()
    if "r_lat" in o and o.r_lat.notna().any() and len(o) >= 5:
        b = np.linalg.lstsq(design(o[["x", "y"]].to_numpy(), 1), o.z.to_numpy(), rcond=None)[0]
        grad = float(np.hypot(b[1], b[2]))  # m of depth per km
        o["var"] = o["var"] + (o.r_lat.fillna(0) / 1000.0 * grad) ** 2
    return _agg(o)


def blocks(x, y, km=BLOCK_KM):
    return (np.floor(x / km).astype(int) * 100003 + np.floor(y / km).astype(int))


CANDIDATES = ("const", "trend", "gp0", "gp1")


class Fit:
    """One horizon model: constant, linear trend, or GP with constant / linear mean. `k` inflates sigma (nested CV calibration)."""

    def __init__(self, kind, X, z, v):
        self.kind = kind
        if kind in ("gp0", "gp1"):
            self.gp = GP(0 if kind == "gp0" else 1).fit(X, z, v)
        else:
            deg = 0 if kind == "const" else 1
            self.deg = deg
            self.beta = np.linalg.lstsq(design(X, deg), z, rcond=None)[0]
            self.res_sd = float(np.std(z - design(X, deg) @ self.beta)) or 1.0
        self.k = 1.0

    def predict(self, Xs, latent=True):
        if self.kind in ("gp0", "gp1"):
            m, var = self.gp.predict(Xs, latent=latent)
            return m, np.sqrt(var) * self.k
        return design(Xs, self.deg) @ self.beta, np.full(len(Xs), self.res_sd * self.k)


def _cv_errors(kind, X, z, v, bl, folds=5):
    k = min(folds, len(np.unique(bl)))
    e, zs, fold = np.full(len(z), np.nan), np.full(len(z), np.nan), np.full(len(z), -1)
    for i, (tr, te) in enumerate(GroupKFold(k).split(X, groups=bl)):
        f = Fit(kind, X[tr], z[tr], v[tr])
        m, sd = f.predict(X[te], latent=False)
        e[te] = m - z[te]; zs[te] = (m - z[te]) / np.sqrt(sd ** 2 + v[te]); fold[te] = i
    return e, zs, fold


def nested_cover(zs, fold):
    """Coverage of 90 percent intervals when sigma is inflated by a factor fitted on the *other* folds (no peeking)."""
    inside = []
    for f in np.unique(fold):
        other = np.abs(zs[fold != f]); kf = max(1.0, float(np.percentile(other, 90)) / Z90) if len(other) else 1.0
        inside += list(np.abs(zs[fold == f]) <= Z90 * kf)
    return float(np.mean(inside)), max(1.0, float(np.percentile(np.abs(zs), 90)) / Z90)


def select(o: pd.DataFrame, folds=5) -> tuple[Fit, dict]:
    """Choose the model of one horizon by blocked CV (40 km): lowest RMSE wins; sigma inflation by nested CV; near-field CV (10 km) reported."""
    X, z, v = o[["x", "y"]].to_numpy(), o.z.to_numpy(), o["var"].to_numpy()
    bl = blocks(o.x.to_numpy(), o.y.to_numpy())
    if len(np.unique(bl)) < 2 or len(o) < 15:
        f = Fit("const", X, z, v); return f, {"n": int(len(o)), "chosen": "const", "skipped": "too few observations or blocks"}
    res = {}
    for kind in CANDIDATES:
        e, zs, fold = _cv_errors(kind, X, z, v, bl, folds)
        res[kind] = (float(np.sqrt(np.nanmean(e ** 2))), zs, fold)
    best = min(res, key=lambda k: res[k][0])
    cover, kfull = nested_cover(res[best][1], res[best][2])
    en, zn, fn = _cv_errors(best, X, z, v, blocks(o.x.to_numpy(), o.y.to_numpy(), 10.0), folds)
    near_cover = float(np.mean(np.abs(zn) <= Z90 * kfull))
    f = Fit(best, X, z, v); f.k = kfull
    return f, {"n": int(len(o)), "chosen": best, **{f"rmse_{k}": round(res[k][0], 1) for k in CANDIDATES},
               "gain_vs_best_baseline": (round(1 - res[best][0] / min(res["const"][0], res["trend"][0]), 3) if min(res["const"][0], res["trend"][0]) > 0 else None), "sigma_inflation": round(kfull, 3),
               "cover90_far_nested": round(cover, 3), "rmse_near_10km": round(float(np.sqrt(np.nanmean(en ** 2))), 1), "cover90_near_10km": round(near_cover, 3),
               **({"gp": f.gp.params()} if best.startswith("gp") else {})}


def cv_presence(o: pd.DataFrame, folds=5) -> dict:
    """Blocked CV of the presence probability: Brier score vs the training share."""
    X, y = o[["x", "y"]].to_numpy(), o.z.to_numpy()
    bl = blocks(o.x.to_numpy(), o.y.to_numpy())
    k = min(folds, len(np.unique(bl)))
    if k < 2 or len(o) < 15 or y.min() == y.max():
        return {"n": int(len(o)), "share": round(float(y.mean()), 3) if len(y) else None, "skipped": "too few observations or no variation"}
    b_gp, b_c = [], []
    for tr, te in GroupKFold(k).split(X, groups=bl):
        p = np.clip(GP(0).fit(X[tr], y[tr], np.full(len(tr), 0.02)).predict(X[te])[0], 0, 1)
        b_gp += list((p - y[te]) ** 2); b_c += list((y[tr].mean() - y[te]) ** 2)
    return {"n": int(len(o)), "share": round(float(y.mean()), 3), "brier_gp": round(float(np.mean(b_gp)), 4), "brier_const": round(float(np.mean(b_c)), 4), "use_gp": bool(np.mean(b_gp) < np.mean(b_c))}


def fractions(tops: pd.DataFrame, column: dict) -> dict:
    """Formation top as a fraction of its group interval in each well: (formation top - group top) / (group base - group top)."""
    g = tops[tops.level == "GROUP"].sort_values("top_tvdss").drop_duplicates(["wellbore", "name"]).set_index(["wellbore", "name"])
    out = {}
    for h in column["horizons"]:
        if h["level"] != "FORMATION":
            continue
        f = tops[(tops.level == "FORMATION") & (tops.name == h["name"])].sort_values("top_tvdss").drop_duplicates("wellbore")
        rows = []
        for r in f.itertuples():
            key = (r.wellbore, h["group"])
            if key not in g.index:
                continue
            gt, gb = g.loc[key, "top_tvdss"], g.loc[key, "bot_tvdss"]
            if not (np.isfinite(gt) and np.isfinite(gb)) or gb - gt < 1:
                continue
            rows.append({"x": r.x, "y": r.y, "z": float(np.clip((r.top_tvdss - gt) / (gb - gt), 0, 1)), "var": 0.0004, "wellbore": r.wellbore, "kind": "fraction", "depth": r.top_tvdss, "dvar": r.sigma_z ** 2})
        out[h["name"]] = pd.DataFrame(rows)
    return out


def build() -> dict:
    t0 = time.time()
    column = json.loads((EARTH / "column.json").read_text())
    tops = pd.read_parquet(EARTH / "tops.parquet")
    wells = pd.read_parquet(EARTH / "wells.parquet")
    obs, pres = observations(tops, wells, column)
    fr = fractions(tops, column)
    xs, ys, inside, lat, lon = lattice()
    XX, YY = np.meshgrid(xs, ys); P = np.c_[XX.ravel(), YY.ravel()]
    names = ["SEABED"] + [h["name"] for h in column["horizons"]]
    level = {"SEABED": "SEABED", **{h["name"]: h["level"] for h in column["horizons"]}}
    grp_of = {h["name"]: h.get("group") for h in column["horizons"]}
    gnames = [n for n in names if level[n] in ("SEABED", "GROUP")]
    mean, sd, pres_p, near, fits, report, keep = {}, {}, {}, {}, {}, {}, []
    from scipy.spatial import cKDTree
    first_group = gnames[1]
    for n in gnames:
        o = obs[n] if n == "SEABED" else with_dip(obs[n])
        keep.append(o.assign(horizon=n))
        near[n] = cKDTree(o[["x", "y"]].to_numpy()).query(P)[0].reshape(XX.shape)
        if n == first_group:  # the shallowest group starts at the seabed (L055: shallowest top = KB + water depth in 642 wells)
            mean[n], sd[n] = mean["SEABED"].copy(), sd["SEABED"].copy()
            report[n] = {"n": int(len(o)), "chosen": "= SEABED", "rule": "the shallowest group's top is the seabed"}
            continue
        f, rep = select(o)
        fits[n], report[n] = f, rep
        m, s_ = f.predict(P)
        mean[n], sd[n] = m.reshape(XX.shape), s_.reshape(XX.shape)
    # sophisticated candidates (ML-kriging hybrid, deep-kernel GP) compete with the chosen model on shared blocked folds (L057).
    # Adopted only if held-out RMSE falls by >= 5 percent and nested 90 percent coverage stays within 0.85-0.95.
    from se.earth import hybrid
    O = {g: (obs[g] if g == "SEABED" else with_dip(obs[g])) for g in gnames}
    base_kind = {g: (report[g]["chosen"] if report.get(g, {}).get("chosen") in CANDIDATES else "gp0") for g in gnames}
    hres, covf = hybrid.evaluate(gnames, O, base_kind, lambda kind, X, z, v: Fit(kind, X, z, v))
    full = {g: Fit(base_kind[g], O[g][["x", "y"]].to_numpy(), O[g].z.to_numpy(), O[g]["var"].to_numpy()) for g in gnames}
    for g, r in hres.items():
        b, best = r["base"], None
        for kind in ("rk_gbm", "dkl"):
            c = r.get(kind, {})
            if "rmse" in c and c["rmse"] <= 0.95 * b["rmse"] and c["cover90_nested"] is not None and 0.85 <= c["cover90_nested"] <= 0.95 and (best is None or c["rmse"] < r[best]["rmse"]):
                best = kind
        r["adopted"] = best or "base"
        report[g]["hybrid"] = r
        if best:
            sh = gnames[:gnames.index(g)]
            mdl = (hybrid.RKGBM() if best == "rk_gbm" else hybrid.DKL()).fit(covf(full, sh, O[g][["x", "y"]].to_numpy()), O[g][["x", "y"]].to_numpy(), O[g].z.to_numpy(), O[g]["var"].to_numpy())
            m, s_ = mdl.predict(covf(full, sh, P), P, latent=True)
            mean[g], sd[g] = m.reshape(XX.shape), (s_ * r[best]["inflation"]).reshape(XX.shape)
            report[g]["chosen"] = best
    # isochores (L059): a group top may instead be the group above plus a kriged thickness. Constant deep surfaces carry no
    # thickness, so the grid collapsed Vestland and Statfjord to one layer. Chosen per group by the same shared blocked folds.
    iso = isochores(gnames, O, base_kind, P, XX.shape, keep={g for g, r in hres.items() if r["adopted"] != "base"})
    for g, r in iso["report"].items():
        report[g]["isochore"] = r
        if r["adopted"]:
            above = gnames[gnames.index(g) - 1]
            mean[g] = mean[above] + iso["T"][g]
            sd[g] = np.sqrt(sd[above] ** 2 + iso["sdT"][g] ** 2)
            report[g]["chosen"] = f"isochore below {above}"
    # seismic horizons tied to wells (P2.3, L058): blended in where they beat the well-only surface on held-out blocks
    from se.earth import seismic
    srep, ssurf = seismic.build(xs, ys, STEP_KM)

    def blend(n):
        if n not in ssurf:
            return
        w = ssurf[n]["weight"]; ms = np.where(w > 0, ssurf[n]["mean"], 0.0)
        mean[n] = w * ms + (1 - w) * mean[n]
        sd[n] = np.sqrt(w * np.where(w > 0, ssurf[n]["sd"], 0.0) ** 2 + (1 - w) * sd[n] ** 2)
        report[n]["seismic"] = {**srep["held_out"][n], "nodes_weighted": int((w > 0).sum())}

    for g in gnames:
        blend(g)
    clamp = {}
    for a_, b_ in zip(gnames, gnames[1:]):
        before = mean[b_].copy(); mean[b_] = np.maximum(mean[b_], mean[a_]); clamp[b_] = round(float((mean[b_] != before)[inside].mean()), 4)
    # formations: fraction of the group interval, so they cannot leave it
    for n in names:
        if level[n] != "FORMATION":
            continue
        G = grp_of[n]; i = gnames.index(G)
        top, base = mean[G], (mean[gnames[i + 1]] if i + 1 < len(gnames) else mean[G] + 300.0)
        o = fr.get(n, pd.DataFrame())
        if len(o) >= 5:
            f, rep = select(o)
            m, s_ = f.predict(P)
            fm, fs = np.clip(m, 0, 1).reshape(XX.shape), s_.reshape(XX.shape)
            near[n] = cKDTree(o[["x", "y"]].to_numpy()).query(P)[0].reshape(XX.shape)
            keep.append(o.assign(horizon=n))
        else:
            fm, fs, rep = np.full(XX.shape, 0.5), np.full(XX.shape, 0.29), {"n": int(len(o)), "chosen": "none: no fraction data, middle of group with uniform sigma"}
            near[n] = np.full(XX.shape, np.inf)
        thick = np.maximum(base - top, 0)
        mean[n] = top + fm * thick
        sd[n] = np.sqrt(((1 - fm) * sd[G]) ** 2 + (fm * (sd[gnames[i + 1]] if i + 1 < len(gnames) else sd[G])) ** 2 + (thick * fs) ** 2)
        rep["fraction_model"] = True
        report[n] = rep
        blend(n)
        mean[n] = np.clip(mean[n], top, base)  # still inside its group after the seismic blend
        if n in pres:
            report[n]["presence"] = cv_presence(pres[n])
            po = pres[n]
            if report[n]["presence"].get("use_gp"):
                pres_p[n] = np.clip(GP(0).fit(po[["x", "y"]].to_numpy(), po.z.to_numpy(), np.full(len(po), 0.02)).predict(P)[0], 0, 1).reshape(XX.shape)
            else:
                pres_p[n] = np.full(XX.shape, float(po.z.mean()) if len(po) else 1.0)
    # formation depth checked end to end at held-out wells (group surfaces and fraction fitted without the well's block)
    report["_formation_chain"] = formation_chain_cv(obs, fr, gnames, grp_of, report, level, names)
    np.savez_compressed(EARTH / "surfaces.npz", x=xs, y=ys, inside=inside, lat=lat, lon=lon, names=np.array(names), level=np.array([level[n] for n in names]),
                        mean=np.stack([mean[n] for n in names]), sd=np.stack([sd[n] for n in names]), near_km=np.stack([near[n] for n in names]),
                        presence=np.stack([pres_p.get(n, np.ones(XX.shape)) for n in names]))
    pd.concat(keep, ignore_index=True).to_parquet(EARTH / "surface_obs.parquet")
    out = {"step_km": STEP_KM, "nodes": int(XX.size), "nodes_inside": int(inside.sum()), "qc": QC, "cv": report, "group_clamped_share_inside": clamp, "seconds": round(time.time() - t0, 1)}
    (EARTH / "surfaces_report.json").write_text(json.dumps(out, indent=1, default=str))
    manifest.write(EARTH / "surfaces.npz", [EARTH / "tops.parquet", EARTH / "wells.parquet", EARTH / "column.json"], {"step_km": STEP_KM, "candidates": CANDIDATES, "block_km": BLOCK_KM, "near_block_km": 10.0})
    return out


def isochores(gnames, O, base_kind, P, shape, k=5, keep=()) -> dict:
    """Per group below the first two: direct model vs (top of the group above + kriged thickness), on shared 40 km block folds.

    Thickness observations: wells with both tops (absent groups enter as zero thickness through their zero-thickness observation).
    The group above is predicted with whatever was chosen for it (direct or isochore), so chained errors are scored honestly.
    """
    from se.earth.hybrid import fold_of

    choice, rep, T, sdT = {}, {}, {}, {}
    cache = {}

    def direct(g, f):
        key = ("d", g, f)
        if key not in cache:
            o = O[g]; tr = fold_of(o.x.to_numpy(), o.y.to_numpy(), k=k) != f if f is not None else np.ones(len(o), bool)
            cache[key] = Fit(base_kind.get(g, "gp0"), o[["x", "y"]].to_numpy()[tr], o.z.to_numpy()[tr], o["var"].to_numpy()[tr])
        return cache[key]

    def thick_obs(g):
        above = gnames[gnames.index(g) - 1]
        a = O[above].drop_duplicates("wellbore").set_index("wellbore"); b = O[g].drop_duplicates("wellbore").set_index("wellbore")
        j = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")
        j = j[(j.z_b - j.z_a) >= -5]
        return pd.DataFrame({"x": j.x_b, "y": j.y_b, "z": np.maximum(j.z_b - j.z_a, 0.0), "var": j.var_a + j.var_b})

    def thick(g, f):
        key = ("t", g, f)
        if key not in cache:
            t = thick_obs(g); tr = fold_of(t.x.to_numpy(), t.y.to_numpy(), k=k) != f if f is not None else np.ones(len(t), bool)
            kind = select(t[tr].reset_index(drop=True))[0].kind if tr.sum() >= 15 else "const"
            cache[key] = Fit(kind, t[["x", "y"]].to_numpy()[tr], t.z.to_numpy()[tr], t["var"].to_numpy()[tr])
        return cache[key]

    def predict(g, f, X):
        if choice.get(g) == "iso":
            above = gnames[gnames.index(g) - 1]
            ma, sa = predict(above, f, X); mt, st_ = thick(g, f).predict(X, latent=False)
            return ma + np.maximum(mt, 0), np.sqrt(sa ** 2 + st_ ** 2)
        return direct(g, f).predict(X, latent=False)

    for i, g in enumerate(gnames):
        if i < 2 or len(thick_obs(g)) < 15:
            continue
        o = O[g]; X, z, v = o[["x", "y"]].to_numpy(), o.z.to_numpy(), o["var"].to_numpy(); fo = fold_of(o.x.to_numpy(), o.y.to_numpy(), k=k)
        res = {}
        for c in ("direct", "iso"):
            choice[g] = c
            e, zs = np.full(len(z), np.nan), np.full(len(z), np.nan)
            for f in range(k):
                te = fo == f
                if te.sum():
                    m, sd_ = predict(g, f, X[te]); e[te] = m - z[te]; zs[te] = (m - z[te]) / np.sqrt(sd_ ** 2 + v[te])
            ok = np.isfinite(e); cover, kf = nested_cover(zs[ok], fo[ok])
            res[c] = {"rmse": round(float(np.sqrt(np.mean(e[ok] ** 2))), 1), "cover90_nested": round(cover, 3), "inflation": round(kf, 3)}
        win = res["iso"]["rmse"] <= 0.95 * res["direct"]["rmse"] and 0.85 <= res["iso"]["cover90_nested"] <= 0.95
        # a constant surface carries no thickness: under a varying surface it makes artificial pinch-outs (the grid collapsed
        # Vestland and Statfjord to one layer). Then the isochore is taken if its depth RMSE is at most 10 percent worse (L059).
        if base_kind.get(g) == "const" and res["iso"]["rmse"] <= 1.10 * res["direct"]["rmse"] and 0.85 <= res["iso"]["cover90_nested"] <= 0.97:
            win = True
        if g in keep:  # a sophisticated model already won for this group (L057); its fold models are not refitted here
            win = False
        choice[g] = "iso" if win else "direct"
        rep[g] = {**res, "thickness_wells": int(len(thick_obs(g))), "adopted": bool(win)}
        if win:
            mt, st_ = thick(g, None).predict(P)
            T[g] = np.maximum(mt, 0).reshape(shape); sdT[g] = (st_ * res["iso"]["inflation"]).reshape(shape)
    return {"report": rep, "T": T, "sdT": sdT}


def formation_chain_cv(obs, fr, gnames, grp_of, report, level, names, folds=5) -> dict:
    """Held-out formation tops predicted from group surfaces + fraction (all fitted on other 40 km blocks) vs a direct per-formation fit."""
    out = {}
    for n in names:
        if level[n] != "FORMATION" or len(fr.get(n, [])) < 15:
            continue
        o = fr[n]; G = grp_of[n]; i = gnames.index(G); Gb = gnames[i + 1] if i + 1 < len(gnames) else None
        X = o[["x", "y"]].to_numpy(); bl = blocks(o.x.to_numpy(), o.y.to_numpy()); k = min(folds, len(np.unique(bl)))
        if k < 2 or Gb is None:
            continue
        e_chain, e_direct, inside = [], [], []
        for tr, te in GroupKFold(k).split(X, groups=bl):
            held = set(o.wellbore.iloc[te])
            def fit_h(h):
                oo = obs[h] if h == "SEABED" else with_dip(obs[h]); oo = oo[~oo.wellbore.isin(held)]
                kind = report[h]["chosen"] if report[h]["chosen"] in CANDIDATES else "gp1"
                return Fit(kind, oo[["x", "y"]].to_numpy(), oo.z.to_numpy(), oo["var"].to_numpy())
            ft, fb = fit_h(G), fit_h(Gb)
            ff = Fit(report[n]["chosen"] if report[n].get("chosen") in CANDIDATES else "const", X[tr], o.z.to_numpy()[tr], o["var"].to_numpy()[tr])
            mt, st_ = ft.predict(X[te], latent=False); mb, sb = fb.predict(X[te], latent=False); mf, sf = ff.predict(X[te], latent=False)
            mb = np.maximum(mb, mt); mf = np.clip(mf, 0, 1); th = mb - mt
            pred = mt + mf * th; psd = np.sqrt(((1 - mf) * st_) ** 2 + (mf * sb) ** 2 + (th * sf) ** 2)
            truth = o.depth.to_numpy()[te]
            e_chain += list(pred - truth); inside += list(np.abs(pred - truth) <= Z90 * np.sqrt(psd ** 2 + o.dvar.to_numpy()[te]))
            dd = obs[n][~obs[n].wellbore.isin(held)]  # direct: the formation's own picks only
            fd = Fit("gp1", dd[["x", "y"]].to_numpy(), dd.z.to_numpy(), dd["var"].to_numpy()) if len(dd) >= 10 else None
            if fd is not None:
                e_direct += list(fd.predict(X[te], latent=False)[0] - truth)
        out[n] = {"n": int(len(o)), "rmse_chain": round(float(np.sqrt(np.mean(np.square(e_chain)))), 1), "rmse_direct": round(float(np.sqrt(np.mean(np.square(e_direct)))), 1) if e_direct else None,
                  "cover90_chain": round(float(np.mean(inside)), 3)}
    return out


if __name__ == "__main__":
    o = build()
    print("nodes", o["nodes"], "inside", o["nodes_inside"], "seconds", o["seconds"])
    ch = o["cv"].pop("_formation_chain")
    for n, r in o["cv"].items():
        c = ch.get(n, {})
        print(f"{n:22s} n {r.get('n', 0):4d} {r.get('chosen', '-'):>9}  far rmse {r.get('rmse_' + r.get('chosen', ''), '-'):>7} (const {r.get('rmse_const', '-')}, trend {r.get('rmse_trend', '-')})  cover {r.get('cover90_far_nested', '-')}  near rmse {r.get('rmse_near_10km', '-')} cover {r.get('cover90_near_10km', '-')}"
              + (f"  | chain {c.get('rmse_chain')} vs direct {c.get('rmse_direct')} cover {c.get('cover90_chain')}" if c else ""))
