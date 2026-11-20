"""Stratigraphic grid (PLAN P2.4, LOG L059).

Columns: the 2 km surface lattice. Zones: groups, top-down, each split into a fixed number of proportional layers (about 10 m at the
thick end: nk = ceil(p90 thickness inside the pilot / 10 m)), so the grid is structured (i, j, k) and layers follow the strata.
Formations are a cell label, not zones: inside a group, a cell belongs to the formation with the deepest top above the cell centre,
among formations present in that column (presence >= 0.5); above all of them it is the group itself (undivided). This keeps
interfingering formations (Viking: Heather and Sognefjord) correct per column. The deepest group's base is its top plus the median
pilot well thickness of that group (no deeper surface is modelled).
"""
import json

import numpy as np
import pandas as pd

from se.config import EARTH
from se.earth import manifest

DZ = 10.0
NK_MAX = 400


def build() -> dict:
    s = np.load(EARTH / "surfaces.npz")
    names, level, M, inside = list(s["names"]), list(s["level"]), s["mean"].astype(np.float64), s["inside"]
    pres = s["presence"]
    col = json.loads((EARTH / "column.json").read_text())
    grp_of = {h["name"]: h.get("group") for h in col["horizons"]}
    groups = [n for n, l in zip(names, level) if l == "GROUP"]
    tops = pd.read_parquet(EARTH / "tops.parquet")
    last = groups[-1]
    th_last = float(tops[(tops.name == last) & (tops.level == "GROUP")].thick_tvd.median())
    labels = []  # label id -> (group, formation or None)
    bounds, zone_of_k, label = [], [], []
    for gi, g in enumerate(groups):
        top = M[names.index(g)]
        base = M[names.index(groups[gi + 1])] if gi + 1 < len(groups) else top + th_last
        thick = np.maximum(base - top, 0.0)
        nk = int(min(NK_MAX, max(1, np.ceil(np.percentile(thick[inside], 90) / DZ))))
        f = np.linspace(0, 1, nk + 1)[:, None, None]
        zb = top[None] + f * thick[None]
        bounds.append(zb[:-1]); zone_of_k += [gi] * nk
        zc = 0.5 * (zb[:-1] + zb[1:])
        fms = [n for n in names if grp_of.get(n) == g and level[names.index(n)] == "FORMATION"]
        gid = len(labels); labels.append((g, None))
        lab = np.full(zc.shape, gid, np.int16)
        if fms:
            ft = np.stack([np.where(pres[names.index(n)] >= 0.5, M[names.index(n)], np.nan) for n in fms])  # (nf, ny, nx)
            score = np.where(ft[:, None] <= zc[None], ft[:, None], -np.inf)
            best = np.argmax(score, axis=0); anyf = np.isfinite(score).any(axis=0)
            ids = np.array([len(labels) + i for i in range(len(fms))], np.int16)
            labels += [(g, n) for n in fms]
            lab = np.where(anyf, ids[best], gid).astype(np.int16)
        label.append(lab)
        if gi + 1 == len(groups):
            bounds.append(zb[-1:])
    zb = np.concatenate(bounds).astype(np.float32)  # (nk + 1, ny, nx) layer boundaries, TVDSS m
    lab = np.concatenate(label)
    zone = np.array(zone_of_k, np.int16)
    # checks: no gaps or overlaps (boundaries never decrease downward), round trip cell -> label -> depth interval
    dz = np.diff(zb.astype(np.float64), axis=0)
    gaps = int((dz < -1e-3)[:, inside].sum())
    cell_km2 = float((s["x"][1] - s["x"][0]) * (s["y"][1] - s["y"][0]))
    vol = {}
    for i, (g, f) in enumerate(labels):
        v = float((dz * (lab == i))[:, inside].sum() * cell_km2 / 1000.0)  # km3
        vol[f or f"{g} (undivided)"] = round(v, 1)
    rng = np.random.default_rng(0); bad = 0; tested = 0
    K, J, I = zb.shape[0] - 1, zb.shape[1], zb.shape[2]
    for _ in range(2000):  # a cell's label must be the formation whose interval holds the cell centre
        k, j, i = rng.integers(K), rng.integers(J), rng.integers(I)
        if not inside[j, i] or dz[k, j, i] <= 0:
            continue
        g, f = labels[lab[k, j, i]]; c = 0.5 * (zb[k, j, i] + zb[k + 1, j, i]); tested += 1
        if f is not None:
            t = M[names.index(f)][j, i]
            deeper = [M[names.index(n)][j, i] for n in names if grp_of.get(n) == g and n != f and pres[names.index(n)][j, i] >= 0.5 and M[names.index(n)][j, i] > t]
            nxt = min(deeper + [np.inf])
            bad += int(not (t <= c + 1e-6 and (c < nxt + 1e-6)))
        else:
            gt = M[names.index(g)][j, i]
            bad += int(c < gt - 1e-6)
    np.savez_compressed(EARTH / "grid.npz", x=s["x"], y=s["y"], inside=inside, zb=zb, zone=zone, label=lab,
                        zones=np.array(groups), labels=np.array([f"{g}|{f or ''}" for g, f in labels]))
    out = {"columns": int(J * I), "columns_inside": int(inside.sum()), "layers": int(K), "cells": int(K * J * I), "dz_target_m": DZ,
           "layers_per_zone": {g: int((zone == gi).sum()) for gi, g in enumerate(groups)}, "deepest_group_thickness_m": round(th_last, 1),
           "gaps_or_overlaps": gaps, "roundtrip_tested": tested, "roundtrip_failures": bad, "volume_km3": vol,
           "median_layer_thickness_m": round(float(np.median(dz[:, inside][dz[:, inside] > 0])), 2)}
    (EARTH / "grid_report.json").write_text(json.dumps(out, indent=1))
    manifest.write(EARTH / "grid.npz", [EARTH / "surfaces.npz", EARTH / "column.json", EARTH / "tops.parquet"], {"dz_m": DZ, "nk_max": NK_MAX})
    return out


def cell(x_km: float, y_km: float, z: float) -> dict | None:
    """(i, j, k), zone and formation of the cell holding a point (3035 km, TVDSS m); None outside the grid."""
    g = np.load(EARTH / "grid.npz")
    i = int(np.argmin(np.abs(g["x"] - x_km))); j = int(np.argmin(np.abs(g["y"] - y_km)))
    zb = g["zb"][:, j, i]
    if not (zb[0] <= z <= zb[-1]):
        return None
    k = int(min(np.searchsorted(zb, z, side="right") - 1, len(zb) - 2))
    gname, fname = str(g["labels"][g["label"][k, j, i]]).split("|")
    return {"i": i, "j": j, "k": k, "zone": str(g["zones"][g["zone"][k]]), "group": gname, "formation": fname or None}


def thickness_map(match) -> np.ndarray:
    """(ny, nx) thickness in m of the grid labels for which match("GROUP|FORMATION") is true (0 where absent)."""
    g = np.load(EARTH / "grid.npz"); dz = np.diff(g["zb"].astype(np.float64), axis=0)
    ls = [li for li, s in enumerate(g["labels"]) if match(str(s))]
    return (dz * np.isin(g["label"], ls)).sum(0) if ls else np.zeros(g["zb"].shape[1:])


def at_columns(field: np.ndarray, x_km, y_km) -> np.ndarray:
    """A (ny, nx) column field at points (3035 km), nearest column."""
    g = np.load(EARTH / "grid.npz")
    i = np.abs(g["x"][None] - np.ravel(x_km)[:, None]).argmin(1); j = np.abs(g["y"][None] - np.ravel(y_km)[:, None]).argmin(1)
    return field[j, i].reshape(np.shape(x_km))


if __name__ == "__main__":
    o = build()
    print({k: v for k, v in o.items() if k != "volume_km3"})
    print("volumes km3:", dict(sorted(o["volume_km3"].items(), key=lambda kv: -kv[1])[:20]))
