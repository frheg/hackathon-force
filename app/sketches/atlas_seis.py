"""Seismic explorer for the Data Atlas: slices through Adele and F3 in any direction, a fault attribute (coherence),
one trace with its spectrum and header, and the QC numbers of each cube.

    uv run python -m sketches.atlas_seis [adele] [f3]

builds data/atlas/seis/: Adele as two int8 copies (inline-major and time-major, so every slice direction is one
contiguous read) and a profile JSON per cube. The SEG-Y itself is read only for the true values of one trace.
"""

import sys
import time
from functools import lru_cache

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from scipy.ndimage import uniform_filter

from common import DATA_DIR, load_json, save_json

router = APIRouter(prefix="/atlas/api/seis")
OUT = DATA_DIR / "atlas" / "seis"
ADELE = DATA_DIR / "official" / "adele" / "Adele_seismic_survey_NW australia_bind cube_fault_detection.segy"
F3 = DATA_DIR / "seismic" / "f3" / "data"
F3_SPLITS = {  # file stem, and where the block sits in the original F3 numbering (Alaudah et al. 2019)
    "train": ("train/train", (300, 700), (300, 1000)),
    "test1": ("test_once/test1", (100, 299), (300, 1000)),
    "test2": ("test_once/test2", (100, 700), (1001, 1200)),
}
FACIES = ["Upper North Sea", "Middle North Sea", "Lower North Sea", "Rijnland / Chalk", "Scruff", "Zechstein"]
NIL, NXL, NS, DT = 301, 2731, 1001, 4.0  # Adele: checked against the headers when the profile is built
T0 = 1500.0
CLIP = 2000.0  # Adele int8 copies: 127 stands for this amplitude (p99.9 is about 1,500; one spike trace goes to 350,000)
TRACE = np.dtype([("h", "V240"), ("a", ">f4", (NS,))])

# SEG-Y rev 1 header fields: (name, first byte, bytes, what it holds)
BINARY = [("Job id", 3201, 4, "job number"), ("Line number", 3205, 4, ""), ("Reel number", 3209, 4, ""),
          ("Traces per ensemble", 3213, 2, ""), ("Auxiliary traces", 3215, 2, ""),
          ("Sample interval (µs)", 3217, 2, "time between samples"), ("Samples per trace", 3221, 2, ""),
          ("Format code", 3225, 2, "1 IBM float, 5 IEEE float, 8 one-byte integer"),
          ("Ensemble fold", 3227, 2, "traces per bin"), ("Sorting code", 3229, 2, "4 = stacked, one trace per bin"),
          ("Vertical sum", 3231, 2, ""), ("Measurement system", 3255, 2, "1 metres, 2 feet"),
          ("Impulse polarity", 3257, 2, "1: a hard boundary gives a negative number (SEG rule)"),
          ("SEG-Y revision", 3501, 2, "0 = rev 0"), ("Fixed trace length", 3503, 2, ""),
          ("Extended text headers", 3505, 2, "")]
TRACEH = [("Trace in line", 1, 4, "position along this inline (1 to 2,731)"),
          ("Trace in file", 5, 4, "here a copy of the inline number"),
          ("Field record", 9, 4, "here a copy of the inline number"), ("Trace in record", 13, 4, "position along the inline"),
          ("CDP", 21, 4, "here a copy of the crossline number"), ("Trace in CDP", 25, 4, ""),
          ("Trace id", 29, 2, "1 = live seismic"), ("Data use", 35, 2, "1 = production"),
          ("Elevation scalar", 69, 2, ""), ("Coordinate scalar", 71, 2, "-100: divide coordinates by 100"),
          ("Source X", 73, 4, "a copy of the bin X"), ("Source Y", 77, 4, "a copy of the bin Y"),
          ("Coordinate units", 89, 2, "1 = length (metres)"), ("Lag time A (ms)", 105, 2, ""),
          ("Delay time (ms)", 109, 2, "time of the first sample"), ("Samples", 115, 2, ""),
          ("Sample interval (µs)", 117, 2, ""), ("CDP X", 181, 4, "bin centre X, scaled"), ("CDP Y", 185, 4, "bin centre Y, scaled"),
          ("Inline", 189, 4, "inline number"), ("Crossline", 193, 4, "crossline number")]


def _int(buf: bytes, start: int, size: int, base: int = 1) -> int:
    o = start - base
    return int.from_bytes(buf[o:o + size], "big", signed=True)


@lru_cache(1)
def _segy():
    return np.memmap(ADELE, dtype=TRACE, mode="r", offset=3600)


@lru_cache(4)
def _adele(order: str):
    p = OUT / f"adele_{order}.npy"
    if not p.exists():
        raise HTTPException(503, "not built yet: uv run python -m sketches.atlas_seis adele")
    return np.load(p, mmap_mode="r")


@lru_cache(6)
def _f3(split: str, kind: str):
    if split not in F3_SPLITS:
        raise HTTPException(404, f"split: one of {', '.join(F3_SPLITS)}")
    p = F3 / f"{F3_SPLITS[split][0]}_{kind}.npy"
    if not p.exists():
        raise HTTPException(503, "no F3 yet: uv run python fetch_data.py seismic")
    return np.load(p, mmap_mode="r")


def spectrum(a: np.ndarray, dt_s: float) -> tuple[np.ndarray, np.ndarray]:
    a = np.atleast_2d(a).astype(np.float64)
    s = np.abs(np.fft.rfft(a * np.hanning(a.shape[-1]), axis=-1)).mean(0)
    return np.fft.rfftfreq(a.shape[-1], dt_s), s


def bands(fr, sp) -> dict:
    db = 20 * np.log10(sp / sp.max() + 1e-12)
    return {"peak_hz": round(float(fr[np.argmax(sp)]), 1), "half_power_hz": [round(float(fr[db > -6].min()), 1), round(float(fr[db > -6].max()), 1)],
            "minus20_hz": [round(float(fr[db > -20].min()), 1), round(float(fr[db > -20].max()), 1)]}


def histogram(a: np.ndarray, lo: float, hi: float, bins: int = 80) -> dict:
    c, e = np.histogram(np.clip(a, lo, hi), bins=bins, range=(lo, hi))
    return {"counts": c.tolist(), "edges": np.round(e, 4).tolist(), "log": False}


# -- build --


def build_adele() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = open(ADELE, "rb").read(3600)
    text = raw[:3200].decode("cp500").replace("Ý", "[").replace("¨", "]")  # Petrel writes the brackets in another EBCDIC page
    lines = [text[i:i + 80].rstrip() for i in range(0, 3200, 80)]
    binary = [{"name": n, "byte": b, "value": _int(raw, b, s), "what": w} for n, b, s, w in BINARY]
    m = _segy()
    h0 = bytes(m["h"][0])
    assert len(m) == NIL * NXL and _int(h0, 115, 2) == NS and _int(h0, 117, 2) == DT * 1000
    ilxt = np.lib.format.open_memmap(OUT / "adele_ilxt.npy.tmp", mode="w+", dtype=np.int8, shape=(NIL, NXL, NS))
    txy = np.lib.format.open_memmap(OUT / "adele_txy.npy.tmp", mode="w+", dtype=np.int8, shape=(NS, NIL, NXL))
    rms = np.zeros((NIL, NXL), np.float32)
    peak = np.zeros((NIL, NXL), np.float32)
    rms_t = np.zeros(NS)
    sample = []
    for i in range(0, NIL, 10):
        a = np.asarray(m["a"][i * NXL:min(NIL, i + 10) * NXL], dtype=np.float32).reshape(-1, NXL, NS)
        q = np.clip(np.round(a / CLIP * 127), -127, 127).astype(np.int8)
        ilxt[i:i + len(a)] = q
        txy[:, i:i + len(a)] = q.transpose(2, 0, 1)
        rms[i:i + len(a)] = np.sqrt((a ** 2).mean(2))
        peak[i:i + len(a)] = np.abs(a).max(2)
        rms_t += (a ** 2).sum((0, 1))
        sample.append(a[:, ::25].reshape(-1, NS))
        print(f"adele: inline {i}/{NIL}", flush=True)
    ilxt.flush()
    txy.flush()
    del ilxt, txy
    for n in ("ilxt", "txy"):
        (OUT / f"adele_{n}.npy.tmp").rename(OUT / f"adele_{n}.npy")
    A = np.concatenate(sample)
    dead = peak == 0
    live = A[np.abs(A).max(1) > 0]
    fr, sp = spectrum(live, DT / 1000)
    pc = {str(p): round(float(np.percentile(live, p)), 1) for p in (0.1, 1, 5, 25, 50, 75, 95, 99, 99.9)}
    spikes = []
    thresh = 10 * pc["99.9"]
    for i, j in zip(*np.where(peak > thresh)):
        tr = np.asarray(m["a"][int(i) * NXL + int(j)])
        k = int(np.argmax(np.abs(tr)))
        spikes.append({"il": 4175 + 2 * int(i), "xl": 5670 + int(j), "t_ms": T0 + DT * k, "value": round(float(tr[k]), 1)})
    xy = lambda k: [_int(bytes(m["h"][k]), 181, 4) / 100, _int(bytes(m["h"][k]), 185, 4) / 100]
    corners = {"il4175_xl5670": xy(0), "il4175_xl8400": xy(NXL - 1), "il4775_xl5670": xy((NIL - 1) * NXL), "il4775_xl8400": xy(NIL * NXL - 1)}
    deadx = sorted({5670 + int(j) for j in np.where(dead.all(0))[0]})
    out = {
        "built": time.strftime("%Y-%m-%d %H:%M"), "file_gb": round(ADELE.stat().st_size / 1e9, 2),
        "grid": {"inlines": [4175, 4775, 2], "crosslines": [5670, 8400, 1], "n_inlines": NIL, "n_crosslines": NXL,
                 "samples": NS, "dt_ms": DT, "t0_ms": T0, "t1_ms": T0 + DT * (NS - 1), "traces": NIL * NXL,
                 "bin_m": {"along_inline": 12.5, "between_stored_inlines": 37.5}, "corners_xy": corners,
                 "crs": "GDA94 / MGA zone 51 (UTM, metres)",
                 # from the text header (degrees and minutes there): the grid is square to north, so these bound it
                 "latlon": {"south": -(13 + 46 / 60 + 31.2245 / 3600), "north": -(13 + 40 / 60 + 21.4206 / 3600),
                            "west": 123 + 21 / 60 + 41.8737 / 3600, "east": 123 + 40 / 60 + 39.3047 / 3600},
                 "orientation": "crossline numbers grow westward, inline numbers grow northward"},
        "clip": CLIP, "text_header": lines, "binary_header": binary,
        "trace_header_sample": [{"name": n, "byte": b, "value": _int(h0, b, s), "what": w} for n, b, s, w in TRACEH],
        "amplitude": {"percentiles": pc, "std": round(float(live.std()), 1), "hist": histogram(live, -2000, 2000),
                      "header_range": [-350841.13, 266021.69]},
        "rms_map": np.round(rms[:, ::6]).astype(int).tolist(), "rms_map_xl_step": 6,
        "rms_median": round(float(np.median(rms[~dead])), 1),
        "rms_time": np.round(np.sqrt(rms_t / (NIL * NXL)), 1).tolist(),
        "spectrum": {"hz": np.round(fr, 2).tolist(), "amp": np.round(sp / sp.max(), 4).tolist(), **bands(fr, sp)},
        "dead": {"traces": int(dead.sum()), "crosslines": deadx, "share": round(float(dead.mean()), 5)},
        "spikes": spikes,
    }
    save_json(OUT / "adele.json", out)
    return out


def build_f3() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "facies": FACIES, "dt_ms": 4.0, "bin_m": 25, "splits": {}}
    meta = load_json(DATA_DIR / "seismic" / "f3" / "index.json")
    if meta:
        out["lookalike"] = {"texture": meta["precision_at_k"], "learned": meta.get("learned", {}).get("precision_at_k"),
                            "chance": meta["chance"], "per_class": {k: v["precision"] for k, v in meta.get("learned", meta)["per_class"].items()}}
    for split, (_, ils, xls) in F3_SPLITS.items():
        S = np.asarray(_f3(split, "seismic"), dtype=np.float32)
        L = np.asarray(_f3(split, "labels"))
        n = L.size
        prof = np.stack([(L == k).mean((0, 1)) for k in range(6)])  # share of each class at each sample
        d = np.diff(L.astype(np.int8), axis=2)
        contacts = np.zeros((6, 6), np.int64)  # above -> below, where the unit changes going down a trace
        for a in range(6):
            sel = (L[:, :, :-1] == a) & (d != 0)
            if sel.any():
                contacts[a] += np.bincount(L[:, :, 1:][sel], minlength=6)
        amp = [{"k": FACIES[k], "rms": round(float(np.sqrt((S[L == k] ** 2).mean())), 4) if (L == k).any() else None} for k in range(6)]
        fr, sp = spectrum(S[::10, ::10].reshape(-1, S.shape[2]), 0.004)
        out["splits"][split] = {
            "shape": list(S.shape), "inlines": list(ils), "crosslines": list(xls),
            "counts": [int((L == k).sum()) for k in range(6)], "share": [round(float((L == k).sum() / n), 4) for k in range(6)],
            "depth_profile": np.round(prof, 4).tolist(), "contacts": contacts.tolist(), "upward": int((d < 0).sum()),
            "amp_by_class": amp, "percentiles": {str(p): round(float(np.percentile(S[::5], p)), 3) for p in (1, 50, 99)},
            "std": round(float(S.std()), 4), "rms_time": np.round(np.sqrt((S ** 2).mean((0, 1))), 4).tolist(),
            "spectrum": {"hz": np.round(fr, 2).tolist(), "amp": np.round(sp / sp.max(), 4).tolist(), **bands(fr, sp)},
            "amp_hist": histogram(S[::5].ravel(), -1, 1),
        }
        print(f"f3: {split}", flush=True)
    save_json(OUT / "f3.json", out)
    return out


def axis_stats(v: np.ndarray, axis: int, d: float, per_km: bool) -> dict:
    """What the data itself says about its granularity along one axis: the average power spectrum (in cycles per km,
    or Hz for time), how fast neighbouring samples stop resembling each other (autocorrelation), and how much energy
    sits near the sampling limit. d is the spacing in metres (or ms for time)."""
    v = v - v.mean(axis=axis, keepdims=True)
    shape = [1, 1, 1]
    shape[axis] = v.shape[axis]
    other = tuple(i for i in range(3) if i != axis)
    power = (np.abs(np.fft.rfft(v * np.hanning(v.shape[axis]).reshape(shape), axis=axis)) ** 2).mean(axis=other).astype(np.float64)
    k = np.fft.rfftfreq(v.shape[axis], d if per_km else d / 1000)  # cycles per metre, or Hz
    k = k * 1000 if per_km else k  # cycles per km
    nyq = float(k[-1])
    cum = np.cumsum(power[1:]) / power[1:].sum()
    r = np.fft.irfft(power)[:60]
    r = r / r[0]
    lag = np.arange(len(r)) * d

    def cross(level):  # first lag where r falls below level, by linear interpolation
        i = np.where(r < level)[0]
        if not len(i) or i[0] == 0:
            return None
        a, b = i[0] - 1, i[0]
        return float(lag[a] + (r[a] - level) / (r[a] - r[b]) * d)

    return {"d": d, "unit": "m" if per_km else "ms", "nyquist": round(nyq, 2), "k": np.round(k, 3).tolist(),
            "power": np.round(power / power.max(), 6).tolist(), "lag": np.round(lag, 2).tolist(), "r": np.round(r, 4).tolist(),
            "k95": round(float(k[1:][np.searchsorted(cum, 0.95)]), 2), "above_half_nyquist": round(float(power[k > nyq / 2].sum() / power.sum()), 5),
            "half_lag": cross(0.5), "zero_lag": cross(0.0), "peak_k": round(float(k[1:][np.argmax(power[1:])]), 2)}


def build_resolution() -> None:
    """Granularity measured on each cube: spectra and autocorrelations along the three axes of a representative
    block (Adele: 100 inlines x 800 crosslines x 600 samples from the middle; F3: the whole training block)."""
    out = {}
    a = np.asarray(_adele("ilxt")[100:200, 1000:1800, 200:800], dtype=np.float32)
    out["adele"] = {"block": list(a.shape), "block_note": "inlines 4375 to 4573, crosslines 6670 to 7469, 2,300 to 4,696 ms",
                    "crossline": axis_stats(a, 1, 12.5, True), "inline": axis_stats(a, 0, 37.5, True), "time": axis_stats(a, 2, DT, False)}
    f = np.asarray(_f3("train", "seismic"), dtype=np.float32)
    out["f3"] = {"block": list(f.shape), "block_note": "the whole training block",
                 "crossline": axis_stats(f, 1, 25.0, True), "inline": axis_stats(f, 0, 25.0, True), "time": axis_stats(f, 2, 4.0, False)}
    for c, d in out.items():
        save_json(OUT / f"resolution_{c}.json", {"built": time.strftime("%Y-%m-%d %H:%M"), **d})
        print(c, {ax: (d[ax]["half_lag"], d[ax]["zero_lag"], d[ax]["k95"], d[ax]["nyquist"], d[ax]["above_half_nyquist"]) for ax in ("crossline", "inline", "time")}, flush=True)


# -- slices --


def _section(cube: str, axis: str, i: int, split: str) -> tuple[np.ndarray, np.ndarray | None]:
    """A 2D int8 image (rows down, columns across) and, for F3, its labels. Time slices are map view:
    for Adele north up and east right."""
    if cube == "adele":
        if axis == "inline":
            return np.asarray(_adele("ilxt")[_clamp(i, NIL)]).T[:, ::-1], None  # east on the right
        if axis == "crossline":
            return np.asarray(_adele("ilxt")[:, _clamp(i, NXL)]).T, None  # south on the left
        return np.asarray(_adele("txy")[_clamp(i, NS)])[::-1, ::-1], None
    S, L = _f3(split, "seismic"), _f3(split, "labels")
    q = lambda a: np.clip(np.round(np.asarray(a, dtype=np.float32) * 127), -127, 127).astype(np.int8)
    if axis == "inline":
        k = _clamp(i, S.shape[0])
        return q(S[k]).T, np.asarray(L[k]).T
    if axis == "crossline":
        k = _clamp(i, S.shape[1])
        return q(S[:, k]).T, np.asarray(L[:, k]).T
    k = _clamp(i, S.shape[2])
    return q(S[:, :, k]), np.asarray(L[:, :, k])


def _clamp(i: int, n: int) -> int:
    if not 0 <= i < n:
        raise HTTPException(404, f"index out of range 0..{n - 1}")
    return i


def semblance(block: np.ndarray, space: tuple, along: tuple) -> np.ndarray:
    """Coherence: how alike neighbouring traces are within a short time window, 0 to 1. Faults and chaotic zones
    score low. space and along are the filter sizes per axis for the trace neighbourhood and the time window."""
    a = block.astype(np.float32)
    num = uniform_filter(uniform_filter(a, space) ** 2, along)
    den = uniform_filter(uniform_filter(a * a, space), along)
    return num / np.maximum(den, 1e-6)


def _coherence(cube: str, axis: str, i: int, split: str, w: int = 5) -> np.ndarray:
    if cube == "adele":
        if axis == "time":
            k = _clamp(i, NS)
            lo, hi = max(0, k - w), min(NS, k + w + 1)
            s = semblance(np.asarray(_adele("txy")[lo:hi]), (1, 3, 3), (hi - lo, 1, 1))[k - lo]
            return s[::-1, ::-1]
        c = _adele("ilxt")
        if axis == "inline":
            k = _clamp(i, NIL)
            lo, hi = max(0, k - 1), min(NIL, k + 2)
            return semblance(np.asarray(c[lo:hi]), (3, 3, 1), (1, 1, 2 * w + 1))[k - lo].T[:, ::-1]
        k = _clamp(i, NXL)
        lo, hi = max(0, k - 1), min(NXL, k + 2)
        return semblance(np.asarray(c[:, lo:hi]), (3, 3, 1), (1, 1, 2 * w + 1))[:, k - lo].T
    S = _f3(split, "seismic")
    if axis == "time":
        k = _clamp(i, S.shape[2])
        lo, hi = max(0, k - w), min(S.shape[2], k + w + 1)
        return semblance(np.asarray(S[:, :, lo:hi]), (3, 3, 1), (1, 1, hi - lo))[:, :, k - lo]
    if axis == "inline":
        k = _clamp(i, S.shape[0])
        lo, hi = max(0, k - 1), min(S.shape[0], k + 2)
        return semblance(np.asarray(S[lo:hi]), (3, 3, 1), (1, 1, 2 * w + 1))[k - lo].T
    k = _clamp(i, S.shape[1])
    lo, hi = max(0, k - 1), min(S.shape[1], k + 2)
    return semblance(np.asarray(S[:, lo:hi]), (3, 3, 1), (1, 1, 2 * w + 1))[:, k - lo].T


def _bin(a: np.ndarray, **extra) -> Response:
    a = np.ascontiguousarray(a)
    return Response(a.tobytes(), media_type="application/octet-stream",
                    headers={"X-Shape": f"{a.shape[0]},{a.shape[1]}", "Cache-Control": "max-age=3600",
                             **{f"X-{k}": str(v) for k, v in extra.items()}})


# -- API --


@lru_cache(8)
def _volume(cube: str, split: str):
    """A coarse copy of a cube for the 3D view, int8 on the same scale as the slices: lateral traces picked every si and sx
    (so an index i is original index i * si), time averaged over blocks of sz samples (index k is original k * sz + (sz - 1) / 2)."""
    if cube == "adele":
        si, sx, sz = 6, 40, 12
        a = np.asarray(_adele("ilxt")[::si, ::sx, :], dtype=np.float32)
        q = a
    else:
        si, sx, sz = 8, 14, 4
        a = np.asarray(_f3(split, "seismic")[::si, ::sx, :], dtype=np.float32)
        q = a * 127
    ni, nx, nt = q.shape
    n = nt // sz
    q = q[:, :, :n * sz].reshape(ni, nx, n, sz).mean(3)
    return np.clip(np.round(q), -127, 127).astype(np.int8), (si, sx, sz)


@router.get("/volume/{cube}")
def volume(cube: str, split: str = "train"):
    if cube not in ("adele", "f3"):
        raise HTTPException(404, "cube: adele or f3")
    v, steps = _volume(cube, split if cube == "f3" else "")
    return Response(np.ascontiguousarray(v).tobytes(), media_type="application/octet-stream",
                    headers={"X-Shape": ",".join(map(str, v.shape)), "X-Steps": ",".join(map(str, steps)), "Cache-Control": "max-age=3600"})


@router.get("/resolution/{cube}")
def resolution(cube: str):
    if cube not in ("adele", "f3"):
        raise HTTPException(404, "cube: adele or f3")
    d = load_json(OUT / f"resolution_{cube}.json")
    if d is None:
        raise HTTPException(404, "not measured yet: uv run python -m sketches.atlas_seis resolution")
    return d


@router.get("/profile/{cube}")
def profile(cube: str):
    if cube not in ("adele", "f3"):
        raise HTTPException(404, "cube: adele or f3")
    d = load_json(OUT / f"{cube}.json")
    if d is None:
        raise HTTPException(404, f"not profiled yet: uv run python -m sketches.atlas_seis {cube}")
    return d


Axis = Query("inline", pattern="^(inline|crossline|time)$")


@router.get("/slice/{cube}")
def slice_(cube: str, axis: str = Axis, i: int = 0, split: str = "train", step: int = Query(1, ge=1, le=8)):
    """int8 amplitudes, row by row; for F3 the uint8 labels follow in the same response. step keeps every
    step-th row and column: a light preview while a slider is dragged."""
    if cube not in ("adele", "f3"):
        raise HTTPException(404, "cube: adele or f3")
    a, lab = _section(cube, axis, i, split)
    a, lab = a[::step, ::step], (lab[::step, ::step] if lab is not None else None)
    if lab is None:
        return _bin(a)
    return _bin(np.concatenate([a.view(np.uint8), lab.astype(np.uint8)]), Labels=1)


@router.get("/coherence/{cube}")
def coherence(cube: str, axis: str = Axis, i: int = 0, split: str = "train", step: int = Query(1, ge=1, le=8)):
    """1 - coherence as uint8, stretched so the 99th percentile is white: bright lines are breaks (faults)."""
    if cube not in ("adele", "f3"):
        raise HTTPException(404, "cube: adele or f3")
    d = (1 - _coherence(cube, axis, i, split))[::step, ::step]
    top = float(np.percentile(d, 99)) or 1.0
    return _bin(np.clip(d / top * 255, 0, 255).astype(np.uint8), Top=round(top, 4))


@router.get("/trace/{cube}")
def trace(cube: str, il: int, xl: int, split: str = "train"):
    """One trace: true amplitudes, spectrum, and for Adele the trace header, for F3 the labels down the trace.
    il and xl are array indices (0-based)."""
    if cube == "adele":
        _clamp(il, NIL)
        _clamp(xl, NXL)
        rec = _segy()[il * NXL + xl]
        a = np.asarray(rec["a"], dtype=np.float64)
        h = bytes(rec["h"])
        fr, sp = spectrum(a, DT / 1000) if np.abs(a).max() > 0 else (np.zeros(1), np.zeros(1))
        return {"il": 4175 + 2 * il, "xl": 5670 + xl, "t": (T0 + DT * np.arange(NS)).tolist(), "a": np.round(a, 2).tolist(),
                "hz": np.round(fr, 2).tolist(), "spec": np.round(sp / (sp.max() or 1), 4).tolist(),
                "header": [{"name": n, "byte": b, "value": _int(h, b, s), "what": w} for n, b, s, w in TRACEH],
                "rms": round(float(np.sqrt((a ** 2).mean())), 1), "peak": round(float(np.abs(a).max()), 1)}
    S, L = _f3(split, "seismic"), _f3(split, "labels")
    _clamp(il, S.shape[0])
    _clamp(xl, S.shape[1])
    a = np.asarray(S[il, xl], dtype=np.float64)
    fr, sp = spectrum(a, 0.004)
    ils, xls = F3_SPLITS[split][1], F3_SPLITS[split][2]
    return {"il": ils[0] + il, "xl": xls[0] + xl, "t": (4.0 * np.arange(len(a))).tolist(), "a": np.round(a, 4).tolist(),
            "labels": np.asarray(L[il, xl]).tolist(), "hz": np.round(fr, 2).tolist(), "spec": np.round(sp / (sp.max() or 1), 4).tolist()}


if __name__ == "__main__":
    steps = {"adele": build_adele, "f3": build_f3, "resolution": build_resolution}
    for n in sys.argv[1:] or list(steps):
        t = time.time()
        steps[n]()
        print(f"{n}: {time.time() - t:.0f} s")
