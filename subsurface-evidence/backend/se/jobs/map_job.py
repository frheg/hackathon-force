"""Map job: the estimated rate on a lat/lon grid for one formation, from the formation layer plus the spatial layer.

The heavy part is a (cells x training units) distance matrix. On cuda it runs in torch (chunked); on cpu in numpy. Same maths, same answer (tested).
Cells farther than 3 ell from every training unit of that formation are masked ("no data"): the layer cannot speak there, and the map says so.
"""
import time

import numpy as np

from se.config import device as default_device
from se.evidence.spatial import KM_LAT

LON_KM = 111.32


def _km(lat, lon, lat0):
    return np.c_[np.asarray(lon) * LON_KM * np.cos(np.radians(lat0)), np.asarray(lat) * KM_LAT]


def weights(P: np.ndarray, Q: np.ndarray, ng: np.ndarray, cov: np.ndarray, ell: float, dev: str, chunk: int = 4096):
    """Per cell: sum w*green, sum w*rows, neighbour count within 3 ell, nearest distance. P cells (n,2) km, Q training units (m,2) km."""
    n = len(P)
    out = np.zeros((n, 4), dtype=np.float64)
    if dev == "cuda":
        import torch

        q = torch.as_tensor(Q, dtype=torch.float32, device="cuda")
        g = torch.as_tensor(ng, dtype=torch.float32, device="cuda")
        c = torch.as_tensor(cov, dtype=torch.float32, device="cuda")
        for i in range(0, n, chunk):
            p = torch.as_tensor(P[i:i + chunk], dtype=torch.float32, device="cuda")
            d = torch.cdist(p, q, compute_mode="donot_use_mm_for_euclid_dist")  # the matrix-multiply shortcut loses precision in float32 (L025)
            w = torch.exp(-d / ell) * (d <= 3 * ell)
            out[i:i + chunk] = torch.stack([w @ g, w @ c, (d <= 3 * ell).sum(1).float(), d.min(1).values], 1).double().cpu().numpy()
        torch.cuda.synchronize()
        return out
    for i in range(0, n, chunk):
        p = P[i:i + chunk]
        d = np.sqrt(((p[:, None, :] - Q[None, :, :]) ** 2).sum(-1))
        w = np.exp(-d / ell) * (d <= 3 * ell)
        out[i:i + chunk] = np.c_[w @ ng, w @ cov, (d <= 3 * ell).sum(1), d.min(1)]
    return out


def run(strat, units, formation: str, res_deg: float = 0.1, ell: float = 20.0, k: float = 30.0, use_spatial: bool = True, dev: str | None = None, pad_deg: float = 0.5) -> dict:
    """Grid for one formation. `strat` is a fitted Strat, `units` the labelled training units. Returns cells with the raw rate logit (pre-calibration)."""
    t0 = time.time()
    dev = dev or default_device()
    tr = units[(units.name == formation) & (units.label >= 0)]
    if tr.empty:
        return {"error": f"no labelled units for {formation}"}
    lat0 = float(tr.lat.mean())
    lat = np.arange(tr.lat.min() - pad_deg, tr.lat.max() + pad_deg + 1e-9, res_deg)
    lon = np.arange(tr.lon.min() - 2 * pad_deg, tr.lon.max() + 2 * pad_deg + 1e-9, res_deg)
    LA, LO = np.meshgrid(lat, lon, indexing="ij")
    P = _km(LA.ravel(), LO.ravel(), lat0)
    Q = _km(tr.lat.to_numpy(), tr.lon.to_numpy(), lat0)
    c0 = Q.mean(0)  # centre on the units: float32 distances lose precision at 6,600 km from the equator (L025)
    P, Q = P - c0, Q - c0
    pf = strat.table[formation][0] if formation in strat.table else strat.p0
    base = np.log(strat.p0 / (1 - strat.p0))
    t = weights(P, Q, tr.n_green.to_numpy(float), tr.coverage.to_numpy(float), ell, dev) if use_spatial else np.zeros((len(P), 4))
    local = (t[:, 0] + k * pf) / (t[:, 1] + k)
    logit_f = np.log(pf / (1 - pf)) - base
    llr_sp = np.log(local / (1 - local)) - np.log(pf / (1 - pf))
    raw = base + logit_f + llr_sp
    near = t[:, 3] if use_spatial else np.full(len(P), np.nan)
    return {"formation": formation, "lat": lat.tolist(), "lon": lon.tolist(), "shape": [len(lat), len(lon)], "logit": raw.reshape(len(lat), len(lon)).tolist(),
            "neighbours": t[:, 2].reshape(len(lat), len(lon)).tolist(), "nearest_km": near.reshape(len(lat), len(lon)).tolist(), "formation_rate": float(pf), "base_rate": float(strat.p0),
            "cells": int(len(P)), "units": int(len(tr)), "device": dev, "seconds": round(time.time() - t0, 3), "res_deg": res_deg, "ell_km": ell, "reach_km": 3 * ell}
