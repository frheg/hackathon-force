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
    d = np.r_[0.0, np.cumsum(np.hypot(np.diff(xy[sel, 0]), np.diff(xy[sel, 1])))]
    return {"survey": survey, "axis": axis, "index": int(pick), "x": xy[sel, 0].round(2).tolist(), "y": xy[sel, 1].round(2).tolist(), "lat": ll[sel, 0].round(5).tolist(), "lon": ll[sel, 1].round(5).tolist(),
            "il": ilxl[sel, 0].tolist(), "xl": ilxl[sel, 1].tolist(), "dist_km": d.round(3).tolist(), "amp_p99": float(scale),
            "t_ms": t.round(1).tolist(), "amp": q.T.tolist(), "traces": int(len(sel)), "credit": CREDIT.get(m["dataset"], ""), "diff_with": baseline}


@router.get("/slice")
def time_slice(survey: str, t_ms: float = 1000.0, baseline: str | None = None):
    """Amplitudes at one two-way time on the inline x crossline grid (missing traces are null), int8 scaled by the survey's 99th percentile.
    x, y: the cell positions in the scene's km frame, for placing the slice in 3D."""
    ll, xy, ilxl, tr = geo(survey)
    m = meta(survey)
    k = int(np.clip(round((t_ms - m["t0_ms"]) / m["dt_ms"]), 0, tr.shape[1] - 1))
    v = np.asarray(tr[:, k], dtype=np.float32)
    if baseline:
        _, _, bilxl, btr = geo(baseline)
        key = {(i, j): n for n, (i, j) in enumerate(map(tuple, bilxl))}
        rows = np.array([key.get(tuple(r), -1) for r in ilxl])
        if not (rows >= 0).any():
            raise HTTPException(400, "the two surveys share no traces")
        v = np.where(rows >= 0, v - np.asarray(btr[:, k][np.clip(rows, 0, None)], dtype=np.float32), np.nan)
    ui, uj = np.unique(ilxl[:, 0]), np.unique(ilxl[:, 1])
    ii, jj = np.searchsorted(ui, ilxl[:, 0]), np.searchsorted(uj, ilxl[:, 1])
    amp = np.full((len(ui), len(uj)), np.nan); X = amp.copy(); Y = amp.copy()
    amp[ii, jj], X[ii, jj], Y[ii, jj] = v, xy[:, 0], xy[:, 1]
    q = np.where(np.isnan(amp), np.nan, np.clip(np.round(amp / m["amp_p99"] * 127), -127, 127))
    cut = lambda a, d=0: [[None if np.isnan(x) else (int(x) if d == 0 else round(float(x), d)) for x in r] for r in a]
    return {"survey": survey, "t_ms": float(m["t0_ms"] + k * m["dt_ms"]), "il": ui.tolist(), "xl": uj.tolist(), "amp": cut(q), "x": cut(X, 2), "y": cut(Y, 2), "amp_p99": float(m["amp_p99"]), "diff_with": baseline}


@router.get("/wells")
def survey_wells(survey: str):
    """Our wells inside the survey footprint, each with its nearest trace (inline, crossline) and the distance to it."""
    from scipy.spatial import cKDTree

    _, xy, ilxl, _ = geo(survey)
    names = wells_inside().get(survey, {}).get("wells", [])
    if not names:
        return []
    u = pd.read_parquet(OUT / "units.parquet").drop_duplicates("wellbore").set_index("wellbore")
    out = []
    tree = cKDTree(xy)
    for n in names:
        la, lo = float(u.loc[n, "lat"]), float(u.loc[n, "lon"])
        p = scene.xy(la, lo)[0]
        d, i = tree.query(p)
        out.append({"name": n, "lat": la, "lon": lo, "x": float(p[0]), "y": float(p[1]), "il": int(ilxl[i, 0]), "xl": int(ilxl[i, 1]), "dist_m": round(float(d) * 1000)})
    return out


# ---- enrichment: what else we know along a section (LOG L061). Interpreted horizons are in survey time already; well logs and tops are
# in depth and are put into time with the GN1101 well-tie velocity (L058) for Smeaheia surveys, else with the UI's preview velocity.
@lru_cache(maxsize=1)
def _frame():
    from se.config import EARTH
    from se.earth.frame import Frame

    return Frame(json.loads((EARTH / "frame_calibration.json").read_text()))


@lru_cache(maxsize=1)
def _force_logs() -> dict:
    from se.earth.frame import FORCE_TRAIN
    from se.ingest.names import norm

    f = pd.read_csv(FORCE_TRAIN, sep=";", usecols=["WELL", "DEPTH_MD", "GR"])  # train only: the hidden test labels are never read
    f["wb"] = f.WELL.map(norm)
    return {wb: (g.DEPTH_MD.to_numpy(), g.GR.to_numpy()) for wb, g in f.dropna(subset=["GR"]).groupby("wb")}


@lru_cache(maxsize=4)
def _las_gr(wb: str):
    import zipfile

    from se.config import DATA
    from se.modeling.smeaheia_velocity import _las_curve

    member = {"32/4-1": "Well_Logs/data/32 4-1", "32/2-1": "Well_Logs/data/32 2-1"}.get(wb)
    if not member:
        return None
    with zipfile.ZipFile(DATA / "seismic" / "smeaheia" / "well_logs.zip") as z:
        return _las_curve(z.read(member), "GR", "gAPI")


@lru_cache(maxsize=1)
def _tops_all() -> pd.DataFrame:
    from se.earth.tops import raw_tops

    return raw_tops().dropna(subset=["top_md"])


@lru_cache(maxsize=1)
def _horizons():
    from scipy.spatial import cKDTree

    from se.earth import seismic as es

    out = {}
    for src, name in {"Seabed": "SEABED", **es.HORIZONS}.items():
        p = es.read(src); out[name] = (p, cKDTree(p[:, :2]))
    return out


def _to_time(survey: str, xy_utm, tvdss, v_kms: float):
    """TVDSS -> two-way time (ms). Smeaheia: invert the L058 tie (seabed time at the well + layer-velocity function); else 2 z / v."""
    from se.config import EARTH

    tvdss = np.asarray(tvdss, float)
    rep = EARTH / "seismic_report.json"
    if meta(survey)["dataset"] == "smeaheia" and rep.exists():
        p, kd = _horizons()["SEABED"]
        nb = kd.query_ball_point(xy_utm, 250.0) or kd.query_ball_point(xy_utm, 1500.0)  # the seabed is smooth: a wider search is safe
        if nb:
            tsb = float(np.median(p[nb, 2])); vel = json.loads(rep.read_text())["velocity"]
            t = np.linspace(tsb, 6000, 3000); dt = (t - tsb) / 2000.0
            z = vel["water_mps"] * tsb / 2000.0 + dt * (vel["a_mps"] + vel["b_mps_per_s"] * dt)
            zw = vel["water_mps"] * np.linspace(0, tsb, 200) / 2000.0
            tt = np.r_[np.linspace(0, tsb, 200), t]; zz = np.r_[zw, z]
            return np.interp(tvdss, zz, tt), f"GN1101 well-tie velocity (L058): water {vel['water_mps']:.0f} m/s, rock {vel['a_mps']:.0f} + {vel['b_mps_per_s']:.0f} x one-way time; tie residual sd {vel['tie_residual_sd_m']:.0f} m"
    return 2000.0 * tvdss / (v_kms * 1000.0), f"uncalibrated preview: constant {v_kms:.2f} km/s from sea level"


@router.get("/enrich")
def enrich(survey: str, axis: str | None = None, index: int | None = None, v: float = 2.0):
    """Wells with gamma ray and formation tops in survey time; interpreted horizons along the chosen line (Smeaheia key horizons 2010)."""
    to_utm = Transformer.from_crs(4326, 23031, always_xy=True)
    fr, logs, tops = _frame(), _force_logs(), _tops_all()
    wl, models = [], set()
    for w in survey_wells(survey):
        wb = w["name"]
        e, n = to_utm.transform(w["lon"], w["lat"])
        md, gr, src = None, None, None
        if wb in logs:
            md, gr = logs[wb]; src = "FORCE 2020 (train)"
        else:
            try:
                r = _las_gr(wb)
            except Exception:
                r = None
            if r is not None:
                md, gr = r; src = "Smeaheia LAS"
        item = {**w, "log_source": src}
        if md is not None:
            k = np.unique(np.round(md / 4.0), return_index=True)[1]  # one sample per 4 m
            md, gr = md[k], gr[k]
            z = np.asarray(fr.at(wb, md)["tvdss"], float); ok = np.isfinite(z)
            t, model = _to_time(survey, (e, n), z[ok], v); models.add(model)
            item["gr"] = {"twt": np.round(t, 1).tolist(), "v": np.round(gr[ok], 1).tolist(), "tvdss": np.round(z[ok], 1).tolist()}
        tp = tops[tops.wellbore == wb]
        if len(tp):
            z = np.asarray(fr.at(wb, tp.top_md.to_numpy())["tvdss"], float)
            t, model = _to_time(survey, (e, n), z, v); models.add(model)
            item["tops"] = [{"name": a, "level": b, "md": float(c), "tvdss": round(float(d), 1), "twt": round(float(tt), 1)} for a, b, c, d, tt in zip(tp.name, tp.level, tp.top_md, z, t) if np.isfinite(tt)]
        wl.append(item)
    hz = []
    if axis in ("inline", "crossline") and index is not None and meta(survey)["dataset"] == "smeaheia":
        ll, _, ilxl, _ = geo(survey)
        sel = ilxl[:, 0 if axis == "inline" else 1] == index
        along = ilxl[sel, 1 if axis == "inline" else 0]; o = np.argsort(along); along = along[o]
        e, n = to_utm.transform(ll[sel, 1][o], ll[sel, 0][o])
        for name, (p, kd) in _horizons().items():
            d, i = kd.query(np.c_[e, n])
            t = np.where(d < 75.0, p[i, 2], np.nan)  # an interpreted point within 75 m of the trace, else a gap
            if np.isfinite(t).sum() >= 5:
                hz.append({"name": name, "along": along.tolist(), "twt": [None if not np.isfinite(x) else round(float(x), 1) for x in t]})
    return {"survey": survey, "wells": wl, "horizons": hz, "time_model": sorted(models),
            "horizon_source": "Smeaheia Key_Horizons_2010 (Equinor, Gassnova), interpreted two-way time" if hz else None}


@router.get("/cube")
def cube(survey: str, max_points: int = 350_000, horizons: bool = True, fill: bool = True):
    """The whole decimated survey as one block on the inline x crossline x time grid, thinned further to about max_points values, int8
    (0 where no trace: shown transparent). With horizons: interpreted horizon times at the block's inline/crossline nodes (Smeaheia)."""
    ll, xy, ilxl, tr = geo(survey)
    m = meta(survey)
    ui, uj = np.unique(ilxl[:, 0]), np.unique(ilxl[:, 1]); nt = tr.shape[1]
    f = (len(ui) * len(uj) * nt / max_points) ** (1 / 3)  # the same thinning on all three axes
    si, sj, sk = max(1, int(np.ceil(f))), max(1, int(np.ceil(f))), max(1, int(np.ceil(f)))
    gi, gj = ui[::si], uj[::sj]
    keep = np.isin(ilxl[:, 0], gi) & np.isin(ilxl[:, 1], gj)
    ii, jj = np.searchsorted(gi, ilxl[keep, 0]), np.searchsorted(gj, ilxl[keep, 1])
    a = np.zeros((len(gi), len(gj), len(range(0, nt, sk))), np.int8)
    v = np.asarray(tr[np.where(keep)[0]][:, ::sk], dtype=np.float32)
    a[ii, jj] = np.clip(np.round(v / m["amp_p99"] * 127), -127, 127).astype(np.int8)
    have = np.zeros(a.shape[:2], bool); have[ii, jj] = True; filled = 0
    if fill:  # fill holes between kept traces (inside the survey) from the nearest trace within 2 nodes; outside stays empty (transparent)
        from scipy.ndimage import binary_closing, distance_transform_edt

        inside = binary_closing(have, iterations=2) | have
        d, (ni_, nj_) = distance_transform_edt(~have, return_indices=True)
        hole = inside & ~have & (d <= 2)
        a[hole] = a[ni_[hole], nj_[hole]]; filled = int(hole.sum())
    t = m["t0_ms"] + np.arange(0, nt, sk) * m["dt_ms"]

    def span(col, val):  # km from the first to the last trace of one line, for the block's true aspect
        q = np.where(ilxl[:, col] == val)[0]
        return float(np.hypot(*(xy[q].max(0) - xy[q].min(0)))) if len(q) > 1 else 1.0
    spans = {"along_crossline_axis_km": round(span(0, ui[len(ui) // 2]), 2), "along_inline_axis_km": round(span(1, uj[len(uj) // 2]), 2)}
    A = np.c_[np.ones(keep.sum()), ilxl[keep, 0], ilxl[keep, 1]]  # the survey grid is regular: x, y (scene km) are linear in inline and crossline
    cx, cy = np.linalg.lstsq(A, xy[keep, 0], rcond=None)[0], np.linalg.lstsq(A, xy[keep, 1], rcond=None)[0]
    out = {"survey": survey, **spans, "il": gi.tolist(), "xl": gj.tolist(), "t_ms": t.round(1).tolist(), "amp": a.ravel().tolist(), "order": "il, xl, t (t fastest)",
           "xy_from_il_xl": {"x": cx.round(6).tolist(), "y": cy.round(6).tolist(), "frame": "scene km (as curtain x, y): x = c0 + c1 il + c2 xl"},
           "stride": {"inline": si, "crossline": sj, "time": sk}, "filled_traces": filled, "traces_in_block": int(have.sum()), "amp_p99": float(m["amp_p99"]), "credit": CREDIT.get(m["dataset"], ""), "horizons": []}
    if horizons and m["dataset"] == "smeaheia":
        to_utm = Transformer.from_crs(4326, 23031, always_xy=True)
        e, n = to_utm.transform(ll[keep, 1], ll[keep, 0])
        for name, (p, kd) in _horizons().items():
            d, k = kd.query(np.c_[e, n])
            hz = np.full((len(gi), len(gj)), np.nan); hz[ii, jj] = np.where(d < 75.0, p[k, 2], np.nan)
            if np.isfinite(hz).sum() >= 20:
                out["horizons"].append({"name": name, "twt": [[None if not np.isfinite(x) else round(float(x), 1) for x in r] for r in hz]})
    return out
