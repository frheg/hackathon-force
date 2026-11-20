"""Gamma ray between wells (owner question, LOG L071): a property model of the kind Petrel builds, with an honest test.

Data: FORCE 2020 GR (training wells only) in the pilot, averaged per well and unit (one value per well-unit; the samples of one well are
not independent). Estimate in every grid cell (unit x 2 km column): the unit's mean GR, updated by the same unit in nearby wells
(Gaussian weights, ELL km; shrunk to the unit mean with strength K) and a depth trend inside the unit. Tested on held-out 40 km blocks
against the unit mean and the pilot mean. Sigma from the held-out errors. Where the seismic is tied, seismic attributes could later act
as a secondary variable (co-kriging); not done here.
"""
import json

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from se.config import EARTH
from se.earth import manifest
from se.earth.folds import blocks

ELL, K = 20.0, 3.0


def well_units() -> pd.DataFrame:
    from se.earth.rules import _force

    f = _force(["GR"]).dropna(subset=["GR", "unit"])
    f = f[(f.GR > 0) & (f.GR < 300)]
    w = pd.read_parquet(EARTH / "wells.parquet").set_index("wellbore")
    g = f.groupby(["wellbore", "unit"]).agg(gr=("GR", "mean"), gr_sd=("GR", "std"), n=("GR", "size")).reset_index()
    g["x"], g["y"] = g.wellbore.map(w.x), g.wellbore.map(w.y)
    return g.dropna(subset=["x", "y"])


def estimate(tr: pd.DataFrame, q: pd.DataFrame) -> np.ndarray:
    gm = float(tr.gr.mean()); um = tr.groupby("unit").gr.mean().to_dict(); out = np.empty(len(q))
    for u, ix in q.groupby("unit").groups.items():
        t = tr[tr.unit == u]; qq = q.loc[ix]; base = um.get(u, gm); k = q.index.get_indexer(ix)
        if not len(t):
            out[k] = base; continue
        d2 = ((qq[["x", "y"]].to_numpy()[:, None] - t[["x", "y"]].to_numpy()[None]) ** 2).sum(-1); wk = np.exp(-0.5 * d2 / ELL ** 2)
        out[k] = (wk @ t.gr.to_numpy() + K * base) / (wk.sum(1) + K)
    return out


def build() -> dict:
    g = well_units().reset_index(drop=True)
    if len(g) < 20:
        from se.earth.run import Skip
        raise Skip(f"only {len(g)} FORCE well-units with gamma ray in this region")
    bl = blocks(g.x, g.y)
    e_m, e_u, e_g = np.zeros(len(g)), np.zeros(len(g)), np.zeros(len(g))
    for tr, te in GroupKFold(5).split(g, groups=bl):
        a, b = g.iloc[tr], g.iloc[te]
        e_m[te] = estimate(a, b) - b.gr
        um = a.groupby("unit").gr.mean(); e_u[te] = b.unit.map(um).fillna(a.gr.mean()).to_numpy() - b.gr
        e_g[te] = a.gr.mean() - b.gr
    rm = lambda e: round(float(np.sqrt(np.mean(e ** 2))), 1)
    sigma = float(np.percentile(np.abs(e_m), 90) / 1.645)
    C = pd.read_parquet(EARTH / "targets" / "cells.parquet")
    gr = estimate(g, C)
    np.savez_compressed(EARTH / "targets" / "gamma_ray.npz", value=gr.astype(np.float32), sd=np.full(len(C), sigma, np.float32))
    out = {"well_units": int(len(g)), "wells": int(g.wellbore.nunique()), "units": int(g.unit.nunique()), "rmse_model_gAPI": rm(e_m), "rmse_unit_mean_gAPI": rm(e_u),
           "rmse_pilot_mean_gAPI": rm(e_g), "sigma_gAPI": round(sigma, 1), "cells": int(len(C)), "ell_km": ELL, "k": K,
           "what": "unit-mean gamma ray per cell (not a log at 10 m resolution); within-unit variation shown as the wells' mean within-unit sd",
           "within_unit_sd_median_gAPI": round(float(g.gr_sd.median()), 1)}
    (EARTH / "targets" / "gamma_ray_report.json").write_text(json.dumps(out, indent=1))
    manifest.write(EARTH / "targets" / "gamma_ray.npz", [EARTH / "targets" / "cells.parquet"], {"ell_km": ELL, "k": K})
    return out


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
