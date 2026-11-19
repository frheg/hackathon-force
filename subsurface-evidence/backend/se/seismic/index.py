"""Index a SEG-Y survey: footprint, line geometry and a decimated amplitude copy that the app can slice in milliseconds.

Reads the SEG-Y directly with numpy (rev 1 layout: 3600 byte header, then per trace 240 bytes of header + samples). Standard header words:
inline 189, crossline 193, X 73, Y 77, coordinate scalar 71 (negative = divide). Coordinates are projected metres; `crs` is the survey's EPSG
(from its .crsmeta.xml; Smeaheia and Sleipner: ED50 / UTM 31N, EPSG:23031), converted to WGS84 for the footprint (ED50 vs WGS84 is under 150 m).
Output: OUT/seismic/<id>/{meta.json, traces.npy float16 [n, nt], xy.npy float32 [n, 2], ilxl.npy int32 [n, 2]}. LOG L038.

Run: uv run python -m se.seismic.index <file.sgy> <id> "<name>" <dataset> [epsg]
"""
import json
import sys
from pathlib import Path

import numpy as np

from se.config import OUT

SEIS = OUT / "seismic"
FORMATS = {1: ">u4", 2: ">i4", 3: ">i2", 5: ">f4", 8: ">i1"}  # 1 = IBM float (stored as raw words, decoded by ibm())


def ibm(w: np.ndarray) -> np.ndarray:
    """IBM 32-bit float (sign, 7-bit base-16 exponent excess 64, 24-bit fraction) -> float32."""
    w = w.astype(np.uint32)
    sign = np.where(w >> 31, -1.0, 1.0)
    return (sign * (w & 0xFFFFFF) * 2.0 ** -24 * 16.0 ** (((w >> 24) & 0x7F).astype(np.int32) - 64)).astype(np.float32)


def header(f) -> dict:
    with open(f, "rb") as fh:
        h = fh.read(3600)
    ns, fmt, dt = int.from_bytes(h[3220:3222], "big"), int.from_bytes(h[3224:3226], "big"), int.from_bytes(h[3216:3218], "big")
    if FORMATS.get(fmt) is None:
        raise ValueError(f"unsupported SEG-Y sample format {fmt}")
    return {"ns": ns, "fmt": fmt, "dt_ms": dt / 1000.0, "dtype": FORMATS[fmt]}


def build(f, sid: str, name: str, dataset: str, epsg: int = 23031, max_traces: int = 40000, tstep: int = 2, extra: dict | None = None) -> dict:
    from pyproj import Transformer
    from scipy.spatial import ConvexHull

    f = Path(f)
    h = header(f)
    itemsize = np.dtype(h["dtype"]).itemsize
    tsize = 240 + h["ns"] * itemsize
    n = (f.stat().st_size - 3600) // tsize
    mm = np.memmap(f, dtype=np.uint8, mode="r", offset=3600, shape=(n, tsize))
    i32 = lambda a, o: np.ascontiguousarray(mm[:, o - 1:o + 3]).view(">i4").ravel().astype(np.int64)
    il, xl, x, y = i32(mm, 189), i32(mm, 193), i32(mm, 73), i32(mm, 77)
    if not x[:: max(1, n // 50)].any():  # some surveys keep the positions in the CDP words (181, 185) and leave 73, 77 empty
        x, y = i32(mm, 181), i32(mm, 185)
    sc = int(np.ascontiguousarray(mm[:1, 70:72]).view(">i2")[0, 0])
    k = 1.0 if sc == 0 else (abs(sc) if sc > 0 else 1.0 / abs(sc))
    X, Y = x * k, y * k
    step = max(1, int(np.ceil(np.sqrt(n / max_traces))))
    keep = np.where((il % step == 0) & (xl % step == 0))[0]  # absolute line numbers: vintages of one survey keep the same traces, so they can be differenced
    # amplitudes: every tstep-th sample of the kept traces
    raw = np.ascontiguousarray(mm[keep, 240:]).view(h["dtype"])
    body = (ibm(raw) if h["fmt"] == 1 else raw.astype(np.float32))[:, ::tstep]
    amp = np.nanpercentile(np.abs(body[:: max(1, len(body) // 4000)]), 99)
    d = SEIS / sid
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / "traces.npy", body.astype(np.float16))
    np.save(d / "xy.npy", np.c_[X[keep], Y[keep]].astype(np.float32))
    np.save(d / "ilxl.npy", np.c_[il[keep], xl[keep]].astype(np.int32))
    t0 = float(np.ascontiguousarray(mm[:1, 108:110]).view(">i2")[0, 0])  # delay recording time (ms), header word 109
    tr = Transformer.from_crs(epsg, 4326, always_xy=True)
    pts = np.c_[X[keep], Y[keep]]
    try:
        hull = pts[ConvexHull(pts).vertices]
    except Exception:  # a single line of traces has no area: use its bounding box
        (x0, y0), (x1, y1) = pts.min(0), pts.max(0)
        hull = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    lon, lat = tr.transform(hull[:, 0], hull[:, 1])
    clon, clat = tr.transform(float(X.mean()), float(Y.mean()))
    meta = {"id": sid, "name": name, "dataset": dataset, "file": f.name, "epsg": epsg, "traces_total": int(n), "traces_kept": int(len(keep)), "decimation": step,
            "samples": int(body.shape[1]), "dt_ms": h["dt_ms"] * tstep, "t0_ms": t0, "t_end_ms": t0 + (body.shape[1] - 1) * h["dt_ms"] * tstep,
            "inline": [int(il.min()), int(il.max())], "crossline": [int(xl.min()), int(xl.max())], "amp_p99": float(amp),
            "footprint": [[float(a), float(b)] for a, b in zip(lat, lon)], "centre": [float(clat), float(clon)],
            **(extra or {}), "bin_m": float(np.median(np.hypot(np.diff(X[:2000]), np.diff(Y[:2000])))) if n > 2000 else None}
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    return meta


if __name__ == "__main__":
    a = sys.argv[1:]
    m = build(a[0], a[1], a[2], a[3], int(a[4]) if len(a) > 4 else 23031)
    print(json.dumps({k: v for k, v in m.items() if k != "footprint"}, indent=1))
