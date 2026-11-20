"""Reproduce the 15/9-13 tie from released logs and the full-resolution 94p07 trace."""

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from zipfile import ZipFile

import duckdb
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.signal import hilbert

from se.config import DATA, OUT
from se.modeling.artifacts import sha256, write_json
from se.modeling.sleipner_transfer import ROOT, WELLS, las
from se.seismic.index import ibm

STORE = Path("velocity/well_ties")
VERSION = r"[a-f0-9]{64}"
WELL, NPDID = "15/9-13", 45
ARCHIVE = Path("seismic/sleipner/94p07.zip")
MEMBER = "2007 processing/data/94p07ful.sgy"
WINDOW = (800, 1300)  # Comparison window from Nature's Plug, not chosen on our correlations.
STEP_MS = 2
CREDIT = "Sleipner Group: CO2 DataShare 4D seismic (10.11582/2020.00005) and 2019 Benchmark Model (10.11582/2020.00004)."


def source_trace(archive: Path, xy: np.ndarray) -> dict:
    """Scan just the full-stack member once; retain the nearest live trace and verify the publisher digest."""
    digest = hashlib.sha256()
    with ZipFile(archive) as z, z.open(MEMBER) as f:
        expected = dict(line.split()[::-1] for line in z.read("2007 processing/manifest-sha256.txt").decode().splitlines())
        h = f.read(3600)
        digest.update(h)
        ns, dt, fmt, ext = (struct.unpack_from(">h", h, i)[0] for i in (3220, 3216, 3224, 3504))
        if (ns, dt, fmt, ext) != (1001, 2000, 1, 0):
            raise ValueError(f"unexpected 94p07 SEG-Y layout: {ns}, {dt}, {fmt}, {ext}")
        size = 240 + 4 * ns
        layout = np.dtype({"names": ["scale", "xy", "bin", "time", "ns", "dt", "amp"],
                           "formats": [">i2", (">i4", 2), (">i4", 2), ">i2", ">i2", ">i2", (">u4", ns)],
                           "offsets": [70, 180, 188, 108, 114, 116, 240], "itemsize": size})
        best, row = None, 0
        while raw := f.read(size * 2048):
            digest.update(raw)
            a = np.frombuffer(raw, dtype=layout)
            scale = a["scale"].astype(float)
            k = np.where(scale < 0, 1 / np.maximum(1, -scale), np.maximum(1, scale))
            coords = a["xy"] * k[:, None]
            d = np.linalg.norm(coords - xy, axis=1)
            for idx in np.argsort(d, kind="stable"):
                if best is not None and d[idx] >= best["distance_m"]:
                    break
                if not a["amp"][idx].any():
                    continue
                r = a[idx]
                if (int(r["ns"]), int(r["dt"])) != (ns, dt):
                    raise ValueError("nearest trace has inconsistent sample headers")
                amp = ibm(r["amp"])
                if not np.isfinite(amp).all() or not np.any(amp != 0):
                    raise ValueError("nearest nonempty trace has invalid amplitudes")
                best = {"distance_m": float(d[idx]), "row_zero_based": row + int(idx), "xy_m": coords[idx].tolist(),
                        "inline": int(r["bin"][0]), "crossline": int(r["bin"][1]), "t0_ms": int(r["time"]),
                        "dt_ms": dt / 1000, "amplitude": amp.tolist()}
                break
            row += len(a)
    if best is None or digest.hexdigest() != expected[MEMBER.split("/", 1)[1]]:
        raise ValueError("94p07 is empty or fails the archive's published SHA-256")
    return best | {"source_sha256": digest.hexdigest(), "traces_scanned": row}


def time_depth(tvd: np.ndarray, dt: np.ndarray) -> np.ndarray:
    """TVD below sea level (m), interval sonic (us/ft), result in ms TWT."""
    if len(tvd) < 2 or not (np.isfinite(tvd).all() and (np.diff(tvd) > 0).all() and
                            np.isfinite(dt).all() and (dt > 0).all()) or not 0 <= tvd[0] <= 0.5:
        raise ValueError("invalid or unanchored corrected sonic interval")
    slow = dt / 304800
    return 2000 * (tvd[0] * slow[0] + cumulative_trapezoid(slow, tvd, initial=0))


def _series(x: np.ndarray) -> list:
    return [round(float(v), 8) if np.isfinite(v) else None for v in x]


def build(data: Path = DATA) -> dict:
    path = data / WELLS[WELL]
    position = path.with_name("159-13_Position Log.csv")
    bag = data / ROOT.parents[1] / "manifest-sha256.txt"
    expected = dict(line.split(maxsplit=1)[::-1] for line in bag.read_text().splitlines())
    with duckdb.connect(str(data / "ncs.duckdb"), read_only=True) as db:
        rows = db.execute("""SELECT wlbNpdidWellbore, wlbGeodeticDatum, wlbUtmZone, wlbEwUtm, wlbNsUtm,
                          wlbKellyBushElevation, wlbWaterDepth FROM wellbore_exploration WHERE wlbWellboreName = ?""", [WELL]).fetchall()
    if len(rows) != 1 or rows[0][:3] != (NPDID, "ED50", 31):
        raise ValueError("expected exact NPDID and ED50 UTM 31N from FactPages")
    _, _, _, x, y, kb, water = rows[0]
    h_las, h_pos = sha256(path), sha256(position)
    for p, h in ((path, h_las), (position, h_pos)):
        if expected[p.relative_to(bag.parent).as_posix()] != h:
            raise ValueError(f"{p.name}: does not match the publisher's SHA-256")
    if "DT-CKS   .us/ft" not in path.read_text().split("~A ")[0]:
        raise ValueError("unexpected DT-CKS sample unit")
    log = las(path, WELL)
    p = pd.read_csv(position, skiprows=1)
    pos_md, px, py, z = (p[c].to_numpy() for c in ("MD (meters)", "X Absolute", "Y Absolute", "TVDSS"))
    if (not all(np.isfinite(a).all() for a in (pos_md, px, py, z)) or not (np.diff(pos_md) > 0).all() or
            np.hypot(px[0] - x, py[0] - y) > 1 or abs(z[0] - kb) > 0.1):
        raise ValueError("released trajectory does not match the registry wellhead and vertical datum")
    d = log.loc[log.DEPTH_MD.ge(kb) & log["DT-CKS"].between(40, 250)].copy()
    md, dt = d.DEPTH_MD.to_numpy(), d["DT-CKS"].to_numpy()
    if md[-1] > pos_md[-1] or np.diff(md).max() > 1:
        raise ValueError("corrected sonic contains an unsupported trajectory interval or gap")
    tvd = -np.interp(md, pos_md, z)
    twt = time_depth(tvd, dt)
    anchor_md = float(np.interp(np.mean(WINDOW), twt, md))
    anchor = np.array([np.interp(anchor_md, pos_md, c) for c in (px, py)])
    trace = source_trace(data / ARCHIVE, anchor)
    if trace["distance_m"] > 20:
        raise ValueError("no live trace within 20 m of trajectory at the fixed window midpoint")
    path_md = np.interp(WINDOW, twt, md)
    distances = np.hypot(np.interp(path_md, pos_md, px) - trace["xy_m"][0],
                         np.interp(path_md, pos_md, py) - trace["xy_m"][1])
    seabed = float(np.interp(water, tvd, twt))
    seismic_t = trace["t0_ms"] + trace["dt_ms"] * np.arange(len(trace["amplitude"]))
    candidates = np.flatnonzero(abs(seismic_t - seabed) <= 16)
    pick = candidates[np.argmax(np.abs(np.asarray(trace["amplitude"])[candidates]))]
    rho = d.RHOB.where(d.RHOB.between(1, 3.2)).to_numpy()
    tg = np.arange(trace["t0_ms"], seismic_t[-1] + STEP_MS, STEP_MS, dtype=float)
    rg = np.interp(tg, twt, rho, left=np.nan, right=np.nan)
    vp = np.where(np.isfinite(rg), 304800 / np.interp(tg, twt, dt), np.nan)
    return {
        "schema": 1, "status": "diagnostic_only", "well": WELL, "npdid": NPDID, "survey": "sleipner_94p07",
        "survey_label": "Sleipner 1994 full stack (2007 processing)", "credit": CREDIT,
        "sources": {"seismic": {"path": str(ARCHIVE), "member": MEMBER, "sha256": trace["source_sha256"]},
                    "sonic_density": {"path": str(WELLS[WELL]), "sha256": h_las, "columns": ["DEPTH", "DT-CKS", "RHOB"],
                                      "las_lines_inclusive": [int(d.las_line.min()), int(d.las_line.max())]},
                    "trajectory": {"path": position.relative_to(data).as_posix(), "sha256": h_pos},
                    "registry": {"path": "ncs.duckdb", "sha256": sha256(data / "ncs.duckdb"), "table": "wellbore_exploration", "npdid": NPDID},
                    "code_sha256": sha256(Path(__file__))},
        "registration": {"epsg": 23031, "rkb_m": kb, "water_depth_m": water, "anchor_md_m": round(anchor_md, 2),
                         "window_edge_distances_m": _series(distances), "wellhead_xy_m": [x, y],
                         "seabed_log_ms": round(seabed, 2), "seabed_trace_ms": float(seismic_t[pick]),
                         "seabed_pick": "Strongest absolute sample within 16 ms of the sonic estimate; QC, not independent validation."},
        "window_ms": list(WINDOW), "trace": trace,
        "profile": {"t_ms": _series(tg), "md_m": _series(np.interp(tg, twt, md, left=np.nan, right=np.nan)),
                    "vp_mps": _series(vp), "rhob_gcc": _series(rg)},
        "limits": ["Released checkshot-corrected sonic, not original shot stations; survey processing datum not independently established.",
                   "One nearest migrated trace, not a 3D depth transform; the well trajectory drifts within the tie window.",
                   "Only measured RHOB contributes; gaps are masked. Normal incidence, zero-offset approximation.",
                   "Window from the comparative study. Shift, phase and polarity are sensitivity controls, not validated alignment."],
    }


def synthetic(vp: np.ndarray, rho: np.ndarray, hz: float, phase: float) -> np.ndarray:
    imp = vp * rho
    rc = (imp[1:] - imp[:-1]) / (imp[1:] + imp[:-1])
    rc = np.r_[np.nan, rc]
    t = np.arange(-30, 31) * STEP_MS / 1000
    z = (np.pi * hz * t) ** 2
    w = hilbert((1 - 2 * z) * np.exp(-z))
    w = (w * np.exp(1j * np.deg2rad(phase))).real
    v = np.convolve(np.nan_to_num(rc), w, mode="full")[30:30 + len(rc)]
    n = np.convolve(np.isfinite(rc).astype(int), np.ones(len(w), dtype=int), mode="full")[30:30 + len(rc)]
    return np.where(n == len(w), v, np.nan)


def compare(receipt: dict, *, hz=25., phase=0., polarity=1, shift=0, top=None, base=None, dv=0., drho=0.) -> dict:
    p, tr = receipt["profile"], receipt["trace"]
    t, md, vp, rho = (np.asarray(p[k], dtype=float) for k in ("t_ms", "md_m", "vp_mps", "rhob_gcc"))
    ts = tr["t0_ms"] + tr["dt_ms"] * np.arange(len(tr["amplitude"]))
    obs = np.interp(t, ts, tr["amplitude"], left=np.nan, right=np.nan)
    syn = polarity * synthetic(vp, rho, hz, phase)
    lo, hi = receipt["window_ms"]
    window = (t >= lo) & (t <= hi)
    # All shift comparisons use the same logged samples, not whichever overlap scores best.
    valid = window & np.isfinite(syn) & (t - 40 >= ts[0]) & (t + 40 <= ts[-1])

    def metric(lag):
        x = syn[valid]
        if (t[valid] + lag < ts[0]).any() or (t[valid] + lag > ts[-1]).any():
            return {"r": None, "scale": None, "residual_rms": None, "offset": None}
        y = np.interp(t[valid] + lag, ts, tr["amplitude"])
        if len(x) < 30 or x.std() <= 0 or y.std() <= 0:
            return {"r": None, "scale": None, "residual_rms": None, "offset": None}
        scale = np.mean((x - x.mean()) * (y - y.mean())) / x.var()
        offset = y.mean() - scale * x.mean()
        return {"r": float(np.corrcoef(x, y)[0, 1]), "scale": float(scale), "offset": float(offset),
                "residual_rms": float(np.sqrt(np.mean((y - (scale * x + offset)) ** 2)))}

    scores = {lag: metric(lag) for lag in range(-40, 41, 2)}
    best = max((lag for lag in scores if scores[lag]["r"] is not None),
               key=lambda lag: (scores[lag]["r"], -abs(lag)), default=0)
    selected = metric(shift)
    alternatives = []
    for wrong_time in range(-2000, 2001, 150):
        if abs(wrong_time) < 200:
            continue
        tries = [metric(wrong_time + lag)["r"] for lag in (range(-40, 41, 2) if shift else (0,))]
        if all(r is not None for r in tries):
            alternatives.append(max(tries))
    exceed = sum(r >= selected["r"] for r in alternatives) if selected["r"] is not None else None
    out = {"t_ms": _series(t), "observed": _series(obs), "synthetic": _series(syn), "shift_ms": shift,
           "unshifted": scores[0], "selected": selected, "best_fit": {"shift_ms": best, **scores[best]},
           "wrong_windows": {"tested": len(alternatives), "exceeded_or_tied": exceed, "searched_shifts": bool(shift)},
           "scored_samples": int(valid.sum()), "scenario": None}
    if top is None and base is None:
        return out
    if top is None or base is None or not top < base:
        raise ValueError("provide increasing top and base in metres MD")
    inside = np.isfinite(md) & (md >= top) & (md <= base)
    indices = np.flatnonzero(inside)
    if (len(indices) < 5 or not np.isfinite(vp[inside]).all() or not (np.diff(indices) == 1).all() or
            top < np.nanmin(md) or base > np.nanmax(md)):
        raise ValueError("scenario needs at least five consecutive samples with measured density and sonic")
    # Velocity scales slowness over the interval; the changed reflectivity is resampled to the original trace grid.
    ct = t.copy()
    change = np.clip(t - t[indices[0]], 0., t[indices[-1]] - t[indices[0]]) * (1 / (1 + dv) - 1)
    ct += change
    v, r = np.where(inside, vp * (1 + dv), vp), np.where(inside, rho * (1 + drho), rho)
    s = polarity * synthetic(np.interp(t, ct, v, left=np.nan, right=np.nan),
                             np.interp(t, ct, r, left=np.nan, right=np.nan), hz, phase)
    diff = s - syn
    use = valid & np.isfinite(diff) & (t >= t[indices[0]] - 60) & (t <= t[indices[-1]] + 60)
    fit = selected["scale"]
    ratio = (float(np.sqrt(np.mean(diff[use] ** 2)) * fit / selected["residual_rms"])
             if use.sum() >= 30 and fit is not None and fit > 0 and selected["residual_rms"] > 0 else None)
    out["scenario"] = {"synthetic": _series(s), "delay_ms": float(change[-1]),
                       "local_change_over_tie_residual": ratio, "compared_samples": int(use.sum()),
                       "scope": "Window RMS ratio is descriptive, not a detection probability or mechanical test."}
    return out


def publish(receipt: dict, out: Path) -> Path:
    payload = (json.dumps(receipt, indent=2, allow_nan=False) + "\n").encode()
    path = out / STORE / f"{hashlib.sha256(payload).hexdigest()}.json"
    if not path.exists():
        write_json(path, receipt)
    if path.read_bytes() != payload:
        raise ValueError(f"{path.name}: immutable well-tie receipt differs")
    return path


def load(out: Path, version: str) -> dict:
    if not re.fullmatch(VERSION, version):
        raise ValueError("invalid well-tie version")
    payload = (out / STORE / f"{version}.json").read_bytes()
    if hashlib.sha256(payload).hexdigest() != version:
        raise ValueError("well-tie receipt failed its content hash")
    receipt = json.loads(payload)
    if receipt["schema"] != 1 or receipt["status"] != "diagnostic_only":
        raise ValueError("unsupported well-tie receipt")
    return receipt


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output", type=Path, nargs="?", help="optional scratch receipt; otherwise publish by SHA-256 without activating anything")
    arg = cli.parse_args()
    if arg.output is not None and arg.output.exists():
        cli.error("choose a new output path to preserve prior results")
    receipt = build()
    if arg.output is None:
        print(publish(receipt, OUT))
    else:
        write_json(arg.output, receipt)
