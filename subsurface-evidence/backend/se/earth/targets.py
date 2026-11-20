"""Targets with probability and support per cell (PLAN P6, LOG L069).

A cell is one unit (formation, else group) in one 2 km column of the grid (P2.4): its top, base, mid depth and thickness come from the grid.
Each target is a binary event that wells can observe for a unit, so it can be scored on held-out wells:
  hydrocarbons     the unit holds HC in a well (FactPages HC formations, DST flow; DRY wells and DST no-flow as no)
  reservoir        core mean porosity > 15 % and permeability > 10 mD in the unit (RealPore)
  overpressure     pore pressure EMW >= 1.20 g/cm3 (DST; mud weight x 0.88 from L060 as weaker evidence)
  green_clay       a described clay row names a green mineral (report text; the original evidence-engine target)
  calcareous_clay  a described clay row is calcareous (report text; saved target 89b4ded077)
  sandy_delta      a deltaic unit (Sodir lexicon says delta) with a FORCE sand share >= 0.4
  co2_storage      not observable in wells: P(supercritical) x P(reservoir) x P(seal >= 50 m) x (1 - P(overpressure)); checked on
                   Smeaheia and Northern Lights (Aurora, 31/5-7) instead of calibrated
Model per target: logistic regression on a few features computed from training wells only (unit prior rate, neighbours' rate in the
same unit, and physical features from P3), blocked 40 km CV, Platt calibration if it helps, Monte Carlo over the feature uncertainty
for a 90 percent range, and a support score.
"""
import json
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from se.config import DATA, EARTH, OUT
from se.earth import manifest

ELL, K_UNIT, K_NB = 25.0, 10.0, 5.0
N_MC = 100
EPS = 1e-4
OUT_T = EARTH / "targets"


def logit(p):
    p = np.clip(p, EPS, 1 - EPS); return np.log(p / (1 - p))


def blocks(x, y, km=40.0):
    return np.floor(x / km).astype(int) * 100003 + np.floor(y / km).astype(int)


# ---------------------------------------------------------------- cells
def cells() -> pd.DataFrame:
    """One row per (column, unit) with positive thickness inside the pilot: i, j, x, y, unit, group, top, base, mid, thickness, zb."""
    g = np.load(EARTH / "grid.npz"); zb, lab, inside = g["zb"].astype(np.float32), g["label"], g["inside"]
    labels = [str(s).split("|") for s in g["labels"]]
    s = np.load(EARTH / "surfaces.npz"); sea = s["mean"][list(s["names"]).index("SEABED")]
    X, Y = np.meshgrid(g["x"], g["y"])
    rows = []
    for li, (gname, fname) in enumerate(labels):
        m = lab == li
        if not m.any():
            continue
        top = np.where(m, zb[:-1], np.inf).min(0); base = np.where(m, zb[1:], -np.inf).max(0)
        ok = inside & np.isfinite(top) & (base - top > 0.5)
        j, i = np.where(ok)
        rows.append(pd.DataFrame({"i": i, "j": j, "x": X[ok], "y": Y[ok], "label": li, "unit": fname or gname, "group": gname,
                                  "top": top[ok], "base": base[ok]}))
    c = pd.concat(rows, ignore_index=True)
    c["thick"] = c.base - c.top; c["mid"] = 0.5 * (c.top + c.base); c["zb"] = c.mid - sea[c.j, c.i]
    return c


# ---------------------------------------------------------------- observations per target
def unit_depths() -> pd.DataFrame:
    t = pd.read_parquet(EARTH / "tops.parquet"); w = pd.read_parquet(EARTH / "wells.parquet").set_index("wellbore")
    t = t.sort_values("top_tvdss").drop_duplicates(["wellbore", "name"])
    t["zb"] = 0.5 * (t.top_tvdss + t.bot_tvdss.fillna(t.top_tvdss + 50)) - t.wellbore.map(w.wd)
    return t.set_index(["wellbore", "name"])[["x", "y", "zb"]]


def observations(target: str) -> pd.DataFrame:
    """wellbore, unit, x, y (position), zb, ev (event: 0/1 or a rate), w (weight: trials or evidence strength)."""
    ud = unit_depths()
    def place(d):
        k = list(zip(d.wellbore, d.unit)); ok = [kk in ud.index for kk in k]
        d = d[ok].copy(); u = ud.loc[[kk for kk, o in zip(k, ok) if o]]
        d["x"], d["y"], d["zb"] = u.x.to_numpy(), u.y.to_numpy(), u.zb.to_numpy()
        return d.dropna(subset=["x", "y", "zb"])
    if target == "hydrocarbons":
        f = pd.read_parquet(EARTH / "fluids.parquet"); f = f[f.source.isin(["fp_hc_unit", "dst_flow", "fp_dry", "dst_no_flow", "fp_not_listed"])]
        f = f.groupby(["wellbore", "unit"]).agg(ev=("hc", "max"), w=("strength", "max")).reset_index()  # any HC evidence wins
        return place(f)
    if target == "reservoir":
        p = pd.read_parquet(EARTH / "poroperm_wells.parquet").dropna(subset=["lk"])
        return place(pd.DataFrame({"wellbore": p.wellbore, "unit": p.unit, "ev": ((p.phi > 15) & (p.lk > 1)).astype(float), "w": np.sqrt(p.n_phi)}))
    if target == "overpressure":
        o = pd.read_parquet(EARTH / "pressure_obs.parquet"); o = o[(o.qc == "ok") & o.unit.notna()]
        d = o[o.kind == "pore"].assign(e=o.emw_ss, w=1.0); m = o[o.kind == "mud"].assign(e=o.emw_ss * 0.88, w=0.3)
        a = pd.concat([d, m]); a["ev"] = (a.e >= 1.20).astype(float)
        a = a.groupby(["wellbore", "unit"]).agg(ev=("ev", "max"), w=("w", "max")).reset_index()
        return place(a[["wellbore", "unit", "ev", "w"]])
    if target in ("green_clay", "calcareous_clay"):
        u = pd.read_parquet(OUT / "units.parquet" if target == "green_clay" else OUT / "targets" / "89b4ded077" / "units.parquet")
        u = u[u.coverage > 0]
        return place(pd.DataFrame({"wellbore": u.wellbore, "unit": u.name, "ev": u.n_green / u.coverage, "w": u.coverage.astype(float)}))
    if target == "sandy_delta":
        wt = pd.read_parquet(EARTH / "lithology_wells.parquet"); cols = [c for c in wt.columns if str(c).isdigit()]
        n = wt[cols].sum(1); sand = (wt[cols[0]] + 0.5 * wt[cols[1]]) / n
        dl = deltaic_units()
        return place(pd.DataFrame({"wellbore": wt.wellbore, "unit": wt.unit, "ev": (wt.unit.isin(dl) & (sand >= 0.4)).astype(float), "w": np.sqrt(n)}))
    raise ValueError(target)


def deltaic_units() -> set:
    """Units whose Sodir lexicon description names a delta (rule R-BRENT generalised; the lexicon is the source)."""
    import duckdb

    c = duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True)
    d = c.execute("select lsuName, lsuDescription from strat_litho_overview").df()
    return set(d[d.lsuDescription.fillna("").str.contains(r"\bdelta(?:ic)?\b|delta plain|delta front|mouth bar|distributary", case=False, regex=True)].lsuName)


# ---------------------------------------------------------------- features (from training rows only)
def nb_features(tr: pd.DataFrame, q: pd.DataFrame, self_out: bool = False) -> pd.DataFrame:
    """Unit prior (shrunk to the global rate) and the neighbours' rate in the same unit (Gaussian ELL km, shrunk to the unit prior),
    with the effective count behind each (for uncertainty and support). self_out: q are training rows; each row's own well is left out
    of its prior and its neighbours, as it would be for a well we have not drilled (L069: without this the model over-trusts the
    neighbour term and loses on held-out wells)."""
    g = np.average(tr.ev, weights=tr.w)
    up = tr.groupby("unit").apply(lambda d: pd.Series({"s": float((d.ev * d.w).sum()), "n": float(d.w.sum())}), include_groups=False)
    prior = ((up.s + K_UNIT * g) / (up.n + K_UNIT)).to_dict(); un = up.n.to_dict()
    out = pd.DataFrame(index=q.index); out["prior"] = q.unit.map(prior).fillna(g).to_numpy(); out["n_unit"] = q.unit.map(un).fillna(0).to_numpy()
    if self_out:  # remove the row's own well from its unit prior
        own = q.groupby(["wellbore", "unit"]).apply(lambda d: pd.Series({"s": float((d.ev * d.w).sum()), "n": float(d.w.sum())}), include_groups=False)
        k = pd.MultiIndex.from_arrays([q.wellbore, q.unit]); os_ = own.s.reindex(k).to_numpy(); on = own.n.reindex(k).to_numpy()
        S, Nn = q.unit.map(up.s).to_numpy() - os_, q.unit.map(up.n).to_numpy() - on
        out["prior"] = (S + K_UNIT * g) / (Nn + K_UNIT); out["n_unit"] = Nn
    nb = np.empty(len(q)); ne = np.zeros(len(q)); dmin = np.full(len(q), np.inf)
    for u, qi in q.groupby("unit").groups.items():
        t = tr[tr.unit == u]; qq = q.loc[qi]; p0 = prior.get(u, g)
        if not len(t):
            nb[q.index.get_indexer(qi)] = p0; continue
        d2 = ((qq[["x", "y"]].to_numpy()[:, None] - t[["x", "y"]].to_numpy()[None]) ** 2).sum(-1)
        wk = np.exp(-0.5 * d2 / ELL ** 2) * t.w.to_numpy()[None]
        if self_out:
            other = qq.wellbore.to_numpy()[:, None] != t.wellbore.to_numpy()[None]
            wk = wk * other; d2 = np.where(other, d2, np.inf)
        s = wk @ t.ev.to_numpy(); n = wk.sum(1)
        ix = q.index.get_indexer(qi)
        nb[ix] = (s + K_NB * p0) / (n + K_NB); ne[ix] = n; dmin[ix] = np.sqrt(d2.min(1))
    out["nb"] = nb; out["n_nb"] = ne; out["d_km"] = dmin
    return out


def phys_features(target: str, q: pd.DataFrame, exclude_wells=None) -> pd.DataFrame:
    """Physical features at query points from P3 models: depth, sand and shale share (lithology, training wells only), Athy porosity."""
    from se.earth import lithology as L
    from se.earth.poroperm import athy

    out = pd.DataFrame(index=q.index); out["zb_km"] = q.zb.to_numpy() / 1000
    if target in ("hydrocarbons", "reservoir", "green_clay", "calcareous_clay", "sandy_delta"):
        wt = pd.read_parquet(EARTH / "lithology_wells.parquet")
        wt = wt.rename(columns={c: int(c) for c in wt.columns if str(c).isdigit()})  # parquet stores the class columns as strings
        if exclude_wells is not None:
            wt = wt[~wt.wellbore.isin(exclude_wells)]
        sand, shale = np.full(len(q), np.nan), np.full(len(q), np.nan)
        for u, qi in q.groupby("unit").groups.items():
            p = L.estimate(wt, q.loc[qi, ["x", "y"]].to_numpy(), u, 25.0, 300.0)
            ix = q.index.get_indexer(qi); sand[ix] = p[:, 0] + 0.5 * p[:, 1]; shale[ix] = p[:, 2] + 0.5 * p[:, 1]
        out["sand"] = sand; out["shale"] = shale
    if target == "reservoir":
        r = json.loads((EARTH / "poroperm_report.json").read_text())["athy_fit"]
        out["phi_athy"] = athy(q.zb.to_numpy(), r["phi0_pct"], r["c_per_km"]) / 100
    if target == "sandy_delta":
        out["deltaic"] = q.unit.isin(deltaic_units()).astype(float).to_numpy()
    return out


FEATS = {"hydrocarbons": ["lp", "lnb", "sand", "zb_km"], "reservoir": ["lp", "lnb", "sand", "phi_athy", "zb_km"], "overpressure": ["lp", "lnb", "zb_km"],
         "green_clay": ["lp", "lnb", "shale", "zb_km"], "calcareous_clay": ["lp", "lnb", "shale", "zb_km"], "sandy_delta": ["lp", "lnb", "deltaic", "sand"]}


def design(target, tr, q, exclude_wells=None, self_out=False):
    nb = nb_features(tr, q, self_out); ph = phys_features(target, q, exclude_wells)
    F = pd.concat([nb, ph], axis=1); F["lp"] = logit(F.prior); F["lnb"] = logit(F.nb)
    return F


def expand(y, w):
    """Fractional labels (rates) as two weighted rows, for the logistic fit."""
    return np.r_[np.ones(len(y)), np.zeros(len(y))], np.r_[w * y, w * (1 - y)]


class Model:
    def __init__(self, cols):
        self.cols = cols

    def fit(self, F, y, w):
        X = F[self.cols].to_numpy(float); self.mu, self.sd = np.nanmean(X, 0), np.nanstd(X, 0) + 1e-9
        Xs = np.nan_to_num((X - self.mu) / self.sd); yy, ww = expand(y, w)
        self.m = LogisticRegression(C=1.0, max_iter=2000).fit(np.r_[Xs, Xs], yy, sample_weight=ww)
        return self

    def p(self, F):
        return self.m.predict_proba(np.nan_to_num((F[self.cols].to_numpy(float) - self.mu) / self.sd))[:, 1]


def deviance(p, y, w):
    p = np.clip(p, EPS, 1 - EPS); return float(-np.sum(w * (y * np.log(p) + (1 - y) * np.log(1 - p))))


def reliability(p, y, w, bins=10):
    q = np.quantile(p, np.linspace(0, 1, bins + 1)); idx = np.clip(np.searchsorted(q, p, side="right") - 1, 0, bins - 1)
    return [{"predicted": round(float(np.average(p[idx == b], weights=w[idx == b])), 4), "observed": round(float(np.average(y[idx == b], weights=w[idx == b])), 4), "weight": round(float(w[idx == b].sum()), 1)}
            for b in range(bins) if (idx == b).any() and w[idx == b].sum() > 0]


def platt(p, y, w):
    a = LogisticRegression(C=1e6, max_iter=1000); yy, ww = expand(y, w); z = np.r_[logit(p), logit(p)][:, None]
    a.fit(z, yy, sample_weight=ww); return lambda q: a.predict_proba(logit(q)[:, None])[:, 1]


def evaluate(target: str, o: pd.DataFrame, folds=5) -> dict:
    """Blocked CV: OOF probabilities of the model and of the unit prior; deviance gain, Brier, reliability, Platt cross-fitted."""
    bl = blocks(o.x.to_numpy(), o.y.to_numpy()); k = min(folds, len(np.unique(bl)))
    p_m, p_0, fo = np.zeros(len(o)), np.zeros(len(o)), np.zeros(len(o), int)
    for f, (tr, te) in enumerate(GroupKFold(k).split(o, groups=bl)):
        a, b = o.iloc[tr], o.iloc[te]; held = set(b.wellbore)
        Fa = design(target, a, a, exclude_wells=held, self_out=True)
        Fb = design(target, a, b, exclude_wells=held)
        m = Model(FEATS[target]).fit(Fa, a.ev.to_numpy(), a.w.to_numpy())
        p_m[te] = m.p(Fb); p_0[te] = Fb.prior.to_numpy(); fo[te] = f
    y, w = o.ev.to_numpy(), o.w.to_numpy(); base = np.average(y, weights=w)
    d_m, d_0, d_g = deviance(p_m, y, w), deviance(p_0, y, w), deviance(np.full(len(y), base), y, w)
    p_c = np.zeros(len(o))  # Platt cross-fitted: the calibration of fold f is fitted on the other folds' OOF
    for f in np.unique(fo):
        p_c[fo == f] = platt(p_m[fo != f], y[fo != f], w[fo != f])(p_m[fo == f])
    d_c = deviance(p_c, y, w)
    return {"rows": int(len(o)), "wells": int(o.wellbore.nunique()), "units": int(o.unit.nunique()), "base_rate": round(float(base), 4), "folds": int(k),
            "gain_model_vs_base": round(1 - d_m / d_g, 4), "gain_unit_prior_vs_base": round(1 - d_0 / d_g, 4), "gain_model_vs_unit_prior": round(1 - d_m / d_0, 4),
            "gain_calibrated_vs_base": round(1 - d_c / d_g, 4), "use_platt": bool(d_c < d_m),
            "brier_model": round(float(np.average((p_m - y) ** 2, weights=w)), 4), "brier_unit_prior": round(float(np.average((p_0 - y) ** 2, weights=w)), 4),
            "reliability": reliability(p_c if d_c < d_m else p_m, y, w)}, (p_m, p_c, y, w)


# ---------------------------------------------------------------- realisations, support
def monte_carlo(m: Model, F: pd.DataFrame, cal, n=N_MC, seed=0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample the uncertain inputs (rates by their effective counts, depth by 10 percent, shares by beta-like sd) and push them through the
    fitted model; torch on cuda when available. Returns mean, p05, p95."""
    try:
        import torch
        dev = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        torch = None
    rng = np.random.default_rng(seed)
    base = F.copy(); draws = []
    sd = {"prior": np.sqrt(base.prior * (1 - base.prior) / (base.n_unit + K_UNIT)), "nb": np.sqrt(base.nb * (1 - base.nb) / (base.n_nb + K_NB))}
    coef = m.m.coef_[0]; b0 = m.m.intercept_[0]; mu, s = m.mu, m.sd
    cols = m.cols
    X0 = base[cols].to_numpy(float)
    noise_sd = np.zeros_like(X0)
    for ci, c in enumerate(cols):
        if c == "lp":
            noise_sd[:, ci] = (sd["prior"] / np.clip(base.prior * (1 - base.prior), EPS, None)).to_numpy()  # delta method on the logit
        elif c == "lnb":
            noise_sd[:, ci] = (sd["nb"] / np.clip(base.nb * (1 - base.nb), EPS, None)).to_numpy()
        elif c == "zb_km":
            noise_sd[:, ci] = 0.1 * np.abs(X0[:, ci])
        elif c in ("sand", "shale", "phi_athy"):
            noise_sd[:, ci] = 0.1
    X0, noise_sd = np.nan_to_num(X0), np.nan_to_num(noise_sd)
    if torch is not None:
        T = lambda a: torch.as_tensor(a, dtype=torch.float32, device=dev)
        Xt, St = T(X0), T(noise_sd); W, B, Mu, Sd = T(coef), float(b0), T(mu), T(s)
        g = torch.Generator(device=dev).manual_seed(seed)
        ps = []
        for _ in range(n):
            Z = Xt + St * torch.randn(Xt.shape, generator=g, device=dev)
            ps.append(torch.sigmoid(((Z - Mu) / Sd) @ W + B))
        P = torch.stack(ps).cpu().numpy()
    else:
        P = np.stack([1 / (1 + np.exp(-(((X0 + noise_sd * rng.standard_normal(X0.shape)) - mu) / s) @ coef - b0)) for _ in range(n)])
    if cal is not None:
        P = np.stack([cal(p) for p in P])
    return P.mean(0), np.percentile(P, 5, axis=0), np.percentile(P, 95, axis=0)


def support(F: pd.DataFrame, skill: float) -> np.ndarray:
    """0-1: how much this cell's probability rests on data. data = 1 - exp(-n/3) (n: kernel-weighted observations of this unit within
    about ELL km), near = exp(-d/30 km) (nearest observation of this unit), skill = clip(held-out gain / 0.1, 0.2, 1)."""
    data = 1 - np.exp(-np.nan_to_num(F.n_nb.to_numpy()) / 3.0)
    near = np.exp(-np.nan_to_num(F.d_km.to_numpy(), nan=999.0, posinf=999.0) / 30.0)
    return np.clip(data * near * float(np.clip(skill / 0.1, 0.2, 1.0)), 0, 1)


# ---------------------------------------------------------------- CO2 (composite, not calibrated)
def co2(C: pd.DataFrame, P: dict) -> tuple[np.ndarray, dict]:
    from scipy.stats import norm as N

    from se.earth.temperature import predict as temp

    T, sT = temp(C.x.to_numpy(), C.y.to_numpy(), C.zb.to_numpy())
    sea = C.mid - C.zb
    Ph = 0.1013 + 0.00981 * 1.03 * (C.top.to_numpy())  # hydrostatic at the unit top (sea level datum)
    p_T = 1 - N.cdf((31.1 - T) / np.maximum(sT, 1.0)); p_P = (Ph > 7.38).astype(float)
    seal = np.load(EARTH / "seal_above.npy"); g = np.load(EARTH / "grid.npz"); lab = g["label"]
    first_k = np.full(len(C), 0)
    zb = g["zb"]
    for li, idx in C.groupby("label").groups.items():
        sub = C.loc[idx]; m = (lab[:, sub.j.to_numpy(), sub.i.to_numpy()] == li)
        first_k[C.index.get_indexer(idx)] = m.argmax(0)
    s_above = seal[first_k, C.j.to_numpy(), C.i.to_numpy()]
    p_seal = 1 - N.cdf((50.0 - s_above) / np.maximum(0.3 * s_above, 10.0))
    p = p_T * p_P * P["reservoir"] * p_seal * (1 - P["overpressure"])
    return p, {"terms": "P(T > 31.1 C) x P(P > 7.38 MPa, hydrostatic) x P(reservoir) x P(seal above >= 50 m) x (1 - P(overpressure))",
               "seal_sigma": "30 percent of the grid thickness, at least 10 m"}


def checks_co2(C, p) -> dict:
    """Known storage sites: Smeaheia (Sognefjord around 32/2-1 and 32/4-1) and Northern Lights / Aurora (Johansen, Cook at 31/5-7)."""
    w = pd.read_parquet(EARTH / "wells.parquet").set_index("wellbore")
    out = {}
    for name, wb, units in (("Smeaheia", "32/2-1", ["SOGNEFJORD FM", "FENSFJORD FM"]), ("Smeaheia", "32/4-1", ["SOGNEFJORD FM", "FENSFJORD FM"]),
                            ("Northern Lights (Aurora)", "31/5-7", ["JOHANSEN FM", "COOK FM"])):
        if wb not in w.index:
            continue
        d = np.hypot(C.x - w.x[wb], C.y - w.y[wb]); m = (d < 3) & C.unit.isin(units)
        allm = d < 3
        out[f"{name} {wb}"] = {u: round(float(p[m & (C.unit == u)].mean()), 3) if (m & (C.unit == u)).any() else None for u in units} | \
            {"best_other_unit_here": round(float(p[allm & ~C.unit.isin(units)].max()), 3) if (allm & ~C.unit.isin(units)).any() else None,
             "pilot_median": round(float(np.median(p)), 4), "pilot_p95": round(float(np.percentile(p, 95)), 3)}
    return out


def build(targets=("hydrocarbons", "reservoir", "overpressure", "green_clay", "calcareous_clay", "sandy_delta")) -> dict:
    t0 = time.time(); OUT_T.mkdir(parents=True, exist_ok=True)
    C = cells(); rep, P, S = {}, {}, {}
    for t in targets:
        o = observations(t).reset_index(drop=True)
        ev, (p_m, p_c, y, w) = evaluate(t, o)
        Fo = design(t, o, o, self_out=True); m = Model(FEATS[t]).fit(Fo, o.ev.to_numpy(), o.w.to_numpy())
        cal = platt(p_m, y, w) if ev["use_platt"] else None
        FC = design(t, o, C)
        # publish the simplest form that is not worse on held-out wells: model, unit prior, or the pilot base rate (L069)
        gains = {"model": max(ev["gain_model_vs_base"], ev["gain_calibrated_vs_base"]), "unit prior": ev["gain_unit_prior_vs_base"], "base rate": 0.0}
        ev["published"] = pub = max(gains, key=gains.get)
        if pub == "model":
            mean, lo, hi = monte_carlo(m, FC, cal)
        elif pub == "unit prior":
            mean = FC.prior.to_numpy(); sdp = np.sqrt(mean * (1 - mean) / (FC.n_unit.to_numpy() + K_UNIT)); lo, hi = np.clip(mean - 1.645 * sdp, 0, 1), np.clip(mean + 1.645 * sdp, 0, 1)
        else:
            mean = np.full(len(C), ev["base_rate"]); lo = hi = mean
        sup = support(FC, gains[pub])
        P[t], S[t] = mean, sup
        ev["coefficients"] = dict(zip(FEATS[t], np.round(m.m.coef_[0], 3).tolist()))
        ev["cells"] = int(len(C)); ev["p_median"] = round(float(np.median(mean)), 4); ev["support_median"] = round(float(np.median(sup)), 3)
        np.savez_compressed(OUT_T / f"{t}.npz", i=C.i.to_numpy(np.int16), j=C.j.to_numpy(np.int16), label=C.label.to_numpy(np.int16), p=mean.astype(np.float32),
                            p05=lo.astype(np.float32), p95=hi.astype(np.float32), support=sup.astype(np.float32))
        rep[t] = ev
        print(t, {k: v for k, v in ev.items() if k not in ("reliability",)}, round(time.time() - t0), "s", flush=True)
    pc, info = co2(C, P)
    np.savez_compressed(OUT_T / "co2_storage.npz", i=C.i.to_numpy(np.int16), j=C.j.to_numpy(np.int16), label=C.label.to_numpy(np.int16), p=pc.astype(np.float32),
                        p05=pc.astype(np.float32), p95=pc.astype(np.float32), support=np.minimum(S["reservoir"], S["overpressure"]).astype(np.float32))
    rep["co2_storage"] = {"composite": info, "calibrated": False, "why": "no well observes stored CO2", "checks": checks_co2(C, pc), "cells": int(len(C)),
                          "p_median": round(float(np.median(pc)), 4)}
    C[["i", "j", "x", "y", "label", "unit", "group", "top", "base", "thick", "zb"]].to_parquet(OUT_T / "cells.parquet")
    (OUT_T / "report.json").write_text(json.dumps(rep, indent=1, default=float))
    manifest.write(OUT_T / "cells.parquet", [EARTH / "grid.npz", EARTH / "surfaces.npz", EARTH / "fluids.parquet", EARTH / "poroperm_wells.parquet", EARTH / "pressure_obs.parquet",
                                             EARTH / "lithology_wells.parquet", OUT / "units.parquet"], {"ell_km": ELL, "k_unit": K_UNIT, "k_nb": K_NB, "n_mc": N_MC})
    rep["_seconds"] = round(time.time() - t0, 1)
    return rep


if __name__ == "__main__":
    r = build()
    print(json.dumps(r.get("co2_storage"), indent=1, default=float))
