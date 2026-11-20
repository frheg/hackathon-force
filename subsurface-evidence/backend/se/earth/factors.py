"""Petroleum-system factors per grid column and unit (PLAN P9, LOG L075). Inputs are geology and physics only, never well outcomes,
so no label of a held-out well can leak through them.

  maturity  each source rock in the column (Draupne, Mandal, Farsund, Tau, Spekk, Hekkingen, Are coal, Kobbe): temperature at its mid
            depth (P3.4 model, seabed from WOA) -> P(oil window, T >= 100 C) and P(gas window, T >= 150 C) (rule R-MATURE).
            kit_oil / kit_gas: distance (km) to the nearest column where any source is in the window with P >= 0.5 (0 above a kitchen).
            kit_max: the same with the temperature at maximum burial, T + g E, E the net exhumation map of P9.2 (rule R-UPLIFT).
  fault_km  distance to the nearest mapped fault (Sodir FactMaps, regional scale)
  on_high   the column lies on a mapped structural high or intra-basinal elevation (Sodir structural elements)
  closure_m per unit: height of structural closure on the unit's top surface (spill analysis: the depth to which the top must be
            filled before oil could spill to the edge; smoothed kriged surfaces see only large closures)
  salt_km   Zechstein thickness in the column
  charge    per unit (P10.2, fill and spill as in Trinity / PetroMod flowpath models): oil enters the unit's top surface at kitchen columns,
            moves up-dip along the drainage tree of the priority flood, fills each closure to its spill point and spills on. charge_km2
            is the mature kitchen area (p-weighted) whose oil passes a column; every column of a closure gets the charge of the closure.
            p_charge = 1 - prod(1 - p) over the kitchen columns upstream (at least one mature column drains here; treats them as
            independent, so it saturates). Both at present and at maximum burial (_max). Simplifications: oil enters the unit wherever a
            kitchen lies anywhere in the column (no expulsion direction, no carrier-bed choice, no fault seal), the unit's edges and
            pinch-outs are exits (stratigraphic traps are not seen), and charge volumes are areas, not expelled masses.
Legacy wells (P9.3) are per cell and computed with the cells: legacy(C).
"""
import json

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import norm as N

from se.config import DATA, EARTH
from se.earth import manifest

SOURCES = {"DRAUPNE FM", "MANDAL FM", "FARSUND FM", "TAU FM", "SPEKK FM", "HEKKINGEN FM", "ÅRE FM", "KOBBE FM"}
T_OIL, T_GAS, FAR_KM, LEGACY_KM = 100.0, 150.0, 300.0, 2.0
FM = DATA / "sodir" / "factmaps"
HIGH = ("High", "Elevation")


def _grid():
    g = np.load(EARTH / "grid.npz"); s = np.load(EARTH / "surfaces.npz")
    return g, s["mean"][list(s["names"]).index("SEABED")].astype(np.float64)


def _project_lines(geoms):
    from se.evidence.spatial import project

    pts = []
    for c in geoms:
        p = project(c[:, 0], c[:, 1])
        for a, b in zip(p[:-1], p[1:]):  # densify to <= 0.5 km so vertex distance approximates line distance
            n = max(1, int(np.ceil(np.hypot(*(b - a)) / 0.5))); pts.append(a + (b - a) * np.linspace(0, 1, n + 1)[:, None])
    return np.vstack(pts)


def faults_tree() -> cKDTree:
    d = json.loads((FM / "faults_and_boundaries.geojson").read_text())
    lines = [np.asarray(f["geometry"]["coordinates"], float) for f in d["features"] if f["properties"].get("TEMA_DEF") == "faults" and f["geometry"]]
    return cKDTree(_project_lines(lines))


def _inside(px, py, ring):
    """Ray casting: points (px, py) inside one polygon ring (same units)."""
    ins = np.zeros(len(px), bool); x, y = ring[:, 0], ring[:, 1]
    for k in range(len(ring) - 1):
        x0, y0, x1, y1 = x[k], y[k], x[k + 1], y[k + 1]
        c = (y0 > py) != (y1 > py)
        if c.any():
            xi = x0 + (py - y0) * (x1 - x0) / np.where(y1 == y0, 1e-12, y1 - y0)
            ins ^= c & (px < xi)
    return ins


def on_high(X, Y) -> np.ndarray:
    from se.evidence.spatial import project

    d = json.loads((FM / "structural_elements.geojson").read_text()); out = np.zeros(len(X), bool)
    for f in d["features"]:
        if not any(h in (f["properties"].get("TOPOGRAPHY") or "") for h in HIGH):
            continue
        polys = f["geometry"]["coordinates"] if f["geometry"]["type"] == "MultiPolygon" else [f["geometry"]["coordinates"]]
        for poly in polys:
            r = np.asarray(poly[0], float); r = project(r[:, 0], r[:, 1])
            bb = (X >= r[:, 0].min()) & (X <= r[:, 0].max()) & (Y >= r[:, 1].min()) & (Y <= r[:, 1].max())
            if bb.any():
                ins = _inside(X[bb], Y[bb], r)
                for hole in poly[1:]:
                    h = np.asarray(hole, float); h = project(h[:, 0], h[:, 1]); ins &= ~_inside(X[bb], Y[bb], h)
                out[np.where(bb)[0][ins]] = True
    return out


def flood(top: np.ndarray):
    """Priority flood of a depth surface (NaN = absent) from its edges: oil rises, so closures are local minima of depth.
    Returns the filled surface, the visiting order and each column's parent (the up-dip neighbour oil leaves it by; -1 at the exits)."""
    import heapq

    ny, nx = top.shape; ok = np.isfinite(top); done = ~ok; fill = np.where(ok, top, np.nan); h = []
    parent = np.full(ny * nx, -1, np.int64); order = []
    for j in range(ny):
        for i in range(nx):
            if ok[j, i] and (j in (0, ny - 1) or i in (0, nx - 1) or not ok[max(j - 1, 0):j + 2, max(i - 1, 0):i + 2].all()):
                heapq.heappush(h, (top[j, i], j, i)); done[j, i] = True
    while h:
        z, j, i = heapq.heappop(h); order.append(j * nx + i)
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = j + dj, i + di
            if 0 <= a < ny and 0 <= b < nx and not done[a, b]:
                done[a, b] = True; fill[a, b] = max(top[a, b], z); parent[a * nx + b] = j * nx + i; heapq.heappush(h, (fill[a, b], a, b))
    return fill, np.array(order, np.int64), parent


def closure(top: np.ndarray) -> np.ndarray:
    """Height of structural closure (fill - depth, m); 0 outside closures and where the unit is absent."""
    fill, _, _ = flood(top)
    return np.where(np.isfinite(top), fill - top, 0.0)


def migrate(top: np.ndarray, p_kitchen: np.ndarray, cell_km2: float):
    """Fill-and-spill charge on one unit top (see the module doc): (closure m, charge km2, p_charge), each (ny, nx)."""
    from scipy.ndimage import label

    fill, order, parent = flood(top); ok = np.isfinite(top); shape = top.shape
    p = np.where(ok, np.clip(p_kitchen, 0, 1 - 1e-9), 0.0).ravel()
    acc = p * cell_km2; lq = np.log1p(-p)  # log P(no mature kitchen upstream)
    for k in order[::-1]:  # deepest (last visited) first: pass charge to the up-dip parent
        q = parent[k]
        if q >= 0:
            acc[q] += acc[k]; lq[q] += lq[k]
    acc, lq = acc.reshape(shape), lq.reshape(shape)
    clos = np.where(ok, fill - top, 0.0); comp, n = label(clos > 1.0)
    if n:  # a closure holds what passes its spill point: the largest charge inside it
        mx = np.zeros(n + 1); np.maximum.at(mx, comp.ravel(), acc.ravel()); mq = np.zeros(n + 1); np.minimum.at(mq, comp.ravel(), lq.ravel())
        inside = comp > 0; acc[inside] = mx[comp[inside]]; lq[inside] = mq[comp[inside]]
    return clos, np.where(ok, acc, 0.0), np.where(ok, -np.expm1(lq), 0.0)


def _kitchen(p, X, Y):
    m = p >= 0.5
    if not m.any():
        return np.full(X.shape, FAR_KM)
    d, _ = cKDTree(np.c_[X[m], Y[m]]).query(np.c_[X.ravel(), Y.ravel()])
    return np.minimum(d.reshape(X.shape), FAR_KM)


def build() -> dict:
    from se.earth.grid import thickness_map
    from se.earth.temperature import predict

    g, sea = _grid(); labels = [str(s).split("|") for s in g["labels"]]; lab, zb = g["label"], g["zb"].astype(np.float64)
    X, Y = np.meshgrid(g["x"], g["y"]); mid = 0.5 * (zb[:-1] + zb[1:]); dz = np.diff(zb, axis=0)
    rp = json.loads((EARTH / "poroperm_report.json").read_text()) if (EARTH / "poroperm_report.json").exists() else {}
    E = np.zeros(X.shape)
    if (EARTH / "poroperm_wells.parquet").exists():
        from se.earth.poroperm import burial_map, gradient

        E = np.clip(burial_map(pd.read_parquet(EARTH / "poroperm_wells.parquet"), X.ravel(), Y.ravel()).reshape(X.shape), 0, None); gr = gradient()
    else:
        gr = 0.0
    p_oil, p_gas, p_max = np.zeros(X.shape), np.zeros(X.shape), np.zeros(X.shape); found = {}
    for li, (gn, fn) in enumerate(labels):
        if fn not in SOURCES:
            continue
        m = lab == li; th = (dz * m).sum(0); pres = g["inside"] & (th > 1)
        if not pres.any():
            continue
        zm = (mid * dz * m).sum(0) / np.maximum(th, 1e-9); zbm = np.maximum(zm - sea, 50.0)
        T, sT = predict(X[pres], Y[pres], zbm[pres], sea[pres]); sT = np.maximum(sT, 1.0)
        for arr, t_, extra in ((p_oil, T_OIL, 0.0), (p_gas, T_GAS, 0.0), (p_max, T_OIL, gr * E[pres])):
            arr[pres] = np.maximum(arr[pres], 1 - N.cdf((t_ - (T + extra)) / sT))
        found[fn] = {"columns": int(pres.sum()), "T_median_C": round(float(np.median(T)), 1), "share_oil_window": round(float(np.mean(1 - N.cdf((T_OIL - T) / sT) >= 0.5)), 3)}
    kit_oil, kit_gas, kit_max = _kitchen(p_oil, X, Y), _kitchen(p_gas, X, Y), _kitchen(p_max, X, Y)
    fault_km = faults_tree().query(np.c_[X.ravel(), Y.ravel()])[0].reshape(X.shape)
    high = on_high(X.ravel(), Y.ravel()).reshape(X.shape)
    salt = thickness_map(lambda s: s.startswith("ZECHSTEIN GP")) / 1000
    clos = np.zeros((len(labels),) + X.shape, np.float32); chg, chg_max, pch, pch_max = (np.zeros_like(clos) for _ in range(4))
    km2 = float(np.diff(g["x"][:2])[0] * np.diff(g["y"][:2])[0])
    for li in range(len(labels)):
        m = lab == li
        if m.any():
            top = np.where(m, zb[:-1], np.inf).min(0); top = np.where(np.isfinite(top) & g["inside"], top, np.nan)
            clos[li], chg[li], pch[li] = migrate(top, p_oil, km2)
            _, chg_max[li], pch_max[li] = migrate(top, p_max, km2)
    np.savez_compressed(EARTH / "factors.npz", x=g["x"], y=g["y"], p_oil=p_oil.astype(np.float32), p_gas=p_gas.astype(np.float32), p_max=p_max.astype(np.float32),
                        kit_oil=kit_oil.astype(np.float32), kit_gas=kit_gas.astype(np.float32), kit_max=kit_max.astype(np.float32), fault_km=fault_km.astype(np.float32),
                        on_high=high, salt_km=salt.astype(np.float32), closure=clos, labels=g["labels"], E=E.astype(np.float32),
                        charge=chg, charge_max=chg_max, p_charge=pch, p_charge_max=pch_max)
    ins = g["inside"]
    out = {"sources": found, "share_columns_over_oil_kitchen": round(float((p_oil[ins] >= 0.5).mean()), 3), "share_over_gas_kitchen": round(float((p_gas[ins] >= 0.5).mean()), 3),
           "share_over_kitchen_at_max_burial": round(float((p_max[ins] >= 0.5).mean()), 3), "kit_oil_median_km": round(float(np.median(kit_oil[ins])), 1),
           "fault_km_median": round(float(np.median(fault_km[ins])), 1), "share_on_high": round(float(high[ins].mean()), 3),
           "salt_columns": int((salt[ins] > 0.05).sum()), "closure_cells_gt_20m": int((clos > 20).sum()),
           "share_unit_columns_charged": round(float((pch[clos >= 0] > 0.5).sum() / max(1, (chg >= 0).sum())), 3), "share_charged_at_max_burial": round(float((pch_max > 0.5).sum() / max(1, pch_max.size)), 3), "E_median_m": round(float(np.median(E[ins]))),
           "porosity_trend": rp.get("adopted_trend"), "T_oil_C": T_OIL, "T_gas_C": T_GAS}
    (EARTH / "factors_report.json").write_text(json.dumps(out, indent=1))
    manifest.write(EARTH / "factors.npz", [EARTH / "grid.npz", EARTH / "temperature_report.json", FM / "faults_and_boundaries.geojson", FM / "structural_elements.geojson"],
                   {"T_oil": T_OIL, "T_gas": T_GAS})
    return out


_F = {}


def at(q: pd.DataFrame) -> pd.DataFrame:
    """Factor features at rows with x, y (3035 km) and unit: nearest column; closure of the row's unit (0 if the unit is not there)."""
    if "f" not in _F or _F["path"] != EARTH:
        _F.update(f=dict(np.load(EARTH / "factors.npz")), path=EARTH)
    f = _F["f"]; x, y = q.x.to_numpy(float), q.y.to_numpy(float)
    i = np.abs(f["x"][None] - x[:, None]).argmin(1); j = np.abs(f["y"][None] - y[:, None]).argmin(1)
    li = {}
    for k, s in enumerate(f["labels"]):
        gn, fn = str(s).split("|"); li.setdefault(fn or gn, k)
    lk = q.unit.map(li).fillna(-1).astype(int).to_numpy(); u = np.maximum(lk, 0)
    per = lambda k: np.where(lk >= 0, f[k][u, j, i], 0.0) if k in f else np.zeros(len(q))
    c = per("closure")
    return pd.DataFrame({"lkit": np.log1p(f["kit_oil"][j, i]), "lkit_gas": np.log1p(f["kit_gas"][j, i]), "lkit_max": np.log1p(f["kit_max"][j, i]),
                         "mature": f["p_oil"][j, i], "lfault": np.log1p(f["fault_km"][j, i]), "on_high": f["on_high"][j, i].astype(float),
                         "salt": f["salt_km"][j, i], "lclos": np.log1p(c / 10.0), "lcharge": np.log1p(per("charge")), "lcharge_max": np.log1p(per("charge_max")),
                         "p_charge": per("p_charge"), "p_charge_max": per("p_charge_max"), "closure_m": c}, index=q.index)


def legacy(C: pd.DataFrame) -> np.ndarray:
    """Per cell: wellbores within LEGACY_KM whose total depth (TVDSS) is below the cell's top, i.e. that drilled through it."""
    w = pd.read_parquet(EARTH / "wells.parquet").dropna(subset=["x", "y"])
    tvd = w.tvd_est.where(w.tvd_est.notna(), w.td) if "tvd_est" in w else w.tvd_td.where(w.tvd_td.notna(), w.td)  # estimated TVD where FactPages has none (frame)
    w = w.assign(z=tvd - w.kb.fillna(0)).dropna(subset=["z"])
    tree = cKDTree(w[["x", "y"]].to_numpy()); z = w.z.to_numpy()
    cols = C.groupby(["i", "j"]).indices; out = np.zeros(len(C), np.int32)
    for (_, _), ix in cols.items():
        nb = tree.query_ball_point([C.x.iat[ix[0]], C.y.iat[ix[0]]], LEGACY_KM)
        if nb:
            out[ix] = (z[nb][None] > C.top.to_numpy()[ix][:, None]).sum(1)
    return out


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
