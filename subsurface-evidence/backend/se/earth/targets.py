"""Targets with probability and support per cell (PLAN P6, LOG L069).

A cell is one unit (formation, else group) in one 2 km column of the grid (P2.4): its top, base, mid depth and thickness come from the grid.
Each target is a binary event that wells can observe for a unit, so it can be scored on held-out wells:
  hydrocarbons     the unit holds HC in a well (FactPages HC formations, DST flow; DRY wells and DST no-flow as no)
  oil, gas         the same split by phase (FactPages well content, DST oil and gas rates); "oil and gas" counts for both (P9.8)
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
P9: petroleum-system factors (se/earth/factors.py: source maturity, faults, highs, closures, salt) are candidate features; a candidate is
added (forward selection) only if it raises the held-out deviance gain by MIN_GAIN. Selection uses the same folds it is scored on, so the
forward-in-time test (train on wells completed before YEAR, test on later wells) is the independent check of the chosen set.
Probabilities are conditional on where wells were drilled: wells target structures thought to hold oil or gas (see CONDITIONAL).
"""
import json
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from se.config import DATA, EARTH, OUT
from se.earth import atomic, manifest
from se.earth.folds import blocks

ELL, K_UNIT, K_NB = 25.0, 10.0, 5.0
MIN_GAIN, YEAR = 0.005, 2005
CONDITIONAL = ("P(event | a well is drilled here). Exploration wells are placed on structures that were thought to hold oil or gas, so the "
               "training wells are not a random sample of the subsurface; between wells and in undrilled settings the probability is an extrapolation")
N_MC = 100
EPS = 1e-4
OUT_T = EARTH / "targets"


def logit(p):
    p = np.clip(p, EPS, 1 - EPS); return np.log(p / (1 - p))




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
    if target in ("oil", "gas"):
        f = pd.read_parquet(EARTH / "fluids.parquet"); f = f[f.source.isin(["fp_hc_unit", "dst_flow", "fp_dry", "dst_no_flow", "fp_not_listed"])]
        known = (f.hc == 0) | f.fluid.isin(["oil", "gas", "oil and gas"])  # HC of unknown phase says nothing about the phase
        f = f[known].assign(ev=lambda d: d.fluid.isin([target, "oil and gas"]).astype(float))
        return place(f.groupby(["wellbore", "unit"]).agg(ev=("ev", "max"), w=("strength", "max")).reset_index())
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
    up = tr.assign(s=tr.ev * tr.w).groupby("unit").agg(s=("s", "sum"), n=("w", "sum"))  # one grouped sum (P10.1: was a Python lambda per group)
    prior = ((up.s + K_UNIT * g) / (up.n + K_UNIT)).to_dict(); un = up.n.to_dict()
    out = pd.DataFrame(index=q.index); out["prior"] = q.unit.map(prior).fillna(g).to_numpy(); out["n_unit"] = q.unit.map(un).fillna(0).to_numpy()
    if self_out:  # remove the row's own well from its unit prior
        own = q.assign(s=q.ev * q.w).groupby(["wellbore", "unit"]).agg(s=("s", "sum"), n=("w", "sum"))
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
    if target in ("hydrocarbons", "oil", "gas", "reservoir", "green_clay", "calcareous_clay", "sandy_delta"):
        wt = pd.read_parquet(EARTH / "lithology_wells.parquet")
        wt = wt.rename(columns={c: int(c) for c in wt.columns if str(c).isdigit()})  # parquet stores the class columns as strings
        if exclude_wells is not None:
            wt = wt[~wt.wellbore.isin(exclude_wells)]
        sand, shale = np.full(len(q), np.nan), np.full(len(q), np.nan)
        for u, qi in q.groupby("unit").groups.items():
            p = L.estimate(wt, q.loc[qi, ["x", "y"]].to_numpy(), u, 25.0, 300.0)
            ix = q.index.get_indexer(qi); sand[ix] = p[:, 0] + 0.5 * p[:, 1]; shale[ix] = p[:, 2] + 0.5 * p[:, 1]
        out["sand"] = sand; out["shale"] = shale
    if target == "reservoir":  # the adopted compaction trend of P3.2 / P9.2 (Athy, or with burial or quartz cement)
        from se.earth.grid import at_columns
        from se.earth.poroperm import trend

        s = np.load(EARTH / "surfaces.npz"); sea = s["mean"][list(s["names"]).index("SEABED")]
        x, y = q.x.to_numpy(float), q.y.to_numpy(float)
        out["phi_athy"] = trend(x, y, q.zb.to_numpy(float), at_columns(sea, x, y)) / 100
    if target == "sandy_delta":
        out["deltaic"] = q.unit.isin(deltaic_units()).astype(float).to_numpy()
    if CAND.get(target) and (EARTH / "factors.npz").exists():
        from se.earth.factors import at

        out = pd.concat([out, at(q)], axis=1)
    return out


FEATS = {"hydrocarbons": ["lp", "lnb", "sand", "zb_km"], "reservoir": ["lp", "lnb", "sand", "phi_athy", "zb_km"], "overpressure": ["lp", "lnb", "zb_km"],
         "green_clay": ["lp", "lnb", "shale", "zb_km"], "calcareous_clay": ["lp", "lnb", "shale", "zb_km"], "sandy_delta": ["lp", "lnb", "deltaic", "sand"]}
FEATS["oil"] = FEATS["gas"] = FEATS["hydrocarbons"]
_HC = ["lkit", "lkit_max", "mature", "lfault", "on_high", "lclos", "salt", "lcharge", "lcharge_max", "p_charge", "p_charge_max"]
CAND = {"hydrocarbons": _HC, "oil": _HC, "gas": _HC + ["lkit_gas"], "overpressure": ["mature", "lkit", "lfault", "salt"], "reservoir": ["lfault", "on_high"]}
NOISE = {"lkit": 0.2, "lkit_max": 0.3, "lkit_gas": 0.2, "mature": 0.1, "lfault": 0.1, "lclos": 0.3, "on_high": 0.0, "lcharge": 0.5, "lcharge_max": 0.5,
         "p_charge": 0.1, "p_charge_max": 0.1, "salt": 0.05, "sand": 0.1, "shale": 0.1, "phi_athy": 0.05}  # sd in feature units (MC)
CORR_KM = {"lnb": ELL, "zb_km": 20.0, "phi_athy": 15.0}  # correlation length of each input's error in the Monte Carlo (P10.3); others 25 km
FAMILIES = ("logistic", "gbm", "spline")
FAMILY_MARGIN = 0.01  # a non-linear family must beat logistic by this much on held-out blocks, and not lose forward in time (P10.6)
N_MC_NL = 40  # Monte Carlo draws for the non-linear families (each draw is a full model evaluation)
N_BOOT = 40  # cluster-bootstrap refits (whole wells) for the coefficient uncertainty (P12.3)


def design(target, tr, q, exclude_wells=None, self_out=False):
    nb = nb_features(tr, q, self_out); ph = phys_features(target, q, exclude_wells)
    F = pd.concat([nb, ph], axis=1); F["lp"] = logit(F.prior); F["lnb"] = logit(F.nb)
    return F


def expand(y, w):
    """Fractional labels (rates) as two weighted rows, for the logistic fit."""
    return np.r_[np.ones(len(y)), np.zeros(len(y))], np.r_[w * y, w * (1 - y)]


class Model:
    """Probability of the event from features. Families (P10.6): logistic (linear in standardised features), gbm (histogram gradient
    boosting, shallow trees: interactions and thresholds), spline (logistic on cubic splines of the physical features, the rates kept
    linear: a GAM-like smooth model). Fractional labels enter as two weighted rows (expand)."""
    def __init__(self, cols, family="logistic"):
        self.cols, self.family = cols, family

    def _X(self, F):
        return self.scale(F[self.cols].to_numpy(float))

    def scale(self, X):
        """Standardise, after clipping each input to its 1-99 percent training range: no extrapolation beyond the drilled range (P10.1)."""
        return np.nan_to_num((np.clip(X, self.lo, self.hi) - self.mu) / self.sd)

    def fit(self, F, y, w):
        X = F[self.cols].to_numpy(float); self.mu, self.sd = np.nanmean(X, 0), np.nanstd(X, 0) + 1e-9
        self.lo, self.hi = np.nanpercentile(X, 1, axis=0), np.nanpercentile(X, 99, axis=0)
        Xs = self._X(F); yy, ww = expand(y, w); XX = np.r_[Xs, Xs]
        if self.family == "gbm":
            from sklearn.ensemble import HistGradientBoostingClassifier

            self.m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=250, min_samples_leaf=40, l2_regularization=1.0, random_state=0).fit(XX, yy, sample_weight=ww)
        elif self.family == "spline":
            from sklearn.compose import ColumnTransformer
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import SplineTransformer

            smooth = [k for k, c in enumerate(self.cols) if c not in ("lp", "lnb") and len(np.unique(Xs[:, k])) > 5]
            ct = ColumnTransformer([("s", SplineTransformer(n_knots=5, degree=3, extrapolation="linear"), smooth)], remainder="passthrough")
            self.m = make_pipeline(ct, LogisticRegression(C=0.5, max_iter=3000)).fit(XX, yy, logisticregression__sample_weight=ww)
        else:
            self.m = LogisticRegression(C=1.0, max_iter=2000).fit(XX, yy, sample_weight=ww)
        return self

    def p(self, F):
        return self.m.predict_proba(self._X(F))[:, 1]

    def coef(self) -> dict:
        return dict(zip(self.cols, np.round(self.m.coef_[0], 3).tolist())) if self.family == "logistic" else {"family": self.family}


def deviance(p, y, w):
    p = np.clip(p, EPS, 1 - EPS); return float(-np.sum(w * (y * np.log(p) + (1 - y) * np.log(1 - p))))


def reliability(p, y, w, bins=10):
    q = np.quantile(p, np.linspace(0, 1, bins + 1)); idx = np.clip(np.searchsorted(q, p, side="right") - 1, 0, bins - 1)
    return [{"predicted": round(float(np.average(p[idx == b], weights=w[idx == b])), 4), "observed": round(float(np.average(y[idx == b], weights=w[idx == b])), 4), "weight": round(float(w[idx == b].sum()), 1)}
            for b in range(bins) if (idx == b).any() and w[idx == b].sum() > 0]


def platt(p, y, w):
    a = LogisticRegression(C=1e6, max_iter=1000); yy, ww = expand(y, w); z = np.r_[logit(p), logit(p)][:, None]
    a.fit(z, yy, sample_weight=ww); return lambda q: a.predict_proba(logit(q)[:, None])[:, 1]


def fold_designs(target: str, o: pd.DataFrame, folds=5) -> list:
    """Blocked 40 km folds with the training and held-out design matrices (all candidate columns), computed once."""
    bl = blocks(o.x.to_numpy(), o.y.to_numpy()); k = min(folds, len(np.unique(bl)))
    out = []
    for tr, te in GroupKFold(k).split(o, groups=bl):
        a, b = o.iloc[tr], o.iloc[te]; held = set(b.wellbore)
        out.append((tr, te, design(target, a, a, exclude_wells=held, self_out=True), design(target, a, b, exclude_wells=held)))
    return out


def select(target: str, o: pd.DataFrame, FD: list) -> tuple[list, list]:
    """Forward selection over CAND[target]: add the candidate that raises the held-out gain most, while it adds at least MIN_GAIN."""
    cols = list(FEATS[target]); best = evaluate(target, o, cols, FD)[0]["gain_model_vs_base"]; path = [{"features": list(cols), "gain": best}]
    left = [c for c in CAND.get(target, []) if c in FD[0][2].columns and FD[0][2][c].nunique() > 1]
    while left:
        g = {c: evaluate(target, o, cols + [c], FD)[0]["gain_model_vs_base"] for c in left}; c = max(g, key=g.get)
        path.append({"tried": {k: round(v, 4) for k, v in g.items()}})
        if g[c] < best + MIN_GAIN:
            break
        cols.append(c); left.remove(c); best = g[c]; path.append({"added": c, "gain": best})
    return cols, path


def nested_gain(target: str, o: pd.DataFrame, FD: list, family="logistic") -> tuple[float, list]:
    """Held-out gain with the feature selection redone inside each outer training fold (inner blocked folds), so the score does not
    reuse the folds the features were chosen on (P10.1: the selected-on-the-same-folds gain is optimistic)."""
    p = np.zeros(len(o)); chosen = []
    for tr, te, Fa, Fb in FD:
        a = o.iloc[tr].reset_index(drop=True); inner = fold_designs(target, a, folds=4); cols, _ = select(target, a, inner)
        chosen.append(cols); p[te] = Model(cols, family).fit(Fa, a.ev.to_numpy(), a.w.to_numpy()).p(Fb)
    y, w = o.ev.to_numpy(), o.w.to_numpy()
    return round(1 - deviance(p, y, w) / deviance(np.full(len(o), np.average(y, weights=w)), y, w), 4), chosen


def evaluate(target: str, o: pd.DataFrame, cols=None, FD=None, family="logistic") -> dict:
    """Blocked CV: OOF probabilities of the model and of the unit prior; deviance gain, Brier, reliability, Platt cross-fitted."""
    cols = cols or FEATS[target]; FD = FD or fold_designs(target, o)
    p_m, p_0, fo = np.zeros(len(o)), np.zeros(len(o)), np.zeros(len(o), int)
    for f, (tr, te, Fa, Fb) in enumerate(FD):
        a = o.iloc[tr]
        m = Model(cols, family).fit(Fa, a.ev.to_numpy(), a.w.to_numpy())
        p_m[te] = m.p(Fb); p_0[te] = Fb.prior.to_numpy(); fo[te] = f
    k = len(FD)
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


REFIT = {"phi_athy", "lkit", "lkit_max", "lkit_gas", "mature"}  # inputs from physical models fitted on wells (temperature, porosity, burial)
SURFACE_BASED = {"lclos", "lcharge", "lcharge_max", "p_charge", "p_charge_max"}  # from surfaces kriged on all wells (not refitted per fold)


def refit_check(t: str, o: pd.DataFrame, cols: list, FD: list, family: str) -> dict:
    """P12.2: the held-out gain with the physical inputs refitted inside each fold (temperature, porosity trend, burial and maturity
    fitted without the fold's held-out wells), beside the gain with the shared fit. A drop would mean the shared fit leaked held-out
    information into the inputs. Surface-based inputs are listed, not refitted (a surface fit per fold takes an hour per region)."""
    use = [c for c in cols if c in REFIT]; out = {"refit_inputs": use, "surface_based_inputs_in_model": [c for c in cols if c in SURFACE_BASED]}
    if not use:
        return out | {"why": "no input of this model comes from a physical model fitted on wells"}
    from se.earth.factors import at, maturity
    from se.earth.grid import at_columns
    from se.earth.poroperm import trend

    s = np.load(EARTH / "surfaces.npz"); sea = s["mean"][list(s["names"]).index("SEABED")]
    p0, p1 = np.zeros(len(o)), np.zeros(len(o))
    for tr, te, Fa, Fb in FD:
        a, b = o.iloc[tr], o.iloc[te]; held = set(b.wellbore); Fa2, Fb2 = Fa.copy(), Fb.copy()
        if set(use) - {"phi_athy"}:
            M = maturity(exclude=held); maps = {k: M[k].astype(np.float32) for k in ("p_oil", "p_gas", "p_max", "kit_oil", "kit_gas", "kit_max")}
            for F2, q in ((Fa2, a), (Fb2, b)):
                f = at(q, maps)
                for c in use:
                    if c in f:
                        F2[c] = f[c].to_numpy()
        if "phi_athy" in use:
            for F2, q in ((Fa2, a), (Fb2, b)):
                x, y = q.x.to_numpy(float), q.y.to_numpy(float)
                F2["phi_athy"] = trend(x, y, q.zb.to_numpy(float), at_columns(sea, x, y), exclude=held) / 100
        p0[te] = Model(cols, family).fit(Fa, a.ev.to_numpy(), a.w.to_numpy()).p(Fb)
        p1[te] = Model(cols, family).fit(Fa2, a.ev.to_numpy(), a.w.to_numpy()).p(Fb2)
    y, w = o.ev.to_numpy(), o.w.to_numpy(); d_g = deviance(np.full(len(o), np.average(y, weights=w)), y, w)
    g0, g1 = 1 - deviance(p0, y, w) / d_g, 1 - deviance(p1, y, w) / d_g
    return out | {"gain_shared_fit": round(g0, 4), "gain_refit_per_fold": round(g1, 4), "difference": round(g1 - g0, 4)}


def completion_year() -> pd.Series:
    import duckdb

    from se.ingest.names import norm

    c = duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True)
    d = c.execute("select wlbWellboreName w, wlbCompletionYear y from wellbore_exploration union all select wlbWellboreName, wlbCompletionYear from wellbore_development").df()
    d["w"] = d.w.map(norm); return d.dropna().drop_duplicates("w").set_index("w").y.astype(float)


def time_test(target: str, o: pd.DataFrame, cols: list, families=("logistic",)) -> dict:
    """Forward in time: fit on wells completed before YEAR, score on wells completed from YEAR on (gain vs the training base rate)."""
    yr = o.wellbore.map(completion_year()); a, b = o[yr < YEAR], o[yr >= YEAR]
    if len(a) < 30 or len(b) < 30 or b.ev.nunique() < 2:
        return {"year": YEAR, "train_rows": int(len(a)), "test_rows": int(len(b)), "why": "too few rows on one side of the split"}
    held = set(b.wellbore); Fa = design(target, a, a, exclude_wells=held, self_out=True); Fb = design(target, a, b, exclude_wells=held)
    y, w = b.ev.to_numpy(), b.w.to_numpy(); d_g = deviance(np.full(len(b), np.average(a.ev, weights=a.w)), y, w)
    g = lambda p: round(1 - deviance(p, y, w) / d_g, 4)
    out = {"year": YEAR, "train_rows": int(len(a)), "test_rows": int(len(b)), "test_wells": int(b.wellbore.nunique()),
           "gain_unit_prior": g(Fb.prior.to_numpy()), "gain_base_features": g(Model(FEATS[target]).fit(Fa, a.ev.to_numpy(), a.w.to_numpy()).p(Fb))}
    out["gain_selected_features"] = g(Model(cols).fit(Fa, a.ev.to_numpy(), a.w.to_numpy()).p(Fb)) if cols != FEATS[target] else out["gain_base_features"]
    out["gain_by_family"] = {f: (out["gain_selected_features"] if f == "logistic" else g(Model(cols, f).fit(Fa, a.ev.to_numpy(), a.w.to_numpy()).p(Fb))) for f in families}
    return out


# ---------------------------------------------------------------- realisations, support
def boot_models(t: str, o: pd.DataFrame, Fo: pd.DataFrame, cols: list, family: str, n=N_BOOT, seed=0) -> list:
    """Refits on wells drawn with replacement (each well's rows keep their weight times its draw count): the spread of the coefficients
    that the data allow. Combined with the input draws, the 90 percent range covers both (P12.3)."""
    rng = np.random.default_rng(seed); wb = o.wellbore.to_numpy(); u, inv = np.unique(wb, return_inverse=True); out = []
    for _ in range(n):
        c = np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u))[inv]; k = c > 0
        if o.ev[k].nunique() < 2:
            continue
        out.append(Model(cols, family).fit(Fo[k], o.ev.to_numpy()[k], (o.w.to_numpy() * c)[k]))
    return out


def monte_carlo(m, F: pd.DataFrame, cal, n=N_MC, seed=0, cells=None, zsd=None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Realisations of the uncertain inputs pushed through the fitted model; returns mean, p05, p95 per cell.
    Rates (unit prior, neighbours' rate) are drawn from their beta distribution, Beta(rate x count, (1 - rate) x count) with the
    shrinkage count, and enter as logits. P10.1 fix: the earlier normal noise on the logit (delta method) is far too wide for rare events
    and pulled every rare target towards 0.5. Other inputs: normal with sd from NOISE, depth from the surfaces' sigma at the column.
    P10.3: errors are spatially correlated: a Matern 3/2 random field over the grid columns per input (correlation CORR_KM, 25 km by
    default), mapped through the normal CDF for the beta draws; the unit prior is one draw per unit. Torch device from folds.device()."""
    from scipy.special import betaincinv, ndtr

    from se.earth.folds import device
    from se.earth.gp import prior_field

    ms = m if isinstance(m, list) else [m]; m = ms[0]  # several models (bootstrap refits): draw k uses model k mod len
    rng = np.random.default_rng(seed); cols = m.cols; X0 = np.nan_to_num(F[cols].to_numpy(float))
    nl = m.family != "logistic"; n = min(n, N_MC_NL) if nl else n
    if cells is not None:
        col_id = pd.factorize(pd.Series(list(zip(cells.i.to_numpy(), cells.j.to_numpy()))))[0]
        xy = cells.groupby(col_id)[["x", "y"]].first().to_numpy()  # row k = column code k
    unit_id = pd.factorize(cells.unit)[0] if cells is not None else np.zeros(len(F), int)
    beta = {"lp": (F.prior.to_numpy(), F.n_unit.to_numpy() + K_UNIT), "lnb": (F.nb.to_numpy(), F.n_nb.to_numpy() + K_NB)}
    sd = {}
    for ci, c in enumerate(cols):
        if c in beta:
            continue
        sd[c] = np.nan_to_num(zsd / 1000) if c == "zb_km" and zsd is not None else (0.1 * np.abs(X0[:, ci]) if c == "zb_km" else np.full(len(X0), NOISE.get(c, 0.0)))
    fields = {}
    for ci, c in enumerate(cols):  # one correlated field per input, at column level (n draws), indexed per cell when drawn
        if c not in beta and not sd[c].any():
            continue
        if cells is None:
            fields[c] = ("cell", rng.standard_normal((len(X0), n)))
        elif c == "lp":
            fields[c] = ("unit", rng.standard_normal((unit_id.max() + 1, n)))
        else:
            fields[c] = ("col", prior_field(xy, CORR_KM.get(c, 25.0), n, seed=seed + 17 * ci, features=1000, device=device()))
    def draw(k):
        X = X0.copy()
        for ci, c in enumerate(cols):
            if c not in fields:
                continue
            kind, f = fields[c]; z = f[:, k][col_id] if kind == "col" else f[:, k][unit_id] if kind == "unit" else f[:, k]
            if c in beta:
                r, cnt = beta[c]; a = np.clip(r * cnt, 1e-6, None); b = np.clip((1 - r) * cnt, 1e-6, None)
                X[:, ci] = logit(betaincinv(a, b, np.clip(ndtr(z), 1e-9, 1 - 1e-9)))
            else:
                X[:, ci] = X0[:, ci] + sd[c] * z
        return X
    if not nl:
        import torch

        T = lambda a: torch.as_tensor(a, dtype=torch.float32, device=device())
        P = np.stack([torch.sigmoid(T(ms[k % len(ms)].scale(draw(k))) @ T(ms[k % len(ms)].m.coef_[0]) + float(ms[k % len(ms)].m.intercept_[0])).cpu().numpy() for k in range(n)])
    else:
        P = np.stack([ms[k % len(ms)].m.predict_proba(ms[k % len(ms)].scale(draw(k)))[:, 1] for k in range(n)])
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
def co2_terms(C: pd.DataFrame) -> dict:
    """The physical CO2 terms per cell: P(T > 31.1 C), P(P > 7.38 MPa, hydrostatic at the unit top), P(seal above >= 50 m), and the seal
    thickness above (m). Shared by the CO2 composite, the chance of success (P10.5) and the capacity (P10.4)."""
    from scipy.stats import norm as N

    from se.earth.temperature import predict as temp

    sea = C.mid - C.zb
    T, sT = temp(C.x.to_numpy(), C.y.to_numpy(), C.zb.to_numpy(), sea.to_numpy())
    Ph = 0.1013 + 0.00981 * 1.03 * (C.top.to_numpy())  # hydrostatic at the unit top (sea level datum)
    seal = np.load(EARTH / "seal_above.npy"); g = np.load(EARTH / "grid.npz"); lab = g["label"]
    first_k = np.full(len(C), 0)
    for li, idx in C.groupby("label").groups.items():
        sub = C.loc[idx]; m = (lab[:, sub.j.to_numpy(), sub.i.to_numpy()] == li)
        first_k[C.index.get_indexer(idx)] = m.argmax(0)
    s_above = seal[first_k, C.j.to_numpy(), C.i.to_numpy()]
    return {"T": T, "sT": sT, "p_T": 1 - N.cdf((31.1 - T) / np.maximum(sT, 1.0)), "p_P": (Ph > 7.38).astype(float), "seal_m": s_above,
            "p_seal": 1 - N.cdf((50.0 - s_above) / np.maximum(0.3 * s_above, 10.0))}


def co2(C: pd.DataFrame, P: dict, k: dict) -> tuple[np.ndarray, dict]:
    p = k["p_T"] * k["p_P"] * P["reservoir"] * k["p_seal"] * (1 - P["overpressure"])
    return p, {"terms": "P(T > 31.1 C) x P(P > 7.38 MPa, hydrostatic) x P(reservoir) x P(seal above >= 50 m) x (1 - P(overpressure))",
               "seal_sigma": "30 percent of the grid thickness, at least 10 m"}


TRAP_FLOOR = 0.2  # P(trap) where our surfaces show no closure: traps too small, fault-bounded or stratigraphic for 2-4 km kriged tops (assumption)
ELEMENTS = ("reservoir", "seal", "charge", "trap")


def cos(C: pd.DataFrame, P: dict, k: dict, zsd: np.ndarray) -> tuple[dict, dict]:
    """Chance of success per cell, as in play-based exploration: P(reservoir) x P(seal) x P(charge) x P(trap) (P10.5).
    reservoir: the reservoir target; seal: P(shale >= 50 m above); charge: fill-and-spill migration along the unit top (factors.migrate),
    at maximum burial where the region was uplifted (R-UPLIFT: porosity-implied exhumation over 500 m), else present day; trap:
    1 - exp(-closure / sigma_top), at least TRAP_FLOOR. Not calibrated; tested against the hydrocarbon observations (cos_test)."""
    from se.earth.factors import at

    f = at(C); E = json.loads((EARTH / "poroperm_report.json").read_text()).get("burial", {}).get("E_median_m", 0)
    uplift = E is not None and E > 500
    pc = (f.p_charge_max if uplift else f.p_charge).to_numpy()
    pt = np.maximum(1 - np.exp(-f.closure_m.to_numpy() / np.maximum(zsd, 10.0)), TRAP_FLOOR)
    T = {"reservoir": P["reservoir"], "seal": k["p_seal"], "charge": pc, "trap": pt}
    p = np.prod([T[e] for e in ELEMENTS], axis=0)
    return {"p": p, **T, "limit": np.argmin(np.stack([T[e] for e in ELEMENTS]), axis=0)}, {
        "terms": "P(reservoir) x P(seal above >= 50 m) x P(charge by fill-and-spill migration) x P(trap from closure, at least %.1f)" % TRAP_FLOOR,
        "charge_at": "maximum burial" if uplift else "present day", "elements": list(ELEMENTS)}


def cos_test(C: pd.DataFrame, cs: dict) -> dict:
    """Held-out check of the chance of success against the hydrocarbon observations: each observation takes the value of its unit's cell
    in its column; logit(p) Platt-calibrated on the other blocks (cross-fitted); deviance gain over the base rate, beside the model's."""
    o = pd.read_parquet(OUT_T / "hydrocarbons_obs.parquet"); g = np.load(EARTH / "grid.npz")
    i = np.abs(g["x"][None] - o.x.to_numpy()[:, None]).argmin(1); j = np.abs(g["y"][None] - o.y.to_numpy()[:, None]).argmin(1)
    key = pd.Series(np.arange(len(C)), index=pd.MultiIndex.from_arrays([C.unit, C.i, C.j]))
    k = key.reindex(pd.MultiIndex.from_arrays([o.unit, i, j])).to_numpy(); ok = ~np.isnan(k)
    o, k = o[ok].reset_index(drop=True), k[ok].astype(int)
    if len(o) < 50 or o.ev.nunique() < 2:
        return {"rows": int(len(o)), "why": "too few observations on cells"}
    y, w = o.ev.to_numpy(), o.w.to_numpy(); bl = blocks(o.x.to_numpy(), o.y.to_numpy()); out = {"rows": int(len(o)), "wells": int(o.wellbore.nunique())}
    d_g = deviance(np.full(len(o), np.average(y, weights=w)), y, w)
    for name in ("p", *ELEMENTS):
        z = np.clip(cs[name][k], EPS, 1 - EPS); pc = np.zeros(len(o))
        for tr, te in GroupKFold(min(5, len(np.unique(bl)))).split(o, groups=bl):
            pc[te] = platt(z[tr], y[tr], w[tr])(z[te])
        out["gain_" + ("cos" if name == "p" else name)] = round(1 - deviance(pc, y, w) / d_g, 4)
    return out


def checks_co2(C, p, lg=None) -> dict:
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
             "pilot_median": round(float(np.median(p)), 4), "pilot_p95": round(float(np.percentile(p, 95)), 3)} | \
            ({"legacy_wells_through_units": int(lg[m].max()) if m.any() else None} if lg is not None else {})
    return out


def build(targets=("hydrocarbons", "oil", "gas", "reservoir", "overpressure", "green_clay", "calcareous_clay", "sandy_delta")) -> dict:
    """All targets, written into a staging folder that replaces <EARTH>/targets at the end (P12.4): the API never sees the cell table of one
    run beside the target arrays of another. Outputs of later steps (gamma, volumes) are carried over only if they match the new grid."""
    global OUT_T
    final = EARTH / "targets"; n_new = len(cells())
    def still_fits(p):
        if p.suffix != ".npz":
            return p.name.startswith(("gamma_ray", "co2_capacity")) and p.suffix == ".json"
        z = np.load(p); k = "p" if "p" in z else "value"
        return k in z and len(z[k]) == n_new
    with atomic.staged(final, keep=still_fits) as stage:
        OUT_T = stage
        try:
            rep = _build(targets)
        finally:
            OUT_T = final
    manifest.write(final / "cells.parquet", [EARTH / "grid.npz", EARTH / "surfaces.npz", EARTH / "fluids.parquet", EARTH / "poroperm_wells.parquet", EARTH / "pressure_obs.parquet",
                                             EARTH / "lithology_wells.parquet", OUT / "units.parquet"], {"ell_km": ELL, "k_unit": K_UNIT, "k_nb": K_NB, "n_mc": N_MC})
    return rep


def _build(targets) -> dict:
    t0 = time.time()
    C = cells(); rep, P, S = {"_conditional_on": CONDITIONAL}, {}, {}
    s = np.load(EARTH / "surfaces.npz"); names = list(s["names"])  # depth sigma per cell: its group top's sd at the column (P10.3)
    gk = C.group.map({n: k for k, n in enumerate(names)}).fillna(-1).astype(int).to_numpy()
    zsd = np.where(gk >= 0, s["sd"][np.maximum(gk, 0), C.j.to_numpy(), C.i.to_numpy()], np.nan); zsd = np.nan_to_num(zsd, nan=float(np.nanmedian(zsd)))
    for t in targets:
        o = observations(t).reset_index(drop=True)
        o.to_parquet(OUT_T / f"{t}_obs.parquet")  # the API reads these for the evidence chain (any region)
        FD = fold_designs(t, o); cols, path = select(t, o, FD)
        ev, (p_m, p_c, y, w) = evaluate(t, o, cols, FD)
        ev["features"] = cols; ev["selection"] = path
        ev["gain_selected_on_same_folds"] = ev["gain_model_vs_base"]
        ev["gain_nested"], ev["features_per_fold"] = nested_gain(t, o, FD)
        fam = {f: evaluate(t, o, cols, FD, family=f)[0]["gain_model_vs_base"] for f in FAMILIES}
        ev["time_test"] = tt = time_test(t, o, cols, FAMILIES)
        fwd = tt.get("gain_by_family", {})
        better = [f for f in FAMILIES[1:] if fam[f] >= fam["logistic"] + FAMILY_MARGIN and (not fwd or fwd.get(f, -9) >= fwd.get("logistic", 9))]
        ev["family"] = family = max(better, key=fam.get) if better else "logistic"
        ev["refit_check"] = refit_check(t, o, cols, FD, family)
        ev["families"] = {f: {"held_out": round(fam[f], 4), "forward_in_time": fwd.get(f)} for f in FAMILIES}
        if family != "logistic":
            ev, (p_m, p_c, y, w) = (lambda r: (r[0] | {k: ev[k] for k in ev if k not in r[0]}, r[1]))(evaluate(t, o, cols, FD, family=family))
        Fo = design(t, o, o, self_out=True); m = Model(cols, family).fit(Fo, o.ev.to_numpy(), o.w.to_numpy())
        cal = platt(p_m, y, w) if ev["use_platt"] else None
        FC = design(t, o, C)
        if t == "reservoir":
            C["sand"] = FC["sand"].to_numpy()  # sand share per cell: net-to-gross for the CO2 capacity (P10.4)
        # publish the simplest form that is not worse on held-out wells: model, unit prior, or the base rate (L069). The model's score is
        # the nested one (features chosen inside each training fold), discounted by what calibration adds on the same folds (P10.1)
        if family != "logistic":
            ev["gain_nested"] = nested_gain(t, o, FD, family)[0]
        g_model = ev["gain_nested"] + max(0.0, ev["gain_calibrated_vs_base"] - ev["gain_model_vs_base"])
        gains = {"model": g_model, "unit prior": ev["gain_unit_prior_vs_base"], "base rate": 0.0}
        fw = (tt.get("gain_by_family") or {}).get(family)
        if fw is not None and fw <= 0:  # no skill on later wells: the model is not published, whatever the spatial test says (P10.1)
            gains["model"] = -1.0; ev["model_rejected"] = f"forward-in-time gain {fw} <= 0"
        ev["published"] = pub = max(gains, key=gains.get)
        if pub == "model":
            _, lo0, hi0 = monte_carlo(m, FC, cal, cells=C, zsd=zsd)  # inputs only, for the record
            mean, lo, hi = monte_carlo([m] + boot_models(t, o, Fo, cols, family), FC, cal, n=max(N_MC, 2 * N_BOOT) if family == "logistic" else N_MC_NL, cells=C, zsd=zsd)
            ev["range90_median"] = {"inputs_only": round(float(np.median(hi0 - lo0)), 4), "inputs_and_coefficients": round(float(np.median(hi - lo)), 4), "bootstrap_refits": N_BOOT}
        elif pub == "unit prior":
            mean = FC.prior.to_numpy(); sdp = np.sqrt(mean * (1 - mean) / (FC.n_unit.to_numpy() + K_UNIT)); lo, hi = np.clip(mean - 1.645 * sdp, 0, 1), np.clip(mean + 1.645 * sdp, 0, 1)
        else:
            mean = np.full(len(C), ev["base_rate"]); lo = hi = mean
        sup = support(FC, gains[pub])
        P[t], S[t] = mean, sup
        ev["coefficients"] = m.coef()
        ev["cells"] = int(len(C)); ev["p_median"] = round(float(np.median(mean)), 4); ev["support_median"] = round(float(np.median(sup)), 3)
        atomic.savez(OUT_T / f"{t}.npz", i=C.i.to_numpy(np.int16), j=C.j.to_numpy(np.int16), label=C.label.to_numpy(np.int16), p=mean.astype(np.float32),
                            p05=lo.astype(np.float32), p95=hi.astype(np.float32), support=sup.astype(np.float32))
        rep[t] = ev
        print(t, {k: v for k, v in ev.items() if k not in ("reliability", "selection", "features_per_fold")}, round(time.time() - t0), "s", flush=True)
    from se.earth.factors import legacy

    lg = legacy(C)
    atomic.savez(OUT_T / "legacy_wells.npz", value=lg.astype(np.float32), sd=np.zeros(len(C), np.float32))
    K = co2_terms(C); pc, info = co2(C, P, K)
    atomic.savez(OUT_T / "co2_storage.npz", i=C.i.to_numpy(np.int16), j=C.j.to_numpy(np.int16), label=C.label.to_numpy(np.int16), p=pc.astype(np.float32),
                        p05=pc.astype(np.float32), p95=pc.astype(np.float32), support=np.minimum(S["reservoir"], S["overpressure"]).astype(np.float32))
    rep["co2_storage"] = {"composite": info, "calibrated": False, "why": "no well observes stored CO2", "checks": checks_co2(C, pc, lg), "cells": int(len(C)),
                          "p_median": round(float(np.median(pc)), 4),
                          "legacy_wells": {"what": f"wellbores within {2.0:g} km drilled through the unit (P9.3): each is a possible leak path; shown as evidence, not "
                                                    "multiplied in, because no data here gives a leak probability per well", "share_cells_with_any": round(float((lg > 0).mean()), 3)}}
    cs, cinfo = cos(C, P, K, zsd)
    atomic.savez(OUT_T / "chance_of_success.npz", i=C.i.to_numpy(np.int16), j=C.j.to_numpy(np.int16), label=C.label.to_numpy(np.int16), p=cs["p"].astype(np.float32),
                        p05=cs["p"].astype(np.float32), p95=cs["p"].astype(np.float32), support=S["hydrocarbons"].astype(np.float32),
                        **{e: cs[e].astype(np.float32) for e in ELEMENTS}, limit=cs["limit"].astype(np.int8))
    rep["chance_of_success"] = {"composite": cinfo, "calibrated": False, "why": "a product of geological elements, as explorers risk a prospect; checked against hydrocarbons",
                                "test": cos_test(C, cs), "cells": int(len(C)), "p_median": round(float(np.median(cs["p"])), 4),
                                "limiting_share": {e: round(float((cs["limit"] == k).mean()), 3) for k, e in enumerate(ELEMENTS)}}
    C["T_C"], C["seal_m"], C["w_co2"], C["zsd"] = K["T"], K["seal_m"], K["p_T"] * K["p_P"] * K["p_seal"] * (1 - P["overpressure"]), zsd
    C[["i", "j", "x", "y", "label", "unit", "group", "top", "base", "thick", "zb", "sand", "T_C", "seal_m", "w_co2", "zsd"]].to_parquet(OUT_T / "cells.parquet")
    atomic.write_json(OUT_T / "report.json", rep, indent=1, default=float)
    rep["_seconds"] = round(time.time() - t0, 1)
    return rep


if __name__ == "__main__":
    r = build()
    print(json.dumps(r.get("co2_storage"), indent=1, default=float))
