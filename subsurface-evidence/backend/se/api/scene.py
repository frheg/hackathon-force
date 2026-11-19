"""3D scene and hotspots. Frame: x east, y north in km from (61 N, 3 E); depth is measured depth (MD) in m, shown downward.

Wells = vertical segments top..bot per unit (MD stands in for TVD: shown as such in the UI). Surfaces = per formation, kernel-smoothed
mid-depth coloured by the estimated rate, masked beyond reach. Hotspots = 20 km windows whose green share differs from the formation's
rate, tested with a normal approximation scaled by the formation's overdispersion phi (rows in one interval are correlated, so a plain binomial overstates), then a Bonferroni count over windows (exploratory: reports, not geology).
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import norm

from se.evidence.spatial import KM_LAT
from se.jobs import map_job

LAT0, LON0, R_KM, MIN_WELLS, MIN_ROWS = 61.0, 3.0, 20.0, 4, 80


def xy(lat, lon):
    return np.c_[(np.asarray(lon) - LON0) * 111.32 * np.cos(np.radians(LAT0)), (np.asarray(lat) - LAT0) * KM_LAT]


def wells(u: pd.DataFrame, limit: int = 4000) -> list:
    """One segment per unit. `bin`: -1 too few rows, else 0..4 by observed share (so the UI can colour in few traces)."""
    u = u.head(limit)
    p = xy(u.lat, u.lon)
    obs = (u.n_green / u.coverage.where(u.coverage > 0)).to_numpy()
    fin = lambda v: None if pd.isna(v) else round(float(v), 1)
    return [{"unit": a, "x": round(float(x), 2), "y": round(float(y), 2), "top": float(t), "bot": float(b), "rows": int(c), "green": int(g), "obs": None if np.isnan(o) else round(float(o), 3), "kb": fin(k), "wd": fin(d)}
            for a, (x, y), t, b, c, g, o, k, d in zip(u.unit, p, u.top, u.bot, u.coverage, u.n_green, obs, u.kb, u.wd)]


def surface(state, formation: str, lat_min: float = 0.0, lat_max: float = 90.0, res: float = 0.15, ell_z: float = 40.0, dev: str = "cpu") -> dict | None:
    s, tr = state, state.lab[(state.lab.name == formation) & state.lab.lat.between(lat_min, lat_max)]
    if len(tr) < 8:
        return None
    pad = 0.3
    lat = np.arange(tr.lat.min() - pad, tr.lat.max() + pad + 1e-9, res)
    lon = np.arange(tr.lon.min() - 2 * pad, tr.lon.max() + 2 * pad + 1e-9, res * 2)
    LA, LO = np.meshgrid(lat, lon, indexing="ij")
    P, Q = xy(LA.ravel(), LO.ravel()), xy(tr.lat, tr.lon)
    sp, strat = s.layers["spatial"], s.layers["strat"]
    pf = strat.table[formation][0] if formation in strat.table else strat.p0
    t = map_job.weights(P, Q, tr.n_green.to_numpy(float), tr.coverage.to_numpy(float), sp.ell, dev)
    local = (t[:, 0] + sp.k * pf) / (t[:, 1] + sp.k)
    base = np.log(strat.p0 / (1 - strat.p0))
    raw = base + (np.log(pf / (1 - pf)) - base) + (np.log(local / (1 - local)) - np.log(pf / (1 - pf)))
    rate = s.platt(("strat", "spatial"))(raw)
    z = map_job.weights(P, Q, ((tr.top + tr.bot) / 2).to_numpy(float), np.ones(len(tr)), ell_z, dev)
    depth = np.where(z[:, 1] > 1e-6, z[:, 0] / np.maximum(z[:, 1], 1e-12), np.nan)
    sb = ((tr.top + tr.bot) / 2 - (tr.kb + tr.wd)).fillna(0).to_numpy(float)  # mid depth below the seabed: seabed = rig floor height + water depth (checked: shallowest top = kb + wd, LOG L030)
    zs = map_job.weights(P, Q, sb, np.ones(len(tr)), ell_z, dev)
    depth_sb = np.where(zs[:, 1] > 1e-6, zs[:, 0] / np.maximum(zs[:, 1], 1e-12), np.nan)
    kb = float(tr.kb.median()) if tr.kb.notna().any() else 25.0
    reach = t[:, 3] <= 3 * sp.ell
    sh = LA.shape
    cut = lambda a: [[None if (not np.isfinite(v)) else round(float(v), 4) for v in r] for r in a.reshape(sh)]
    ok = reach & np.isfinite(depth)
    X, Y = xy(LA.ravel(), LO.ravel()).T
    return {"formation": formation, "x": np.round(X.reshape(sh)[0], 1).tolist() if False else np.round(X.reshape(sh), 1).tolist(), "y": np.round(Y.reshape(sh), 1).tolist(),
            "depth": cut(np.where(ok, depth, np.nan)), "depth_sb": cut(np.where(ok, depth_sb, np.nan)), "kb": kb, "rate": cut(np.where(ok, rate, np.nan)), "formation_rate": float(pf), "reach_km": 3 * sp.ell}


def hotspots(state) -> list:
    """Windows of R_KM around each unit; hot = more green than the formation rate, cold = less. Greedy 30 km separation."""
    out, lab = [], state.lab
    for f, g in lab.groupby("name"):
        if len(g) < 30 or g.wellbore.nunique() < 15:
            continue
        P, pf = xy(g.lat, g.lon), g.n_green.sum() / g.coverage.sum()
        if not 0 < pf < 1:
            continue
        tree, cov, ng, wid = cKDTree(P), g.coverage.to_numpy(), g.n_green.to_numpy(), g.wellbore.to_numpy()
        phi = max(1.0, float((((ng - cov * pf) ** 2) / (cov * pf * (1 - pf))).sum() / (len(g) - 1)))  # Pearson dispersion over units
        cand = []
        for i, idx in enumerate(tree.query_ball_point(P, R_KM)):
            rows, green, w = int(cov[idx].sum()), int(ng[idx].sum()), len(set(wid[idx]))
            if w < MIN_WELLS or rows < MIN_ROWS:
                continue
            z = (green - rows * pf) / np.sqrt(rows * pf * (1 - pf) * phi)
            kind, p = ("hot", float(norm.sf(z))) if z > 0 else ("cold", float(norm.cdf(z)))
            cand.append((p, i, kind, rows, green, w, idx))
        n_tests = max(len(cand), 1)
        taken = []
        for p, i, kind, rows, green, w, idx in sorted(cand, key=lambda c: c[0]):
            if any(np.hypot(*(P[i] - P[j])) < 30 for j in taken):
                continue
            taken.append(i)
            sub = g.iloc[idx]
            rate = green / rows
            eff = (rows / w) / (g.coverage.sum() / g.wellbore.nunique())
            out.append({"id": f"{f}#{len(taken)}", "formation": f, "kind": kind, "x": round(float(P[i][0]), 1), "y": round(float(P[i][1]), 1), "lat": float(g.lat.iloc[i]), "lon": float(g.lon.iloc[i]),
                        "radius_km": R_KM, "top": float(sub.top.median()), "bot": float(sub.bot.median()), "kb": float(sub.kb.median()) if sub.kb.notna().any() else 25.0, "wd": float(sub.wd.median()) if sub.wd.notna().any() else 0.0, "wells": w, "rows": rows, "green": green, "rate": round(rate, 4), "formation_rate": round(float(pf), 4),
                        "lift": round(rate / pf, 2), "phi": round(phi, 2), "p": float(p), "p_adj": float(min(1.0, p * n_tests)), "tests": n_tests, "effort": round(float(eff), 2),
                        "units": sub.unit.head(30).tolist(),
                        "text": (f"{green} of {rows} {state.words['rows']} {state.words['hit']} ({rate:.1%}) in {w} wells within {R_KM:.0f} km, vs {pf:.1%} across {f}: "
                                 f"{rate / pf:.1f}x {'more' if kind == 'hot' else 'less'}. p={p:.1e} (dispersion {phi:.1f}x), x{n_tests} windows = {min(1.0, p * n_tests):.2g}. "
                                 f"These wells were described {eff:.1f}x as much as the formation average" + (" (reporting effort may explain it)." if eff > 1.5 else "."))})
            if len(taken) >= 5:
                break
    return sorted(out, key=lambda h: h["p_adj"])[:16]
