"""Export the earth model in formats Petrel, RMS and simulators read (PLAN P10.7, LOG L076).

surfaces  every modelled horizon (mean and sigma) as IRAP classic ASCII grid (.irap) and ZMAP+ (.zmap)
grid      a zone-level corner-point grid (Eclipse GRDECL): one layer per group, columns of the surface lattice, with ACTNUM and, per cell,
          the thickness-weighted mean of the target probabilities of the units inside it (P_*), porosity (PORO) and sand share (NTG)
Coordinates: EPSG:3035 (ETRS89 / LAEA Europe) in metres; depth TVDSS in metres, positive down. Undefined nodes: IRAP 9999900, ZMAP 1e30.
The 10 m layers of the internal grid are not exported (a 400-layer GRDECL of a region is gigabytes); zones carry the structure.
"""
import io
import json
import zipfile

import numpy as np
import pandas as pd

from se.config import EARTH, REGION
from se.earth import manifest

UNDEF_IRAP, UNDEF_ZMAP = 9999900.0, 1e30
PROPS = {"P_HC": "hydrocarbons", "P_OIL": "oil", "P_GAS": "gas", "P_RES": "reservoir", "P_OVERP": "overpressure", "P_CO2": "co2_storage", "P_COS": "chance_of_success"}
README = """Subsurface evidence earth model, region {region}. CRS EPSG:3035 (ETRS89 / LAEA Europe), metres. Depth TVDSS, metres, positive down.
Surfaces: IRAP classic ASCII (.irap) and ZMAP+ (.zmap), mean depth and 1-sigma per horizon, on the {step} km lattice.
Grid: zones.grdecl, a corner-point grid with one layer per group (SPECGRID, COORD, ZCORN, ACTNUM) and cell properties:
  {props}
  PORO modelled porosity (fraction), NTG modelled sand share. Values are thickness-weighted means over units inside a zone cell.
  Cells with no contributing model unit are inactive (ACTNUM=0). Disregard property placeholders in inactive cells.
  P_CO2 and P_COS are screening scores, not calibrated probabilities. Other P_* values are conditional on where wells were drilled.
  This is a screening export, not a simulator-ready model.
Sources: Sodir FactPages and FactMaps (NLOD), FORCE 2020, RealPore (GeoProvider, CC BY 4.0), Smeaheia (Equinor, Gassnova), NOAA WOA23, NIST.
"""


def _lattice(root=EARTH):
    s = np.load(root / "surfaces.npz")
    return s, np.asarray(s["x"], float) * 1000, np.asarray(s["y"], float) * 1000


def irap(z, x, y) -> str:
    ny, nx = z.shape; v = np.where(np.isfinite(z), z, UNDEF_IRAP).ravel()  # rows from the south, x fastest
    head = f"-996 {ny} {x[1] - x[0]:.6f} {y[1] - y[0]:.6f}\n{x[0]:.6f} {x[-1]:.6f} {y[0]:.6f} {y[-1]:.6f}\n{nx} 0.000000 {x[0]:.6f} {y[0]:.6f}\n0 0 0 0 0 0 0\n"
    return head + "\n".join(" ".join(f"{a:.4f}" for a in v[k:k + 6]) for k in range(0, len(v), 6)) + "\n"


def zmap(z, x, y, name) -> str:
    ny, nx = z.shape; v = np.where(np.isfinite(z), z, UNDEF_ZMAP)[::-1].T.ravel()  # column by column from the west, each from the north
    head = f"! subsurface-evidence earth model, EPSG:3035 m, depth TVDSS m\n@{name[:40]} HEADER, GRID, 5\n15, {UNDEF_ZMAP:.1E}, , 4, 1\n{ny}, {nx}, {x[0]:.4f}, {x[-1]:.4f}, {y[0]:.4f}, {y[-1]:.4f}\n0.0, 0.0, 0.0\n@\n"
    return head + "\n".join("".join(f"{a:15.4f}" if a != UNDEF_ZMAP else f"{a:15.1E}" for a in v[k:k + 5]) for k in range(0, len(v), 5)) + "\n"


def _corners(a):
    """Node values (ny + 1, nx + 1) from cell-centre values (ny, nx): mean of the up to four finite neighbours."""
    p = np.pad(a, 1, mode="edge"); st = np.stack([p[:-1, :-1], p[1:, :-1], p[:-1, 1:], p[1:, 1:]])
    return np.where(np.isfinite(st).any(0), np.nanmean(np.where(np.isfinite(st), st, np.nan), 0), 0.0)


def _kw(name, v, fmt="{:.4f}"):
    v = np.asarray(v).ravel(); return f"{name}\n" + "\n".join(" ".join(fmt.format(a) for a in v[k:k + 8]) for k in range(0, len(v), 8)) + "\n/\n\n"


def grdecl(*, root=EARTH) -> tuple[str, dict]:
    g = np.load(root / "grid.npz"); zb = g["zb"].astype(np.float64); zone = g["zone"]; zones = [str(z) for z in g["zones"]]
    x, y = np.asarray(g["x"], float) * 1000, np.asarray(g["y"], float) * 1000; ny, nx = zb.shape[1:]
    used = [k for k in range(len(zones)) if (zone == k).any()]; nz = len(used)
    first = {k: int(np.argmax(zone == k)) for k in used}; last = {k: int(len(zone) - 1 - np.argmax(zone[::-1] == k)) for k in used}
    tops = np.stack([zb[first[k]] for k in used]); bots = np.stack([zb[last[k] + 1] for k in used])
    dx, dy = x[1] - x[0], y[1] - y[0]; xc = np.r_[x - dx / 2, x[-1] + dx / 2]; yc = np.r_[y - dy / 2, y[-1] + dy / 2]
    zt, zbm = float(np.nanmin(tops)), float(np.nanmax(bots))
    XX, YY = np.meshgrid(xc, yc); coord = np.stack([XX, YY, np.full(XX.shape, zt), XX, YY, np.full(XX.shape, zbm)], -1)
    zc = np.empty((nz, 2, 2 * ny, 2 * nx))  # ZCORN: per layer, top then bottom face; per face rows j (2 per cell), x fastest (2 per cell)
    for kk in range(nz):
        for f, s in enumerate((tops[kk], bots[kk])):
            c = _corners(s)
            zc[kk, f, 0::2, 0::2], zc[kk, f, 0::2, 1::2], zc[kk, f, 1::2, 0::2], zc[kk, f, 1::2, 1::2] = c[:-1, :-1], c[:-1, 1:], c[1:, :-1], c[1:, 1:]
    zc = np.maximum.accumulate(zc.reshape(nz * 2, 2 * ny, 2 * nx), axis=0)  # no crossing faces after averaging to the corners
    geometry = ((bots - tops) > 0.5) & g["inside"][None]
    C = pd.read_parquet(root / "targets" / "cells.parquet"); zidx = {zones[k]: kk for kk, k in enumerate(used)}
    zk = C.group.map(zidx).fillna(-1).astype(int).to_numpy(); ok = zk >= 0; flat = (zk * ny + C.j.to_numpy()) * nx + C.i.to_numpy()
    w = np.bincount(flat[ok], C.thick.to_numpy()[ok], minlength=nz * ny * nx)
    act = geometry & (w.reshape(geometry.shape) > 0)
    def prop(v):
        s = np.bincount(flat[ok], (v * C.thick.to_numpy())[ok], minlength=nz * ny * nx); return np.where(w > 0, s / np.maximum(w, 1e-9), 0.0)
    out = ["-- subsurface-evidence earth model, region %s: zone grid (one layer per group). EPSG:3035 m, depth TVDSS m.\n" % REGION, "-- zones: " + ", ".join(zones[k] for k in used) + "\n\n",
           f"SPECGRID\n{nx} {ny} {nz} 1 F\n/\n\n", _kw("COORD", coord, "{:.2f}"), _kw("ZCORN", zc, "{:.2f}"), _kw("ACTNUM", act.astype(int), "{:d}")]
    have = {}
    for kw, t in PROPS.items():
        p = root / "targets" / f"{t}.npz"
        if p.exists():
            out.append(_kw(kw, prop(np.load(p)["p"].astype(float)), "{:.4f}")); have[kw] = t
    if (root / "targets" / "porosity.npz").exists():
        out.append(_kw("PORO", prop(np.load(root / "targets" / "porosity.npz")["value"].astype(float) / 100), "{:.4f}")); have["PORO"] = "porosity"
    if "sand" in C:
        out.append(_kw("NTG", prop(C.sand.fillna(0).to_numpy(float)), "{:.4f}")); have["NTG"] = "sand share"
    return "".join(out), {"nx": int(nx), "ny": int(ny), "nz": nz, "zones": [zones[k] for k in used], "active_cells": int(act.sum()),
                           "geometry_cells_without_unit_rows": int((geometry & ~act).sum()), "properties": have}


def inputs(root, kind: str) -> list:
    paths = [root / "surfaces.npz", root / "grid.npz"]
    if kind in ("grid", "all"):
        d = root / "targets"
        paths += [d / "cells.parquet"]
        paths += [p for t in (*PROPS.values(), "porosity") if (p := d / f"{t}.npz").exists()]
    return paths


def build(kind: str = "all", *, root=EARTH) -> bytes:
    """A zip of the export (kind: surfaces, grid or all); also written to <EARTH>/export/."""
    if kind not in {"all", "surfaces", "grid"}:
        raise ValueError(f"unknown export kind: {kind}")
    dependencies = inputs(root, kind)
    s, x, y = _lattice(root); buf = io.BytesIO(); meta = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if kind in ("surfaces", "all"):
            with np.load(root / "grid.npz") as g:
                mask = s["inside"] & g["inside"]
            for k, n in enumerate(s["names"]):
                nm = str(n).replace(" ", "_").replace("/", "-")
                for what, a in (("depth", s["mean"][k]), ("sd", s["sd"][k])):
                    a = np.where(mask, a, np.nan)
                    z.writestr(f"surfaces/{nm}_{what}.irap", irap(a, x, y)); z.writestr(f"surfaces/{nm}_{what}.zmap", zmap(a, x, y, f"{nm}_{what}"))
            meta["surfaces"] = len(s["names"])
        if kind in ("grid", "all"):
            txt, gm = grdecl(root=root); z.writestr("grid/zones.grdecl", txt); meta["grid"] = gm
        step = (x[1] - x[0]) / 1000
        z.writestr("README.txt", README.format(region=REGION, step=f"{step:g}", props=", ".join(f"{k}: {v}" for k, v in PROPS.items())))
        z.writestr("export.json", json.dumps(meta, indent=1))
    data = buf.getvalue(); (root / "export").mkdir(exist_ok=True)
    path = root / "export" / f"{REGION}_{kind}.zip"
    path.write_bytes(data)
    manifest.write(path, dependencies, {"kind": kind}, {"output_sha256": manifest.sha256(path)})
    return data


if __name__ == "__main__":
    import sys

    d = build(sys.argv[1] if len(sys.argv) > 1 else "all"); print(len(d) // 1024, "kB")
