"""Validation harness for the RATE target (LOG L015). Blocked folds (BLOCK_KM), out-of-fold predictions per ablation, effort-aware metrics.

Metrics: deviance gain = 1 - D(model)/D(constant rate), D = binomial deviance on held-out units (a proper score that counts effort as trials);
AUC of "any green row" *inside* coverage bins, size-weighted (pooled AUC would reward predicting effort). Bootstrap resamples whole wellbores.

Run: uv run python -m se.validate.cv   -> OUT/results.json, OUT/oof.parquet (read by the API and the UI)
"""
import json
import time

import numpy as np
import pandas as pd
from scipy.stats import binom
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from se.config import BLOCK_KM, OUT, device
from se.evidence.spatial import xy
from se.infer.combine import Platt, contributions, fit_layers

K = 5
VARIANTS = {"strat": ("strat",), "strat+spatial": ("strat", "spatial"), "strat+logs": ("strat", "logs"), "full": ("strat", "spatial", "logs")}
COV_BINS = [3, 5, 8, 13, 26, 61, 10**9]


def load() -> pd.DataFrame:
    return pd.read_parquet(OUT / "units.parquet").join(pd.read_parquet(OUT / "log_features.parquet"), how="left")


def blocks(df: pd.DataFrame) -> np.ndarray:
    p = xy(df)
    return np.floor(p[:, 0] / BLOCK_KM).astype(int) * 100003 + np.floor(p[:, 1] / BLOCK_KM).astype(int)


def distance_to_train(tr: pd.DataFrame, te: pd.DataFrame) -> np.ndarray:
    from scipy.spatial import cKDTree

    d = np.full(len(te), np.nan)
    for f, idx in te.reset_index(drop=True).groupby("name").indices.items():
        g = tr[(tr.name == f) & (tr.label >= 0)]
        if len(g):
            d[idx] = cKDTree(xy(g)).query(xy(te.iloc[idx]))[0]
    return d


def oof(units: pd.DataFrame, n_folds: int = K, **kw) -> pd.DataFrame:
    """Out-of-fold layer contributions and variant rates for every labelled unit. Folds are whole 40 km blocks."""
    lab = units[units.label >= 0]
    rows = []
    for i, (tr_i, te_i) in enumerate(GroupKFold(n_folds).split(lab, groups=blocks(lab))):
        tr, te = lab.iloc[tr_i], lab.iloc[te_i]
        layers = fit_layers(tr, **kw)
        c = contributions(layers, te)
        c["p_base"] = 1 / (1 + np.exp(-c["base"]))
        for name, use in VARIANTS.items():
            c["l_" + name] = contributions(layers, te, use)["logit"]
        c["dist_km"], c["fold"] = distance_to_train(tr, te), i
        rows.append(c)
    return lab.join(pd.concat(rows))


def calibrate(r: pd.DataFrame) -> dict:
    """Each variant's raw logit -> calibrated rate (2 parameters, fitted on all out-of-fold units). Fair comparison: a model is not punished for overconfidence."""
    cal = {}
    for n in VARIANTS:
        p = Platt().fit(r["l_" + n], r.n_green, r.coverage)
        r["p_" + n] = p(r["l_" + n])
        r["pr_" + n] = 1 / (1 + np.exp(-r["l_" + n]))  # the raw rate, kept to show the overconfidence
        cal[n] = p.params()
    return cal


def dev(ng, cov, p) -> float:
    p = np.clip(np.asarray(p, float), 1e-5, 1 - 1e-5)
    return float(-2 * np.sum(np.asarray(ng, float) * np.log(p) + (np.asarray(cov, float) - np.asarray(ng, float)) * np.log(1 - p)))


def strat_auc(df: pd.DataFrame, p) -> tuple:
    """AUC of 'has a green row' within each coverage bin, weighted by bin size. Returns (mean, per-bin list)."""
    out, w = [], []
    cb = pd.cut(df.coverage, COV_BINS, right=False)
    for b, g in df.assign(p=np.asarray(p)).groupby(cb, observed=True):
        y = (g.n_green > 0).astype(int)
        if y.nunique() == 2 and len(g) >= 30:
            out.append({"coverage": str(b), "n": int(len(g)), "auc": float(roc_auc_score(y, g.p))})
            w.append(len(g))
    return (float(np.average([o["auc"] for o in out], weights=w)) if out else float("nan")), out


def metrics(df: pd.DataFrame, p, p_base) -> dict:
    ng, cov = df.n_green.to_numpy(float), df.coverage.to_numpy(float)
    d1, d0 = dev(ng, cov, p), dev(ng, cov, p_base)
    return {"units": int(len(df)), "rows": int(cov.sum()), "deviance_gain": 1 - d1 / d0, "auc_in_coverage_bins": strat_auc(df, p)[0], "observed_rate": float(ng.sum() / cov.sum()),
            "predicted_rate": float(np.average(np.asarray(p), weights=cov))}


def reliability(df: pd.DataFrame, p, bins: int = 10) -> list:
    """Bins of predicted rate: observed share of green rows. A calibrated model lies on the diagonal."""
    d = df.assign(p=np.asarray(p))
    q = np.unique(np.quantile(d.p, np.linspace(0, 1, bins + 1)))
    d["b"] = pd.cut(d.p, q, include_lowest=True)
    return [{"predicted": float(np.average(g.p, weights=g.coverage)), "observed": float(g.n_green.sum() / g.coverage.sum()), "rows": int(g.coverage.sum()), "units": int(len(g))}
            for _, g in d.groupby("b", observed=True) if g.coverage.sum() >= 100]


def gain(df: pd.DataFrame, col: str) -> float:
    return 1 - dev(df.n_green, df.coverage, df[col]) / dev(df.n_green, df.coverage, df.p_base)


def boot(r: pd.DataFrame, a: str, b: str | None, n: int = 200, seed: int = 0) -> dict:
    """Gain(a) - gain(b) (b=None: against the constant rate), 90 % interval, resampling whole wellbores (a well's units are not independent)."""
    rng, by = np.random.default_rng(seed), {w: g for w, g in r.groupby("wellbore")}
    wells = np.array(list(by))
    d = []
    for _ in range(n):
        s = pd.concat([by[w] for w in rng.choice(wells, len(wells))])
        d.append(gain(s, "p_" + a) - (gain(s, "p_" + b) if b else 0.0))
    lo, hi = np.percentile(d, [5, 95])
    return {"delta_gain": float(gain(r, "p_" + a) - (gain(r, "p_" + b) if b else 0.0)), "p05": float(lo), "p95": float(hi), "significant": bool(lo > 0 or hi < 0)}


def run() -> dict:
    t0 = time.time()
    u = load()
    lab = u[u.label >= 0]
    res = {"built": time.strftime("%Y-%m-%d %H:%M"), "device": device(), "target": "share of described rows naming a green mineral", "block_km": BLOCK_KM, "folds": K,
           "data": {"units": int(len(u)), "labelled": int(len(lab)), "wellbores_labelled": int(lab.wellbore.nunique()), "rows": int(lab.coverage.sum()), "green_rows": int(lab.n_green.sum()),
                    "base_rate": float(lab.n_green.sum() / lab.coverage.sum()), "with_logs": int(lab.GR.notna().sum()), "wellbores_with_logs": int(lab[lab.GR.notna()].wellbore.nunique())}}
    res["sweep_ell"], res["sweep_a"] = [], []
    for ell in (5, 10, 20, 40, 80, 160, 320):
        r = oof(u, ell=ell)
        calibrate(r)
        res["sweep_ell"].append({"ell_km": ell, **metrics(r, r["p_strat+spatial"], r.p_base)})
    for a in (3, 10, 30, 100, 300):
        r = oof(u, a=a)
        calibrate(r)
        res["sweep_a"].append({"a_rows": a, **metrics(r, r["p_strat"], r.p_base)})
    res["sweep_k"] = []
    for k in (3, 10, 30, 100):
        r = oof(u, k=k)
        calibrate(r)
        res["sweep_k"].append({"k_rows": k, **metrics(r, r["p_strat+spatial"], r.p_base)})
    res["sweep_C"] = []  # the log layer gets a fair try: stronger and weaker regularisation, judged on the units that have logs
    for C in (0.01, 0.03, 0.1, 0.3, 1.0):
        r = oof(u, C=C)
        calibrate(r)
        sub = r[r.GR.notna()]
        res["sweep_C"].append({"C": C, **metrics(sub, sub["p_strat+logs"], sub.p_base), "delta_vs_strat": boot(sub, "strat+logs", "strat", n=100)})
    r = oof(u)
    res["platt"] = calibrate(r)
    res["ablation"] = {n: metrics(r, r["p_" + n], r.p_base) for n in VARIANTS}
    sub = r[r.GR.notna()]
    res["ablation_logs_subset"] = {n: metrics(sub, sub["p_" + n], sub.p_base) for n in VARIANTS}
    res["delta"] = {"strat_over_constant": boot(r, "strat", None), "spatial_over_strat": boot(r, "strat+spatial", "strat"), "logs_over_strat_on_logs_subset": boot(sub, "strat+logs", "strat"),
                    "full_over_strat+spatial_on_logs_subset": boot(sub, "full", "strat+spatial")}
    res["by_coverage"] = strat_auc(r, r["p_full"])[1]
    res["reliability_raw"], res["reliability_calibrated"] = reliability(r, r["pr_full"]), reliability(r, r["p_full"])
    bins = [(0, 5), (5, 15), (15, 40), (40, 100), (100, 1e9)]
    res["by_distance"] = [{"from_km": lo, "to_km": min(hi, 999), **metrics(g, g["p_strat+spatial"], g.p_base), "gain_strat_only": gain(g, "p_strat")}
                          for lo, hi in bins for g in [r[(r.dist_km >= lo) & (r.dist_km < hi)]] if len(g) >= 150]
    res["by_formation"] = [{"formation": f, **metrics(g, g["p_strat+spatial"], g.p_base)} for f, g in r.groupby("name") if len(g) >= 200]
    # contradictions: how surprising is the report under the model? binomial tail, not a threshold on a score. Either side can be wrong.
    th, c = r.p_full.clip(1e-5, 1 - 1e-5), r.coverage
    r["tail_many"] = binom.sf(r.n_green - 1, c, th)  # P(at least this many green rows)
    r["tail_none"] = np.where(r.n_green == 0, (1 - th) ** c, 1.0)  # P(no green row at all)
    cols = ["unit", "name", "lat", "lon", "top", "bot", "coverage", "n_green", "p_full", "strat", "spatial", "logs"]
    res["contradictions"] = {"reported_but_unexpected": r[r.n_green >= 2].nsmallest(25, "tail_many")[cols + ["tail_many"]].round(5).to_dict("records"),
                             "expected_but_not_reported": r[(r.n_green == 0) & (r.coverage >= 8)].nsmallest(25, "tail_none")[cols + ["tail_none"]].round(5).to_dict("records")}
    res["seconds"] = round(time.time() - t0)
    (OUT / "results.json").write_text(json.dumps(res, indent=1, default=float))
    r.to_parquet(OUT / "oof.parquet")
    return res


if __name__ == "__main__":
    s = run()
    g = lambda d: {k: round(v, 3) if isinstance(v, float) else v for k, v in d.items() if k in ("deviance_gain", "auc_in_coverage_bins", "units")}
    print("data", s["data"]); print("ablation", {k: g(v) for k, v in s["ablation"].items()}); print("logs subset", {k: g(v) for k, v in s["ablation_logs_subset"].items()})
    print("delta", {k: {a: round(b, 4) if isinstance(b, float) else b for a, b in v.items()} for k, v in s["delta"].items()})
    print("ell", [(d["ell_km"], round(d["deviance_gain"], 4), round(d["auc_in_coverage_bins"], 3)) for d in s["sweep_ell"]])
    print("a", [(d["a_rows"], round(d["deviance_gain"], 4), round(d["auc_in_coverage_bins"], 3)) for d in s["sweep_a"]])
    print("k", [(d["k_rows"], round(d["deviance_gain"], 4), round(d["auc_in_coverage_bins"], 3)) for d in s["sweep_k"]])
    print("C (logs subset)", [(d["C"], round(d["deviance_gain"], 4), round(d["delta_vs_strat"]["delta_gain"], 4), [round(d["delta_vs_strat"]["p05"], 3), round(d["delta_vs_strat"]["p95"], 3)]) for d in s["sweep_C"]])
    print("by cov", [(d["coverage"], d["n"], round(d["auc"], 3)) for d in s["by_coverage"]])
    print("by dist", [(d["from_km"], d["to_km"], d["units"], round(d["deviance_gain"], 4), round(d["gain_strat_only"], 4), round(d["auc_in_coverage_bins"], 3)) for d in s["by_distance"]])
    print("platt", {k: {a: round(b, 3) for a, b in v.items()} for k, v in s["platt"].items()}, "seconds", s["seconds"])
