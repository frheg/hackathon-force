"""Seabed temperature from the ocean, not a constant (PLAN P9.4, LOG L075).

Source: NOAA World Ocean Atlas 2023, annual mean temperature on a 1 degree grid at standard depths (data/woa23, SOURCE.md). The bottom
temperature at a point is the WOA value at the deepest standard level not below the water depth, in the nearest WOA cell that has ocean
at that level. It replaces the fixed 7 C that temperature.predict used above the DST depth range: North Sea bottom water is about 6-8 C,
but the deep Norwegian Sea is below 0 C.
"""
from functools import lru_cache

import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

from se.config import DATA

WOA = DATA / "woa23" / "t00an01.csv.gz"
TO_LL = Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)


@lru_cache(1)
def _table():
    rows = []  # one row per WOA cell; rows end at the deepest level with ocean, so their length varies
    with __import__("gzip").open(WOA, "rt") as f:
        f.readline(); depths = np.array([float(v) for v in f.readline().split(":")[1].split(",") if v.strip()])
        for line in f:
            v = line.rstrip(",\n").split(",")
            la, lo = float(v[0]), float(v[1])
            if 50 < la < 82 and -15 < lo < 50:  # the NCS and around it
                r = np.full(len(depths) + 2, np.nan); r[:len(v)] = [float(s) if s else np.nan for s in v]; rows.append(r)
    t = np.array(rows)
    return t[:, 0], t[:, 1], t[:, 2:], depths


def lonlat(x, y):
    lo, la = TO_LL.transform(np.asarray(x, float) * 1000, np.asarray(y, float) * 1000)
    return np.asarray(lo), np.asarray(la)


def bottom_temperature(x, y, wd) -> np.ndarray:
    """Bottom-water temperature (C) at EPSG:3035 km points with water depth wd (m)."""
    lat, lon, T, depths = _table()
    lo, la = lonlat(np.ravel(x), np.ravel(y)); wd = np.ravel(np.asarray(wd, float))
    k = np.clip(np.searchsorted(depths, np.nan_to_num(wd, nan=100.0), side="right") - 1, 0, len(depths) - 1)
    out = np.full(len(wd), np.nan)
    for lev in np.unique(k):  # nearest WOA cell with a value at this level (cos-lat scaled degrees)
        for kk in range(lev, -1, -1):
            ok = np.isfinite(T[:, kk])
            if ok.any():
                break
        tree = cKDTree(np.c_[lat[ok], lon[ok] * np.cos(np.radians(66))])
        sel = k == lev; _, j = tree.query(np.c_[la[sel], lo[sel] * np.cos(np.radians(66))])
        out[sel] = T[ok, kk][j]
    return out.reshape(np.shape(x))
