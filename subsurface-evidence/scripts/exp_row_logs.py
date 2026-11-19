"""Experiment (LOG L018): do logs see green clay at the depth of a single description row? Row-level, leave-wells-out.

Run: cd backend && uv run python ../scripts/exp_row_logs.py
Row = a rock-description row with a depth; label = it names a green mineral. Features = log medians within +-1.5 m (cuttings lag), as anomalies vs the
formation's own median (so depth and formation drop out). Baselines: formation rate only, and depth only. All scored with well-grouped folds.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from se.config import DATA, OUT
from se.ingest import logs as L
from se.ingest.units import rows_in_metres, wellbores

d = pd.read_parquet(DATA / "atlas" / "greenclay" / "descriptions.parquet")
w = wellbores()
import sys
LITH = sys.argv[1] if len(sys.argv) > 1 else "clay"
d = rows_in_metres(d[d.lith == LITH], w)  # one lithology at a time: mineral, not lithology (L019)
u = pd.read_parquet(OUT / "units.parquet")
lg = L.read()
rows = []
for wb, g in lg.groupby("wellbore"):
    r = d[d.wellbore == wb]
    if r.empty:
        continue
    z = g.DEPTH_MD.to_numpy()
    uu = u[(u.wellbore == wb) & (u.level == "FORMATION")]
    for depth, hg in zip(r.depth_from, r.has_green):
        a, b = np.searchsorted(z, [depth - 1.5, depth + 1.5])
        if b - a < 8:
            continue
        s = g.iloc[a:b]
        dphi = ((L.RHO_MATRIX - s.RHOB) / (L.RHO_MATRIX - L.RHO_FLUID)).clip(-0.2, 0.8)
        f = uu[(uu.top <= depth) & (uu.bot >= depth)]
        rows.append({"wellbore": wb, "depth": depth, "y": int(hg), "name": f.name.iloc[0] if len(f) else "?", **{c: s[c].median() for c in L.CURVES}, "DNSEP": (s.NPHI - dphi).median()})
R = pd.DataFrame(rows)
print(f"{len(R)} description rows with logs in {R.wellbore.nunique()} wells; {R.y.mean():.1%} name a green mineral; {R.y.sum()} positives")
F = list(L.CURVES) + ["DNSEP"]
R = R[R.name != "?"].copy()
# formation-relative anomalies from the whole table: a descriptive look, the CV below recomputes them per fold
def anomalies(tr, te):
    out = te[F].copy()
    for c in F:
        med = tr.groupby("name")[c].median(); mad = tr.groupby("name")[c].apply(lambda x: 1.4826 * (x - x.median()).abs().median())
        m = te.name.map(med).fillna(tr[c].median()); s = te.name.map(mad).fillna(tr[c].std()).clip(lower=1e-6)
        out[c] = ((te[c] - m) / s).clip(-5, 5)
    return out.fillna(0.0)
print("\nunivariate AUC of each anomaly (green vs not), all rows:")
A = anomalies(R, R)
uni = {}
_rng, _by = np.random.default_rng(1), {w: np.where(R.wellbore.to_numpy() == w)[0] for w in R.wellbore.unique()}
for c in F:
    a0 = roc_auc_score(R.y, A[c]); bs = []
    for _ in range(300):
        idx = np.concatenate([_by[w] for w in _rng.choice(list(_by), len(_by))])
        if R.y.iloc[idx].nunique() == 2: bs.append(roc_auc_score(R.y.iloc[idx], A[c].iloc[idx]))
    lo, hi = np.percentile(bs, [5, 95]); uni[c] = {"auc": float(a0), "p05": float(lo), "p95": float(hi)}
    print(f"  {c:6s} {a0:.3f} [{lo:.3f}, {hi:.3f}] (0.5 = nothing; >0.5 = green rows have higher {c})")
import json as _json
(OUT / f"row_logs_{LITH}.json").write_text(_json.dumps({"lithology": LITH, "rows": int(len(R)), "green_rows": int(R.y.sum()), "wells": int(R.wellbore.nunique()), "univariate_auc": uni}, indent=1))
oof = {k: np.full(len(R), np.nan) for k in ("formation", "depth", "logs_anom", "gbm_raw")}
lg_ = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
for tr_i, te_i in GroupKFold(5).split(R, groups=R.wellbore):
    tr, te = R.iloc[tr_i], R.iloc[te_i]
    rate = tr.groupby("name").y.mean(); p_f = te.name.map(rate).fillna(tr.y.mean())
    bins = np.unique(np.quantile(tr.depth, np.linspace(0, 1, 11))); rt = tr.groupby(pd.cut(tr.depth, bins, include_lowest=True), observed=True).y.mean()
    p_d = pd.cut(te.depth, bins, include_lowest=True).map(rt).astype(float).fillna(tr.y.mean())
    Atr, Ate = anomalies(tr, tr), anomalies(tr, te)
    p_l = LogisticRegression(C=0.1, max_iter=500).fit(Atr, tr.y).predict_proba(Ate)[:, 1]
    g = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05).fit(tr[F + ["depth"]], tr.y)
    for k, p in (("formation", p_f), ("depth", p_d), ("logs_anom", p_l), ("gbm_raw", g.predict_proba(te[F + ["depth"]])[:, 1])):
        oof[k][te_i] = np.asarray(p, float)
rng, by = np.random.default_rng(0), {w: np.where(R.wellbore.to_numpy() == w)[0] for w in R.wellbore.unique()}
wells = list(by)
def ci(f, n=200):
    v = []
    for _ in range(n):
        idx = np.concatenate([by[w] for w in rng.choice(wells, len(wells))])
        if R.y.iloc[idx].nunique() == 2: v.append(f(idx))
    return np.percentile(v, [5, 95])
print(f"\nleave-wells-out AUC over {len(R)} {LITH} rows ({R.y.sum()} green), 90 % CI by well resampling:")
for k in oof:
    a = roc_auc_score(R.y, oof[k]); lo, hi = ci(lambda i, k=k: roc_auc_score(R.y.iloc[i], oof[k][i]))
    print(f"  {k:10s} {a:.3f}  [{lo:.3f}, {hi:.3f}]")
d = lambda i: roc_auc_score(R.y.iloc[i], oof["logs_anom"][i]) - roc_auc_score(R.y.iloc[i], oof["formation"][i])
print(f"  logs - formation: {roc_auc_score(R.y, oof['logs_anom']) - roc_auc_score(R.y, oof['formation']):+.3f}  CI {np.round(ci(d), 3)}")
d2 = lambda i: roc_auc_score(R.y.iloc[i], oof["logs_anom"][i]) - roc_auc_score(R.y.iloc[i], oof["depth"][i])
print(f"  logs - depth:     {roc_auc_score(R.y, oof['logs_anom']) - roc_auc_score(R.y, oof['depth']):+.3f}  CI {np.round(ci(d2), 3)}")
