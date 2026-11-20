"""Earth model API for the pilot (PLAN P7.1, LOG L070): surfaces with thickness, target probabilities with support, true well paths,
and the evidence chain behind one cell. Coordinates: EPSG:3035 km; depth: TVDSS m (positive down)."""
import json
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from se.config import OUT, REGIONS
from se.earth import snapshot

_pinned = ContextVar[tuple[str, Path] | None]("earth_snapshot", default=None)


def _resolve(region: str, build: str | None = None) -> Path:
    if region not in REGIONS:
        raise HTTPException(404, "no such region")
    try:
        return snapshot.resolve(OUT / "earth" / region, build)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404 if build else 503, str(exc)) from exc


BuildQuery = Annotated[str | None, Query(pattern=f"^(?:{snapshot.BUILD_ID}|{snapshot.LEGACY})$")]


async def _build_scope(region: str = "pilot", build: BuildQuery = None):
    token = _pinned.set((region, _resolve(region, build)))
    try:
        yield
    finally:
        _pinned.reset(token)


router = APIRouter(prefix="/api/earth", dependencies=[Depends(_build_scope)])


def _dir(region: str):
    """Artefacts of one region (P8); a region shows up once its pipeline has written targets."""
    pinned = _pinned.get()
    d = pinned[1] if pinned and pinned[0] == region else _resolve(region)
    if not (d / "targets" / "cells.parquet").exists():
        raise HTTPException(404, f"region {region} is not built yet")
    return d


def _build(d: Path) -> str | None:
    return d.name if d.parent.name == snapshot.STORE else None


TARGETS = ["hydrocarbons", "oil", "gas", "chance_of_success", "reservoir", "overpressure", "co2_storage", "green_clay", "calcareous_clay", "sandy_delta"]
TITLES = {"chance_of_success": "Chance of success (reservoir x seal x charge x trap)", "hydrocarbons": "Hydrocarbons", "oil": "Oil (oil or oil and gas)", "gas": "Gas (gas or oil and gas)", "reservoir": "Reservoir quality (porosity > 15 %, permeability > 10 mD)", "overpressure": "Overpressure (pore pressure >= 1.20 g/cm3)",
          "co2_storage": "CO2 storage (dense CO2, reservoir, seal, no overpressure)", "green_clay": "Green clay in described clay", "calcareous_clay": "Calcareous clay",
          "sandy_delta": "Sandy delta (deltaic unit, sand share >= 0.4)"}


def _r(a, d=1):
    return [None if not np.isfinite(v) else round(float(v), d) for v in np.asarray(a, float).ravel()]


def _surf(region="pilot"):
    return _load_surfaces(_dir(region))


@lru_cache(maxsize=4)
def _load_surfaces(d: Path):
    s = dict(np.load(d / "surfaces.npz")); g = d / "grid.npz"
    if g.exists():  # the grid's mask: the region box and the offshore NCS (shelf.py), so no sheet is drawn over land
        gi = np.load(g)["inside"]
        if gi.shape == s["inside"].shape:
            s["inside"] = s["inside"] & gi
    return s


def _cells(region="pilot") -> pd.DataFrame:
    return _load_cells(_dir(region))


@lru_cache(maxsize=4)
def _load_cells(d: Path):
    return pd.read_parquet(d / "targets" / "cells.parquet")


@lru_cache(maxsize=32)
def _load_target(d: Path, t: str) -> dict:
    if t not in TARGETS:
        raise HTTPException(404, "no such target")
    path = d / "targets" / f"{t}.npz"
    if not path.is_file():
        raise HTTPException(404, "target not built in this region")
    with np.load(path) as arrays:
        value = dict(arrays)
    cells = _load_cells(d)
    if len(value["p"]) != len(cells) or any(not np.array_equal(value[k], cells[k]) for k in ("i", "j", "label")):
        _load_cells.cache_clear()
        raise HTTPException(503, "target and cell identities do not match")
    return value


def _target(t: str, region="pilot") -> dict:
    return _load_target(_dir(region), t)


def _report(region="pilot") -> dict:
    return _load_report(_dir(region))


@lru_cache(maxsize=4)
def _load_report(d: Path) -> dict:
    return json.loads((d / "targets" / "report.json").read_text())


@router.get("/regions")
def regions():
    """All regions, which are built, and their held-out skill per target (the P8 comparison)."""
    out = []
    for r, b in REGIONS.items():
        d = _resolve(r); built = (d / "targets" / "report.json").exists()
        rep = json.loads((d / "targets" / "report.json").read_text()) if built else {}
        run = json.loads((d / "run_report.json").read_text()) if (d / "run_report.json").exists() else {}
        out.append({"id": r, "title": b["title"], "short": b.get("short", b["title"]), "lat": b["lat"], "lon": b["lon"], "step_km": b["step_km"], "built": built, "build": _build(d),
                    "skill": {t: {k: rep[t].get(k) for k in ("gain_model_vs_base", "gain_unit_prior_vs_base", "published", "rows", "wells", "features")}
                              | {"forward_in_time": (rep[t].get("time_test") or {}).get("gain_selected_features")} for t in TARGETS if t in rep and t != "co2_storage"},
                    "steps": {k: v.get("status") for k, v in run.items() if isinstance(v, dict) and "status" in v}})
    return out


def _presets(region: str) -> dict:
    return _load_presets(_dir(region))


@lru_cache(maxsize=8)
def _load_presets(d: Path) -> dict:
    """Per target: the 90th percentile of the cell probabilities (the default threshold: the top 10 percent of cells, so a rare target is
    not hidden behind a fixed 0.5) and the groups where its probability is highest (the suggested strata to show)."""
    C = _load_cells(d); out = {}
    for t in TARGETS:
        p = d / "targets" / f"{t}.npz"
        if not p.exists():
            continue
        v = np.load(p)["p"].astype(float)
        if len(v) != len(C):  # the region is being rebuilt: this target is newer than the cell table
            continue
        g = pd.DataFrame({"g": C.group.to_numpy(), "p": v}).groupby("g").p.agg(["mean", "size"])
        out[t] = {"q90": round(float(np.percentile(v, 90)), 3), "q50": round(float(np.median(v)), 3), "top_groups": g[g["size"] >= 100].sort_values("mean", ascending=False).index[:3].tolist()}
    return out


@router.get("/meta")
def meta(region: str = "pilot"):
    EARTH = _dir(region); s = _surf(region); rep = _report(region)
    names, level = [str(n) for n in s["names"]], [str(l) for l in s["level"]]
    col = json.loads((EARTH / "column.json").read_text())
    return {"region": region, "build": _build(EARTH), "pilot": REGIONS[region], "x": _r(s["x"], 1), "y": _r(s["y"], 1), "horizons": [{"name": n, "level": l} for n, l in zip(names, level)],
            "export_available": (EARTH / "export" / f"{region}_all.zip").is_file(),
            "groups": [{"group": c["group"], "formations": [f["name"] for f in c["formations"] if f["model"]]} for c in col["groups"] if c["model"]],
            "targets": [{"id": t, "title": TITLES[t], **({k: rep[t].get(k) for k in ("published", "gain_model_vs_base", "gain_unit_prior_vs_base", "base_rate", "rows", "wells", "calibrated", "why", "checks", "composite",
                                                                              "features", "time_test", "legacy_wells", "test", "limiting_share", "family", "families",
                                                                              "gain_nested", "gain_selected_on_same_folds", "model_rejected")} if t in rep else {})}
                        for t in TARGETS if t in rep],
            "conditional_on": rep.get("_conditional_on"), "presets": _presets(region),
            "co2_capacity": json.loads((EARTH / "targets" / "co2_capacity.json").read_text()) if (EARTH / "targets" / "co2_capacity.json").exists() else None,
            "frame": "EPSG:3035 km; depth TVDSS m below sea level, positive down", "rules": json.loads((EARTH / "earth_rules_report.json").read_text()) if (EARTH / "earth_rules_report.json").exists() else []}


@router.get("/snapshot")
def snapshot_receipt(region: str = "pilot"):
    path = _dir(region) / snapshot.RECEIPT
    if not path.is_file():
        raise HTTPException(404, "this region has not been frozen")
    return json.loads(path.read_text())


@router.get("/surfaces")
def surfaces(names: str = "", step: int = 2, region: str = "pilot"):
    """Mean depth and sd of the chosen horizons on the lattice (every `step`th node), with the inside-pilot mask. Thickness of a unit =
    the next surface down minus its top, so a unit is drawn as its top and base."""
    s = _surf(region); all_names = [str(n) for n in s["names"]]
    want = [n for n in names.split(",") if n] or all_names
    sl = (slice(None, None, step), slice(None, None, step)); inside = s["inside"][sl]
    out = []
    for n in want:
        if n not in all_names:
            continue
        k = all_names.index(n); m = np.where(inside, s["mean"][k][sl], np.nan); sd = np.where(inside, s["sd"][k][sl], np.nan)
        out.append({"name": n, "level": str(s["level"][k]), "z": [_r(r, 0) for r in m], "sd": [_r(r, 0) for r in sd], "near_km": [_r(r, 1) for r in np.where(inside, s["near_km"][k][sl], np.nan)]})
    return {"build": _build(_dir(region)), "x": _r(s["x"][::step]), "y": _r(s["y"][::step]), "surfaces": out}


@router.get("/target")
def target(t: str, pmin: float = 0.5, smin: float = 0.0, units: str = "", limit: int = 30000, region: str = "pilot"):
    """Cells whose probability is at least pmin (and support at least smin): position, depth interval, p, 90 percent range, support."""
    d, C = _target(t, region), _cells(region)
    m = (d["p"] >= pmin) & (d["support"] >= smin)
    if units:
        m &= C.unit.isin(units.split(",")).to_numpy()
    idx = np.where(m)[0]
    if len(idx) > limit:  # keep the most supported, most likely cells
        idx = idx[np.argsort(-(d["p"][idx] * (0.2 + d["support"][idx])))[:limit]]
    c = C.iloc[idx]
    return {"build": _build(_dir(region)), "target": t, "title": TITLES[t], "n": int(m.sum()), "shown": int(len(idx)), "x": _r(c.x), "y": _r(c.y), "top": _r(c.top, 0), "base": _r(c.base, 0),
            "unit": c.unit.tolist(), "p": _r(d["p"][idx], 3), "p05": _r(d["p05"][idx], 3), "p95": _r(d["p95"][idx], 3), "support": _r(d["support"][idx], 2), "cell": idx.tolist()}


@router.get("/wells")
def wells(step_m: float = 25.0, region: str = "pilot"):
    """Pilot wells with formation tops: the true FORCE path where we have it, else the FactPages approximation (straight from the head)."""
    EARTH = _dir(region)
    w = pd.read_parquet(EARTH / "wells.parquet"); w = w[w.pilot]  # "pilot" = inside the region's box
    tops = pd.read_parquet(EARTH / "tops.parquet"); have = set(tops.wellbore)
    paths = dict(tuple(pd.read_parquet(EARTH / "force_paths.parquet").groupby("wellbore")))
    intervals = dict(tuple(tops.groupby("wellbore")))
    out = []
    for r in w[w.wellbore.isin(have)].itertuples():
        datum = dict(zip(("rkb_m", "water_depth_m", "td_md_m", "end_tvd_m", "end_tvd_sd_m"),
                         _r([r.kb, r.wd, r.td, r.tvd_est, r.tvd_sd], 1)))
        p = paths.get(r.wellbore)
        if p is not None:
            p = p.iloc[:: max(1, int(step_m))]
            path = {"source": "FORCE path", "x": _r(p.x, 3), "y": _r(p.y, 3), "z": _r(p.tvdss, 0)}
        else:
            t = intervals[r.wellbore]
            z1 = t.bot_tvdss.fillna(t.top_tvdss).max()
            path = {"source": "FactPages (approximate)", "x": _r([r.x, r.x], 3), "y": _r([r.y, r.y], 3), "z": _r([r.wd, z1], 0)}
        out.append({"name": r.wellbore, **path, **datum, "head": _r([r.x, r.y, r.wd], 3), "depth_source": r.source})
    return out


@router.get("/cell")
def cell(t: str, cell: int, region: str = "pilot", build: BuildQuery = None):
    """The evidence chain behind one cell: where it is, what it is, its properties, the target probability with its range and support,
    the observations of the same unit nearest to it, and the rules that bear on the target."""
    EARTH = _dir(region)
    if build is None and _build(EARTH):
        raise HTTPException(409, "select a cell from a scene with an explicit build ID")
    C = _cells(region)
    if not 0 <= cell < len(C):
        raise HTTPException(404, "no such cell")
    c = C.iloc[cell]; d = _target(t, region); rep = _report(region).get(t, {})
    out = {"cell": int(cell), "build": _build(EARTH), "unit": c.unit, "group": c.group, "x_km": round(float(c.x), 1), "y_km": round(float(c.y), 1), "top_m": round(float(c.top)), "base_m": round(float(c.base)),
           "thickness_m": round(float(c.thick)), "depth_below_seabed_m": round(float(c.zb)), "target": t, "title": TITLES[t],
           "p": round(float(d["p"][cell]), 3), "p05": round(float(d["p05"][cell]), 3), "p95": round(float(d["p95"][cell]), 3), "support": round(float(d["support"][cell]), 2),
           "published": rep.get("published"), "held_out": {k: rep.get(k) for k in ("gain_model_vs_base", "gain_unit_prior_vs_base", "base_rate", "rows", "wells", "use_platt")},
           "coefficients": rep.get("coefficients")}
    s = _surf(region); names = [str(n) for n in s["names"]]
    if c.group in names:
        k = names.index(c.group)
        out["group_top_sd_m"], out["group_top_nearest_pick_km"] = (
            _r([s[field][k, int(c.j), int(c.i)]], digits)[0] for field, digits in (("sd", 0), ("near_km", 1))
        )
    if t not in ("co2_storage", "chance_of_success"):
        op = EARTH / "targets" / f"{t}_obs.parquet"
        o = pd.read_parquet(op) if op.exists() else pd.DataFrame(columns=["wellbore", "unit", "x", "y", "ev", "w"])
        same = o[o.unit == c.unit].assign(d_km=lambda q: np.hypot(q.x - c.x, q.y - c.y)).sort_values("d_km").head(8)
        out["nearest_observations"] = [{"wellbore": r.wellbore, "distance_km": round(float(r.d_km), 1), "event": round(float(r.ev), 3), "weight": round(float(r.w), 2)} for r in same.itertuples()]
        out["unit_rate"] = round(float(np.average(o[o.unit == c.unit].ev, weights=o[o.unit == c.unit].w)), 3) if (o.unit == c.unit).any() else None
    else:
        out["composite"] = rep.get("composite"); out["terms"] = {k: round(float(_target(k, region)["p"][cell]), 3) for k in ("reservoir", "overpressure")}
        if t == "chance_of_success":  # the four elements and the one that limits this cell
            el = rep.get("composite", {}).get("elements", []); out["elements"] = {e: round(float(d[e][cell]), 3) for e in el if e in d}
            out["limiting_element"] = el[int(d["limit"][cell])] if "limit" in d and el else None; out["test"] = rep.get("test")
        cp = EARTH / "targets" / "co2_capacity.npz"
        if t == "co2_storage" and cp.exists():
            out["co2_capacity_kt"] = round(float(np.load(cp)["value"][cell]), 1)
        lp = EARTH / "targets" / "legacy_wells.npz"
        if lp.exists():
            out["legacy_wells"] = int(np.load(lp)["value"][cell]); out["legacy_note"] = LEGACY_NOTE
    if (EARTH / "factors.npz").exists():  # petroleum-system factors at this cell (P9), whether or not the target's model uses them
        from se.earth.factors import at

        f = at(C.iloc[[cell]], root=EARTH).iloc[0]
        out["factors"] = {"kitchen_km": round(float(np.expm1(f.lkit)), 1), "kitchen_at_max_burial_km": round(float(np.expm1(f.lkit_max)), 1), "gas_kitchen_km": round(float(np.expm1(f.lkit_gas)), 1),
                          "source_mature_below_p": round(float(f.mature), 2), "fault_km": round(float(np.expm1(f.lfault)), 1), "on_structural_high": bool(f.on_high),
                          "closure_m": round(float(np.expm1(f.lclos) * 10)), "salt_km": round(float(f.salt), 2),
                          "charge_p": round(float(f.p_charge), 2), "charge_km2": round(float(np.expm1(f.lcharge))), "charge_p_at_max_burial": round(float(f.p_charge_max), 2), "used_by_model": [k for k in (rep.get("features") or []) if k in f.index]}
    out["conditional_on"] = _report(region).get("_conditional_on"); out["time_test"] = rep.get("time_test")
    rules = json.loads((EARTH / "earth_rules_report.json").read_text()) if (EARTH / "earth_rules_report.json").exists() else []
    hc = ["R-SEAL", "R-DRAUPNE", "R-MATURE", "R-MATURE-MAX", "R-TRAP"]
    use = {"hydrocarbons": hc, "oil": hc, "gas": hc, "reservoir": ["R-ATHY", "R-DPHI", "R-QTZ", "R-UPLIFT"], "overpressure": ["R-HYD"],
           "co2_storage": ["R-CO2", "R-SEAL", "R-GEO", "R-HYD", "R-LEGACY", "R-SEABEDT", "R-SALT"], "chance_of_success": hc + ["R-CHARGE"], "sandy_delta": ["R-BRENT"], "green_clay": [], "calcareous_clay": []}[t]
    out["rules"] = [{"id": r["id"], "statement": r["statement"], "verdict": r["test"].get("verdict"), "status": r["status"]} for r in rules if r["id"] in use]
    return out


@router.get("/tied")
def tied(step: int = 2, region: str = "pilot"):
    """Seismic horizons tied to wells (L058) in depth on the lattice, with lat/lon so other views can place them; only where interpreted."""
    p = _dir(region) / "seismic_surfaces.npz"
    if not p.exists():
        return {"surfaces": []}
    t, s = np.load(p), _surf(region)
    sl = (slice(None, None, step), slice(None, None, step))
    out = []
    for k, n in enumerate(t["names"]):
        valid = (t["weight"][k][sl] > 0) & s["inside"][sl]
        z = np.where(valid, t["mean"][k][sl], np.nan)
        out.append({"name": str(n), "z": [_r(r, 0) for r in z], "sd": [_r(r, 0) for r in np.where(valid, t["sd"][k][sl], np.nan)]})
    return {"build": _build(_dir(region)), "lat": [_r(r, 4) for r in s["lat"][sl]], "lon": [_r(r, 4) for r in s["lon"][sl]], "surfaces": out,
            "source": "Smeaheia Key_Horizons_2010 (Equinor, Gassnova), tied to wells (L058); depth below sea level"}


@router.get("/property")
def prop(name: str = "gamma_ray", units: str = "", limit: int = 30000, region: str = "pilot"):
    """A cell property between wells (gamma_ray: L071; legacy_wells: P9.3), thinned evenly to `limit` cells, with its sigma and its test."""
    if name not in PROPS:
        raise HTTPException(404, "no such property")
    EARTH = _dir(region)
    if not (EARTH / "targets" / f"{name}.npz").exists():
        raise HTTPException(404, "no gamma-ray model in this region (no FORCE logs)" if name == "gamma_ray" else "not built in this region")
    d, C = dict(np.load(EARTH / "targets" / f"{name}.npz")), _cells(region)
    m = np.ones(len(C), bool) if not units else C.unit.isin(units.split(",")).to_numpy()
    idx = np.where(m)[0]; idx = idx[:: max(1, len(idx) // limit)][:limit]
    c = C.iloc[idx]
    test = json.loads((EARTH / "targets" / "gamma_ray_report.json").read_text()) if name == "gamma_ray" else \
        {"what": LEGACY_NOTE} if name == "legacy_wells" else \
        {"sigma_pct": float(d["sd"][0])} if name == "porosity" else {"what": "expected kt of CO2 per cell at the median storage efficiency (P10.4)"}
    return {"build": _build(EARTH), "name": name, "unit_of_value": PROPS[name], "n": int(m.sum()), "shown": int(len(idx)), "x": _r(c.x), "y": _r(c.y), "top": _r(c.top, 0), "base": _r(c.base, 0), "unit": c.unit.tolist(),
            "value": _r(d["value"][idx], 1), "sd": _r(d["sd"][idx], 1), "cell": idx.tolist(), "test": test}


LEGACY_NOTE = "Counts wellheads within 2 km whose estimated or reported end depth is below the cell top. Not proof of a trajectory intersection or a leak."
PROPS = {"gamma_ray": "gAPI", "legacy_wells": "nearby wellheads reaching below the cell top", "porosity": "percent", "co2_capacity": "kt CO2 per cell"}


@router.get("/export")
def export(region: str = "pilot"):
    """The region's surfaces (IRAP classic, ZMAP+) and zone grid (GRDECL with probabilities) as a zip, for Petrel or RMS (P10.7)."""
    from fastapi.responses import FileResponse

    d = _dir(region); z = d / "export" / f"{region}_all.zip"  # written by the pipeline's export step (the pod's data mount is read-only)
    if not z.exists() and _build(d):
        raise HTTPException(404, "no verified export in this snapshot")
    if not z.exists():
        raise HTTPException(404, f"no export for {region} yet: run EARTH_REGION={region} python -m se.earth.run export")
    suffix = f"_{_build(d)}" if _build(d) else ""
    return FileResponse(z, media_type="application/zip", filename=f"earth_{region}{suffix}.zip")


@lru_cache(maxsize=8)
def _map(d: Path):
    from se.earth.factors import FM, HIGH
    from se.evidence.spatial import project
    source = d / "map" if _build(d) else FM
    if not all((source / f).is_file() for f in snapshot.MAP_FILES):
        raise HTTPException(404, "no FactMaps layers in this snapshot")

    s = _load_surfaces(d); x0, x1, y0, y1 = float(s["x"].min()) - 30, float(s["x"].max()) + 30, float(s["y"].min()) - 30, float(s["y"].max()) + 30
    ok = lambda p: (p[:, 0] >= x0) & (p[:, 0] <= x1) & (p[:, 1] >= y0) & (p[:, 1] <= y1)

    def lines(coords):  # project, keep the parts inside the box, thin to about 1 km
        xs, ys = [], []
        for c in coords:
            p = project(np.asarray(c, float)[:, 0], np.asarray(c, float)[:, 1]); m = ok(p)
            if not m.any():
                continue
            keep = np.r_[True, np.hypot(*np.diff(p, axis=0).T) > 0] if len(p) > 1 else np.ones(1, bool)
            for k, v in enumerate(p):
                if m[k] and (keep[k] or k == len(p) - 1):
                    xs.append(round(float(v[0]), 2)); ys.append(round(float(v[1]), 2))
                elif xs and xs[-1] is not None:
                    xs.append(None); ys.append(None)
            xs.append(None); ys.append(None)
        return {"x": xs, "y": ys}

    f = json.loads((source / "faults_and_boundaries.geojson").read_text())
    faults = lines([ft["geometry"]["coordinates"] for ft in f["features"] if ft["geometry"] and ft["properties"].get("TEMA_DEF") == "faults"])
    e = json.loads((source / "structural_elements.geojson").read_text()); rings, names = [], []
    for ft in e["features"]:
        g = ft["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            r = np.asarray(poly[0], float); p = project(r[:, 0], r[:, 1])
            if ok(p).any():
                rings.append(poly[0]); c = p[ok(p)].mean(0)
                names.append({"name": ft["properties"].get("NAME"), "kind": ft["properties"].get("TOPOGRAPHY"), "high": any(h in (ft["properties"].get("TOPOGRAPHY") or "") for h in HIGH),
                              "x": round(float(c[0]), 1), "y": round(float(c[1]), 1)})
    return {"faults": faults, "elements": lines(rings), "element_names": names, "box": [x0, x1, y0, y1],
            "source": "Sodir FactMaps: faults and structural elements (regional map scale, NLOD licence)"}


@router.get("/map")
def map_layers(region: str = "pilot"):
    """Map layers for the 3D earth view, in EPSG:3035 km: mapped faults and structural element outlines with their names (P10, owner)."""
    return _map(_dir(region))


@router.get("/observed")
def observed(t: str, region: str = "pilot", units: str = "", limit: int = 20000):
    """What wells observed for a target, unit by unit, at true vertical depth (the frame of P1): the backtracking layer of the 3D view.
    Each row: well position at the unit top, the unit's top and base TVDSS, the observed value (0-1: event or rate) and its weight."""
    EARTH = _dir(region); p = EARTH / "targets" / f"{t}_obs.parquet"
    if t not in TARGETS or not p.exists():
        raise HTTPException(404, "no observations for this target")
    o = pd.read_parquet(p); tp = pd.read_parquet(EARTH / "tops.parquet").sort_values("top_tvdss").drop_duplicates(["wellbore", "name"])
    o = o.merge(tp[["wellbore", "name", "top_tvdss", "bot_tvdss", "x", "y"]].rename(columns={"name": "unit", "x": "px", "y": "py"}), on=["wellbore", "unit"], how="inner")
    o = o.dropna(subset=["top_tvdss"]); o["bot_tvdss"] = o.bot_tvdss.fillna(o.top_tvdss + 20)
    if units:
        o = o[o.unit.isin(units.split(","))]
    o = o.sort_values("w", ascending=False).head(limit)
    return {"build": _build(EARTH), "target": t, "n": int(len(o)), "x": _r(o.px, 2), "y": _r(o.py, 2), "top": _r(o.top_tvdss, 0), "base": _r(o.bot_tvdss, 0), "ev": _r(o.ev, 3), "w": _r(o.w, 2),
            "wellbore": o.wellbore.tolist(), "unit": o.unit.tolist()}


@router.get("/rpt")
def rpt(region: str = "pilot", limit: int = 8000):
    """Rock physics template (P11.1): model lines (friable sand, contact cement; brine, oil, gas), the region's FORCE samples on it, and the
    tests (this region's and pooled over all FORCE wells)."""
    EARTH = _dir(region); rp = EARTH / "rpt_report.json"
    if not rp.exists():
        raise HTTPException(404, "no rock physics here: no FORCE wells with shear logs in this region")
    rep = json.loads(rp.read_text()); d = pd.read_parquet(EARTH / "rpt_samples.parquet"); d = d.sample(min(limit, len(d)), random_state=0)
    pool = OUT / "earth" / "rpt_pooled.json"
    return {"template": rep.pop("template"), "report": rep, "pooled": json.loads(pool.read_text()) if pool.exists() else None,
            "points": {k: (d[k].round(4).tolist() if d[k].dtype.kind == "f" else d[k].tolist()) for k in ("wellbore", "unit", "ai", "vpvs", "phi", "T", "cement", "dai", "valid", "lith", "tvdss")}}


@router.get("/sensitivity")
def sensitivity():
    """P12.1: each untested constant set low and high, per built region; and the P12.2-P12.3 checks from the target reports."""
    out = []
    for r in REGIONS:
        d = _resolve(r)
        if not (d / "sensitivity.json").exists():
            continue
        rep = json.loads((d / "targets" / "report.json").read_text()) if (d / "targets" / "report.json").exists() else {}
        checks = {t: {"refit": rep[t].get("refit_check"), "range90": rep[t].get("range90_median")} for t in TARGETS if isinstance(rep.get(t), dict) and "refit_check" in rep[t]}
        out.append({"region": r, "title": REGIONS[r]["title"], **json.loads((d / "sensitivity.json").read_text()), "checks": checks})
    return out


@router.get("/jeham")
def jeham():
    """Nature's Plug (Jeham, MIT) inside the model (P13, LOG L090): Green Clay surface tested at his report sites, his formation-level
    window and nearest-well verdicts by region, his barrier cases with our Green Clay depth there."""
    p = OUT / "earth" / "jeham.json"
    if not p.exists():
        raise HTTPException(404, "not built: python -m se.earth.jeham")
    return json.loads(p.read_text())


@lru_cache(maxsize=1)
def _jeham_wells():
    from se.config import DATA

    e = json.loads((DATA / "natures_plug" / "engine_results.json").read_text()); ctl = [c for c in e["controls"] if c["assessed"]]
    wb = e["wellbores_left_to_plug"]
    return {"source": e["source"],
            "assessed": {"name": [c["name"] for c in ctl], "lat": [c["lat"] for c in ctl], "lon": [c["lon"] for c in ctl], "verdict": [c["verdict"] for c in ctl], "longest_m": [c["longest_m"] for c in ctl], "group": [c["group"] for c in ctl]},
            "inherited": {"name": [w["name"] for w in wb], "lat": [w["lat"] for w in wb], "lon": [w["lon"] for w in wb], "verdict": [w["log"] for w in wb], "from": [w["log_from"] for w in wb], "km": [w["log_km"] for w in wb]}}


@router.get("/jeham/wells")
def jeham_wells():
    """Jeham's log-level verdicts for the map (P13, LOG L092): assessed log wells (their own logs) and wellbores left to plug, which take the
    verdict of the nearest assessed log well within 10 km (his rule, shown as his result)."""
    return _jeham_wells()
