"""One fixed depth experiment. No regional surfaces, fitted shifts or amplitude features."""
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

from se.earth.folds import blocks


def bracket(path: pd.DataFrame, md: float):
    """Interpolate only between adjacent sampled positions, never across a log gap or beyond TD."""
    m = path.md.to_numpy()
    i = int(np.searchsorted(m, md))
    if i < len(m) and m[i] == md:
        j = i
    elif 0 < i < len(m) and 0 < m[i] - m[i - 1] <= 2:
        j = i - 1
    else:
        return None
    a = path.iloc[j:i + 1]
    return {col: float(np.interp(md, a.md, a[col])) for col in ("x", "y", "tvdss")} | {
        "bracket_md_m": [float(m[j]), float(m[i])]}


def evaluate(rows: list[dict]) -> dict:
    """Leave a 40 km wellhead block out; purge the test families and a 10 km border."""
    d = pd.DataFrame(rows).sort_values("npdid").reset_index(drop=True)
    if d.npdid.duplicated().any() or d.family.isna().any():
        raise ValueError("depth evaluation requires one identified top per borehole and known well family")
    xy = d[["head_x", "head_y"]].to_numpy()
    z = d.tvdss.to_numpy()
    bl = blocks(*xy.T)
    rows_out, folds = [], []
    for b in np.unique(bl):
        test = np.flatnonzero(bl == b)
        tr = np.flatnonzero((bl != b) & ~d.family.isin(d.family.iloc[test]))
        if len(tr):
            tr = tr[cdist(xy[tr], xy[test]).min(axis=1) >= 10]
        folds.append({"block": int(b), "test_ids": d.npdid.iloc[test].tolist(), "train_ids": d.npdid.iloc[tr].tolist()})
        if not len(tr):
            continue
        distances = cdist(xy[test], xy[tr])
        med = float(np.median(z[tr]))
        for i, ds in zip(test, distances, strict=True):
            n = tr[ds.argmin()]
            rows_out.append({**d.iloc[i].to_dict(), "block": int(b), "median_m": med, "nearest_m": float(z[n]),
                             "nearest_id": int(d.npdid.iloc[n]), "distance_km": float(ds.min())})
    result = {"target": "Top SOGNEFJORD FM, m TVDSS (+ down), conditional on a reported formation top.",
              "design": "Retrospective Horda wells. Fixed train median vs nearest training wellhead, same folds. "
                        "Leave a 40 km EPSG:3035 block out; remove shared registry well families and heads within 10 km.",
              "folds": folds, "rows": rows_out, "eligible": len(d), "scored": len(rows_out),
              "blocks": len(np.unique(bl)), "published": False,
              "limit": "Selected logged wells, not blind site validation. Error resampling intervals are not depth prediction intervals. "
                       "No independent Smeaheia seismic tie or site-wide depth prediction."}
    if not rows_out:
        return result
    out = pd.DataFrame(rows_out)
    base, near = (np.abs(out[col] - out.tvdss).to_numpy() for col in ("median_m", "nearest_m"))
    gain = base - near
    rng = np.random.default_rng(42)
    well_ci = np.quantile(rng.choice(gain, (2000, len(gain)), replace=True).mean(axis=1), [.05, .95])
    groups = [gain[out.block.eq(b)] for b in sorted(out.block.unique())]
    draw = rng.integers(len(groups), size=(2000, len(groups)))
    block_ci = np.quantile(np.array([g.sum() for g in groups])[draw].sum(axis=1) /
                           np.array([len(g) for g in groups])[draw].sum(axis=1), [.05, .95])
    result.update(median_mae_m=float(base.mean()), nearest_mae_m=float(near.mean()), gain_m=float(gain.mean()),
                  well_gain90_m=well_ci.tolist(), block_gain90_m=block_ci.tolist())
    return result
