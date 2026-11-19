"""Seismic context API: survey footprints, a curtain (vertical section) along one inline or crossline, and our wells inside each footprint.

Amplitudes come from the decimated copies built by se.seismic.index (about every 6th inline and crossline, every 8 ms). Time is two-way time (ms);
the UI converts to depth with a stated, adjustable average velocity: illustrative, not calibrated (LOG L038).
"""
import json
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pyproj import Transformer
from scipy.spatial import Delaunay

from se.api import scene
from se.config import OUT
from se.seismic.index import SEIS

router = APIRouter(prefix="/api/seismic")
CREDIT = {"smeaheia": "Smeaheia dataset: Equinor and Gassnova, co2datashare.org (DOI 10.11582/2021.00012), CC BY 4.0 based licence",
          "sleipner": "Sleipner 4D dataset: Equinor, co2datashare.org, CC BY based licence"}


def ids() -> list:
    return sorted(p.parent.name for p in SEIS.glob("*/meta.json")) if SEIS.exists() else []


@lru_cache(maxsize=32)
def meta(sid: str) -> dict:
    p = SEIS / sid / "meta.json"
    if not p.exists():
        raise HTTPException(404, "no such survey")
    return json.loads(p.read_text())


@lru_cache(maxsize=8)
def geo(sid: str):
    """Trace positions in the scene's km frame, inline/crossline per trace, amplitudes (memory-mapped)."""
    m, d = meta(sid), SEIS / sid
    xy = np.load(d / "xy.npy").astype(np.float64)
    lon, lat = Transformer.from_crs(m["epsg"], 4326, always_xy=True).transform(xy[:, 0], xy[:, 1])
    return np.c_[lat, lon], scene.xy(lat, lon), np.load(d / "ilxl.npy"), np.load(d / "traces.npy", mmap_mode="r")


@lru_cache(maxsize=1)
def wells_inside() -> dict:
    u = pd.read_parquet(OUT / "units.parquet")
    w = u.drop_duplicates("wellbore")[["wellbore", "lat", "lon"]].dropna()
    out = {}
    for sid in ids():
        fp = np.array(meta(sid)["footprint"])
        inside = w[Delaunay(np.c_[fp[:, 1], fp[:, 0]]).find_simplex(np.c_[w.lon, w.lat]) >= 0]  # the footprint is a convex hull
        out[sid] = {"wells": inside.wellbore.tolist(), "labelled_units": int(((u.wellbore.isin(inside.wellbore)) & (u.label >= 0)).sum())}
    return out


@router.get("/surveys")
def surveys():
    wi = wells_inside()
    return [{**{k: v for k, v in meta(s).items()}, "credit": CREDIT.get(meta(s)["dataset"], ""), "wells_inside": wi[s]["wells"], "labelled_units_inside": wi[s]["labelled_units"]} for s in ids()]


@router.get("/lines")
def lines(survey: str):
    _, _, ilxl, _ = geo(survey)
    return {"inline": np.unique(ilxl[:, 0]).tolist(), "crossline": np.unique(ilxl[:, 1]).tolist()}


@router.get("/curtain")
def curtain(survey: str, axis: str = "inline", index: int = 0, tstep: int = 2, baseline: str | None = None):
    """Amplitudes along one line (nearest kept inline/crossline), scaled to int8 by the survey's 99th percentile. `baseline`: another survey of the
    same geometry; the answer is then the difference (survey - baseline), for time-lapse (4D) views."""
    ll, xy, ilxl, tr = geo(survey)
    col = 0 if axis == "inline" else 1
    vals = np.unique(ilxl[:, col])
    pick = vals[np.abs(vals - index).argmin()]
    sel = np.where(ilxl[:, col] == pick)[0]
    sel = sel[np.argsort(ilxl[sel, 1 - col])]
    a = np.asarray(tr[sel][:, ::tstep], dtype=np.float32)
    m = meta(survey)
    scale = m["amp_p99"]
    if baseline:
        bl, _, bilxl, btr = geo(baseline)
        key = {(i, j): k for k, (i, j) in enumerate(map(tuple, bilxl))}
        rows = np.array([key.get(tuple(r), -1) for r in ilxl[sel]])
        ok = rows >= 0  # only where both surveys have the trace (their footprints overlap, they need not be identical)
        if not ok.any():
            raise HTTPException(400, "the two surveys share no traces on this line")
        sel, a, rows = sel[ok], a[ok], rows[ok]
        a = a - np.asarray(btr[rows][:, ::tstep], dtype=np.float32)
    q = np.clip(np.round(a / scale * 127), -127, 127).astype(np.int8)
    t = m["t0_ms"] + np.arange(0, q.shape[1]) * m["dt_ms"] * tstep
    return {"survey": survey, "axis": axis, "index": int(pick), "x": xy[sel, 0].round(2).tolist(), "y": xy[sel, 1].round(2).tolist(), "lat": ll[sel, 0].round(5).tolist(), "lon": ll[sel, 1].round(5).tolist(),
            "t_ms": t.round(1).tolist(), "amp": q.T.tolist(), "traces": int(len(sel)), "credit": CREDIT.get(m["dataset"], ""), "diff_with": baseline}
