"""Earth model API for the pilot (PLAN P7.1, LOG L070): surfaces with thickness, target probabilities with support, true well paths,
and the evidence chain behind one cell. Coordinates: EPSG:3035 km; depth: TVDSS m (positive down)."""
import json
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from se.config import EARTH

router = APIRouter(prefix="/api/earth")
TARGETS = ["hydrocarbons", "reservoir", "overpressure", "co2_storage", "green_clay", "calcareous_clay", "sandy_delta"]
TITLES = {"hydrocarbons": "Hydrocarbons", "reservoir": "Reservoir quality (porosity > 15 %, permeability > 10 mD)", "overpressure": "Overpressure (pore pressure >= 1.20 g/cm3)",
          "co2_storage": "CO2 storage (dense CO2, reservoir, seal, no overpressure)", "green_clay": "Green clay in described clay", "calcareous_clay": "Calcareous clay",
          "sandy_delta": "Sandy delta (deltaic unit, sand share >= 0.4)"}


def _r(a, d=1):
    return [None if not np.isfinite(v) else round(float(v), d) for v in np.asarray(a, float).ravel()]


@lru_cache(maxsize=1)
def _surf():
    return dict(np.load(EARTH / "surfaces.npz"))


@lru_cache(maxsize=1)
def _cells() -> pd.DataFrame:
    return pd.read_parquet(EARTH / "targets" / "cells.parquet")


@lru_cache(maxsize=8)
def _target(t: str) -> dict:
    if t not in TARGETS:
        raise HTTPException(404, "no such target")
    return dict(np.load(EARTH / "targets" / f"{t}.npz"))


@lru_cache(maxsize=1)
def _report() -> dict:
    return json.loads((EARTH / "targets" / "report.json").read_text())


@router.get("/meta")
def meta():
    s = _surf(); rep = _report()
    names, level = [str(n) for n in s["names"]], [str(l) for l in s["level"]]
    col = json.loads((EARTH / "column.json").read_text())
    from se.config import PILOT

    return {"pilot": PILOT, "x": _r(s["x"], 1), "y": _r(s["y"], 1), "horizons": [{"name": n, "level": l} for n, l in zip(names, level)],
            "groups": [{"group": c["group"], "formations": [f["name"] for f in c["formations"] if f["model"]]} for c in col["groups"] if c["model"]],
            "targets": [{"id": t, "title": TITLES[t], **({k: rep[t].get(k) for k in ("published", "gain_model_vs_base", "gain_unit_prior_vs_base", "base_rate", "rows", "wells", "calibrated", "why", "checks", "composite")} if t in rep else {})}
                        for t in TARGETS],
            "frame": "EPSG:3035 km; depth TVDSS m below sea level, positive down", "rules": json.loads((EARTH / "earth_rules_report.json").read_text()) if (EARTH / "earth_rules_report.json").exists() else []}


@router.get("/surfaces")
def surfaces(names: str = "", step: int = 2):
    """Mean depth and sd of the chosen horizons on the lattice (every `step`th node), with the inside-pilot mask. Thickness of a unit =
    the next surface down minus its top, so a unit is drawn as its top and base."""
    s = _surf(); all_names = [str(n) for n in s["names"]]
    want = [n for n in names.split(",") if n] or all_names
    sl = (slice(None, None, step), slice(None, None, step)); inside = s["inside"][sl]
    out = []
    for n in want:
        if n not in all_names:
            continue
        k = all_names.index(n); m = np.where(inside, s["mean"][k][sl], np.nan); sd = np.where(inside, s["sd"][k][sl], np.nan)
        out.append({"name": n, "level": str(s["level"][k]), "z": [_r(r, 0) for r in m], "sd": [_r(r, 0) for r in sd], "near_km": [_r(r, 1) for r in np.where(inside, s["near_km"][k][sl], np.nan)]})
    return {"x": _r(s["x"][::step]), "y": _r(s["y"][::step]), "surfaces": out}


@router.get("/target")
def target(t: str, pmin: float = 0.5, smin: float = 0.0, units: str = "", limit: int = 30000):
    """Cells whose probability is at least pmin (and support at least smin): position, depth interval, p, 90 percent range, support."""
    d, C = _target(t), _cells()
    m = (d["p"] >= pmin) & (d["support"] >= smin)
    if units:
        m &= C.unit.isin(units.split(",")).to_numpy()
    idx = np.where(m)[0]
    if len(idx) > limit:  # keep the most supported, most likely cells
        idx = idx[np.argsort(-(d["p"][idx] * (0.2 + d["support"][idx])))[:limit]]
    c = C.iloc[idx]
    return {"target": t, "title": TITLES[t], "n": int(m.sum()), "shown": int(len(idx)), "x": _r(c.x), "y": _r(c.y), "top": _r(c.top, 0), "base": _r(c.base, 0),
            "unit": c.unit.tolist(), "p": _r(d["p"][idx], 3), "p05": _r(d["p05"][idx], 3), "p95": _r(d["p95"][idx], 3), "support": _r(d["support"][idx], 2), "cell": idx.tolist()}


@router.get("/wells")
def wells(step_m: float = 25.0):
    """Pilot wells with formation tops: the true FORCE path where we have it, else the FactPages approximation (straight from the head)."""
    w = pd.read_parquet(EARTH / "wells.parquet"); w = w[w.pilot]
    tops = pd.read_parquet(EARTH / "tops.parquet"); have = set(tops.wellbore)
    paths = pd.read_parquet(EARTH / "force_paths.parquet")
    out = []
    for r in w[w.wellbore.isin(have)].itertuples():
        p = paths[paths.wellbore == r.wellbore]
        if len(p):
            p = p.iloc[:: max(1, int(step_m))]
            out.append({"name": r.wellbore, "source": "FORCE path", "x": _r(p.x, 3), "y": _r(p.y, 3), "z": _r(p.tvdss, 0)})
        else:
            t = tops[tops.wellbore == r.wellbore]
            z1 = float(np.nanmax(t.bot_tvdss.fillna(t.top_tvdss))) if len(t) else float(r.wd or 0) + 500
            out.append({"name": r.wellbore, "source": "FactPages (approximate)", "x": [round(float(r.x), 3)] * 2, "y": [round(float(r.y), 3)] * 2, "z": [round(float(r.wd or 0)), round(z1)]})
    return out


@router.get("/cell")
def cell(t: str, cell: int):
    """The evidence chain behind one cell: where it is, what it is, its properties, the target probability with its range and support,
    the observations of the same unit nearest to it, and the rules that bear on the target."""
    from se.earth import targets as T

    C = _cells()
    if not 0 <= cell < len(C):
        raise HTTPException(404, "no such cell")
    c = C.iloc[cell]; d = _target(t); rep = _report().get(t, {})
    out = {"cell": int(cell), "unit": c.unit, "group": c.group, "x_km": round(float(c.x), 1), "y_km": round(float(c.y), 1), "top_m": round(float(c.top)), "base_m": round(float(c.base)),
           "thickness_m": round(float(c.thick)), "depth_below_seabed_m": round(float(c.zb)), "target": t, "title": TITLES[t],
           "p": round(float(d["p"][cell]), 3), "p05": round(float(d["p05"][cell]), 3), "p95": round(float(d["p95"][cell]), 3), "support": round(float(d["support"][cell]), 2),
           "published": rep.get("published"), "held_out": {k: rep.get(k) for k in ("gain_model_vs_base", "gain_unit_prior_vs_base", "base_rate", "rows", "wells", "use_platt")},
           "coefficients": rep.get("coefficients")}
    s = _surf(); names = [str(n) for n in s["names"]]
    if c.group in names:
        k = names.index(c.group); out["group_top_sd_m"] = round(float(s["sd"][k][int(c.j), int(c.i)])); out["group_top_nearest_pick_km"] = round(float(s["near_km"][k][int(c.j), int(c.i)]), 1)
    if t != "co2_storage":
        o = T.observations(t)
        same = o[o.unit == c.unit].assign(d_km=lambda q: np.hypot(q.x - c.x, q.y - c.y)).sort_values("d_km").head(8)
        out["nearest_observations"] = [{"wellbore": r.wellbore, "distance_km": round(float(r.d_km), 1), "event": round(float(r.ev), 3), "weight": round(float(r.w), 2)} for r in same.itertuples()]
        out["unit_rate"] = round(float(np.average(o[o.unit == c.unit].ev, weights=o[o.unit == c.unit].w)), 3) if (o.unit == c.unit).any() else None
    else:
        out["composite"] = rep.get("composite"); out["terms"] = {k: round(float(_target(k)["p"][cell]), 3) for k in ("reservoir", "overpressure")}
    rules = json.loads((EARTH / "earth_rules_report.json").read_text()) if (EARTH / "earth_rules_report.json").exists() else []
    use = {"hydrocarbons": ["R-SEAL", "R-DRAUPNE"], "reservoir": ["R-ATHY", "R-DPHI"], "overpressure": ["R-HYD"], "co2_storage": ["R-CO2", "R-SEAL", "R-GEO", "R-HYD"],
           "sandy_delta": ["R-BRENT"], "green_clay": [], "calcareous_clay": []}[t]
    out["rules"] = [{"id": r["id"], "statement": r["statement"], "verdict": r["test"].get("verdict"), "status": r["status"]} for r in rules if r["id"] in use]
    return out


@router.get("/tied")
def tied(step: int = 2):
    """Seismic horizons tied to wells (L058) in depth on the lattice, with lat/lon so other views can place them; only where interpreted."""
    p = EARTH / "seismic_surfaces.npz"
    if not p.exists():
        return {"surfaces": []}
    t, s = np.load(p), _surf()
    sl = (slice(None, None, step), slice(None, None, step))
    out = []
    for k, n in enumerate(t["names"]):
        w = t["weight"][k][sl]; z = np.where(w > 0, t["mean"][k][sl], np.nan)
        out.append({"name": str(n), "z": [_r(r, 0) for r in z], "sd": [_r(r, 0) for r in np.where(w > 0, t["sd"][k][sl], np.nan)]})
    return {"lat": [_r(r, 4) for r in s["lat"][sl]], "lon": [_r(r, 4) for r in s["lon"][sl]], "surfaces": out,
            "source": "Smeaheia Key_Horizons_2010 (Equinor, Gassnova), tied to wells (L058); depth below sea level"}


@router.get("/property")
def prop(name: str = "gamma_ray", units: str = "", limit: int = 30000):
    """A cell property between wells (gamma_ray: L071), thinned evenly to `limit` cells, with its sigma and the held-out test."""
    if name != "gamma_ray":
        raise HTTPException(404, "no such property")
    d, C = dict(np.load(EARTH / "targets" / "gamma_ray.npz")), _cells()
    m = np.ones(len(C), bool) if not units else C.unit.isin(units.split(",")).to_numpy()
    idx = np.where(m)[0]; idx = idx[:: max(1, len(idx) // limit)][:limit]
    c = C.iloc[idx]
    return {"name": name, "unit_of_value": "gAPI", "n": int(m.sum()), "shown": int(len(idx)), "x": _r(c.x), "y": _r(c.y), "top": _r(c.top, 0), "base": _r(c.base, 0), "unit": c.unit.tolist(),
            "value": _r(d["value"][idx], 1), "sd": _r(d["sd"][idx], 1), "cell": idx.tolist(), "test": json.loads((EARTH / "targets" / "gamma_ray_report.json").read_text())}
