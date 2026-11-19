"""Backend API. Read-only except /api/jobs. Everything the UI shows comes from here, with the numbers it was built from (hide nothing)."""
import os
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from se.api.state import State
from se.config import LOG_MD, PROJECT, TARGET, WORKER_URL
from se.infer.combine import ORDER
from se.api import explore, scene, targets_api
from se.jobs import map_job

app = FastAPI(title="subsurface-evidence", root_path=os.environ.get("ROOT_PATH", ""), docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"])
app.include_router(explore.router)
app.include_router(targets_api.router)
S: dict = {}


def st(target: str = "green_clay") -> State:
    if target not in S:
        S[target] = State(target)
    return S[target]


def clean(o):
    """numpy scalars and NaN -> plain JSON values."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else float(o)
    return o


def layers_arg(layers: str | None, target: str = "green_clay") -> tuple:
    s = st(target)
    use = tuple(x for x in (layers.split(",") if layers else s.default_on) if x in ORDER)
    return use or ("strat",)


@app.on_event("startup")
def _warm():
    st()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta(target: str = "green_clay"):
    s = st(target)
    r = s.results
    return {"target": s.spec.get("id", TARGET["name"]), "title": s.spec["title"], "words": s.words, "mode": s.spec["mode"], "spec": s.spec if target != "green_clay" else None,
            "target_text": ("share of described CLAY rows that name a green mineral (glauconite, green clay, chlorite, nontronite, celadonite): a REPORTED share, not true presence" if target == "green_clay"
                            else f"share of {s.words['rows']} that {s.words['hit']} (FactPages), per {s.words['unit']}"),
            "data": r["data"], "built": r["built"], "validation_seconds": r["seconds"], "device": s.device, "worker": bool(WORKER_URL), "layers_default_on": s.default_on, "status": s.status,
            "block_km": r["block_km"], "folds": r["folds"], "loaded_seconds": s.loaded_seconds}


@app.get("/api/layers")
def layers(target: str = "green_clay"):
    return clean(st(target).layer_info())


@app.get("/api/formations")
def formations(target: str = "green_clay"):
    s = st(target)
    g = s.lab.groupby("name").agg(units=("label", "size"), wells=("wellbore", "nunique"), rows=("coverage", "sum"), green=("n_green", "sum")).reset_index()
    g["rate"] = g.green / g.rows
    return g.sort_values("rows", ascending=False).round(4).to_dict("records")


@app.get("/api/units")
def units(formation: str | None = None, q: str | None = None, min_rows: int = 3, labelled: bool = True, layers_: str | None = Query(None, alias="layers"), sort: str = "rate", limit: int = 300, target: str = "green_clay"):
    s = st(target)
    u = s.lab if labelled else s.units
    if formation:
        u = u[u.name == formation]
    if q:
        u = u[u.unit.str.contains(q, case=False, regex=False)]
    u = u[u.coverage >= (min_rows if target == "green_clay" else 1)] if labelled else u
    if u.empty:
        return []
    c = s.rate(u, layers_arg(layers_, target))
    d = u[["unit", "wellbore", "name", "level", "lat", "lon", "top", "bot", "coverage", "n_green", "label"]].join(c[["rate", "strat", "spatial", "logs"]])
    d["observed"] = d.n_green / d.coverage.where(d.coverage > 0)
    d = d.sort_values({"rate": "rate", "observed": "observed", "rows": "coverage"}.get(sort, "rate"), ascending=False).head(limit)
    return d.round(4).replace({np.nan: None}).to_dict("records")


@app.get("/api/unit")
def unit(id: str, layers_: str | None = Query(None, alias="layers"), target: str = "green_clay"):
    s = st(target)
    m = s.units[s.units.unit == id]
    if m.empty:
        raise HTTPException(404, "no such unit")
    row = m.iloc[0]
    e = s.explain(row, layers_arg(layers_, target))
    o = s.oof[s.oof.unit == id]
    return clean({"unit": id, "wellbore": row.wellbore, "formation": row["name"], "level": row.level, "lat": row.lat, "lon": row.lon, "top": row.top, "bot": row.bot, "thickness": row.thickness,
                  "described_clay_rows": int(row.coverage), "green_rows": int(row.n_green), "observed_rate": float(row.n_green / row.coverage) if row.coverage else None,
                  "labelled": bool(row.label >= 0), "estimate": e, "validation_estimate": (float(o.p_full.iloc[0]) if len(o) else None),
                  "logs": {c: (None if pd.isna(row[c]) else round(float(row[c]), 3)) for c in ("GR", "RHOB", "NPHI", "PEF", "DTC", "RDEP", "DNSEP", "n_log")}})


def _run_map(formation, res, ell, k, spatial, force_cpu=False, target="green_clay"):
    s = st(target)
    params = {"formation": formation, "res_deg": res, "ell": ell, "k": k, "use_spatial": spatial, "target": target}
    out = None
    if WORKER_URL and not force_cpu:
        try:  # the proxy wakes the GPU worker (cold start, minutes the first time); a busy GPU or an error falls back to the CPU
            r = httpx.post(f"{WORKER_URL}/run/map", json=params, timeout=1800)
            out = r.json() if r.status_code == 200 else None
            fallback = None if out else f"worker answered {r.status_code}: {r.text[:120]}"
        except httpx.HTTPError as e:
            fallback = f"worker unreachable: {type(e).__name__}"
        if out is None:
            out = map_job.run(s.layers["strat"], s.lab, formation, res, ell, k, spatial, dev="cpu")
            out["fallback"] = fallback
    else:
        out = map_job.run(s.layers["strat"], s.lab, formation, res, ell, k, spatial, dev="cpu" if force_cpu else None)
    if "error" in out:
        raise HTTPException(404, out["error"])
    return out


@app.get("/api/map")
def map_(formation: str, res: float = 0.2, spatial: bool = True, layers_: str | None = Query(None, alias="layers"), target: str = "green_clay"):
    """Coarse map, computed here (CPU or cuda if present). Rate is calibrated with the same calibrator as the units."""
    s = st(target)
    use = layers_arg(layers_, target)
    out = _run_map(formation, res, s.layers["spatial"].ell, s.layers["spatial"].k, spatial and "spatial" in use, force_cpu=False if not WORKER_URL else True, target=target)
    raw = np.array(out["logit"])
    out["rate"] = s.platt(("strat", "spatial") if spatial and "spatial" in use else ("strat",))(raw.ravel()).reshape(raw.shape).tolist()
    del out["logit"]
    u = s.lab[s.lab.name == formation]
    out["points"] = [{"lat": a, "lon": b, "rows": c, "green": g, "unit": n} for a, b, c, g, n in zip(u.lat, u.lon, u.coverage, u.n_green, u.unit)][:3000]
    return out


@app.post("/api/jobs/map")
def job_map(formation: str, res: float = 0.02, spatial: bool = True, target: str = "green_clay"):
    """Fine map. With WORKER_URL set it goes to the GPU worker (the proxy starts it); else it runs here."""
    s = st(target)
    out = _run_map(formation, res, s.layers["spatial"].ell, s.layers["spatial"].k, spatial, target=target)
    raw = np.array(out["logit"])
    out["rate"] = s.platt(("strat", "spatial") if spatial else ("strat",))(raw.ravel()).reshape(raw.shape).tolist()
    del out["logit"]
    out["via"] = "this process (CPU fallback: " + out["fallback"] + ")" if out.get("fallback") else ("worker" if WORKER_URL else "this process")
    return out


@app.get("/api/validation")
def validation(target: str = "green_clay"):
    return clean(st(target).results)


@app.get("/api/kb")
def kb_(target: str = "green_clay"):
    return clean(st(target).kb)


@app.get("/api/contradictions")
def contradictions(target: str = "green_clay"):
    return clean(st(target).results["contradictions"])


@app.get("/api/log")
def log():
    return {"markdown": Path(LOG_MD).read_text()}


@app.get("/api/docs-list")
def docs_list():
    out = []
    for p in sorted((PROJECT / "docs").glob("*.md")):
        out.append({"name": p.stem, "markdown": p.read_text()})
    return out


LAST = {}  # the last heavy job and where it ran, shown in the UI header (hide nothing)


def estimate_surfaces(s, fs, lat_min, lat_max, target):
    """Estimate surfaces for the 3D scene: on the GPU worker when there is one (the proxy wakes it), else here."""
    t0, via = time.time(), "this process (CPU)"
    out = None
    if WORKER_URL:
        try:
            r = httpx.post(f"{WORKER_URL}/run/surfaces", json={"formations": fs, "lat_min": lat_min, "lat_max": lat_max, "target": target}, timeout=1800)
            if r.status_code == 200:
                j = r.json()
                out, via = j["surfaces"], f"GPU worker ({j['device']})"
        except httpx.HTTPError:
            pass
    if out is None:
        out = [x for x in (scene.surface(s, f, lat_min, lat_max) for f in fs) if x]
    LAST.update({"job": "3D surfaces", "via": via, "seconds": round(time.time() - t0, 2)})
    return out


@app.get("/api/last_job")
def last_job():
    return LAST


@app.get("/api/formations3d")
def formations3d(target: str = "green_clay"):
    s = st(target)
    g = s.lab.groupby("name").agg(units=("label", "size"), wells=("wellbore", "nunique")).reset_index()
    return g[g.units >= 8].sort_values("units", ascending=False).to_dict("records")


@app.get("/api/scene")
def scene_(formations: str, surfaces: bool = True, lat_min: float = 0.0, lat_max: float = 90.0, target: str = "green_clay"):
    """Wells (segments per unit) and smoothed surfaces for the chosen formations, plus the hotspots found in them."""
    s = st(target)
    fs = [f for f in formations.split(",") if f][:8]
    u = s.units[s.units.name.isin(fs) & s.units.lat.between(lat_min, lat_max)]
    if not hasattr(s, "_hot"):
        s._hot = scene.hotspots(s)
    return clean({"formations": fs, "wells": scene.wells(u), "surfaces": estimate_surfaces(s, fs, lat_min, lat_max, target) if surfaces else [],
                  "hotspots": [h for h in s._hot if h["formation"] in fs and lat_min <= h["lat"] <= lat_max], "frame": {"lat0": scene.LAT0, "lon0": scene.LON0}, "units_total": int(len(u)), "units_shown": int(min(len(u), 4000))})


@app.get("/api/hotspots")
def hotspots_(target: str = "green_clay"):
    s = st(target)
    if not hasattr(s, "_hot"):
        s._hot = scene.hotspots(s)
    return clean(s._hot)
