"""GPU worker: heavy jobs only. A gpuctl consumer in the cluster (scaled to 0, started by gpuproxy on the first request); runs fine on CPU too.
Jobs: map grids and the 3D estimate surfaces (both are cells x units distance matrices, the part the GPU speeds up about 10x, LOG L025).
"""
import os
import time

from fastapi import FastAPI, HTTPException

from se.api import scene
from se.api.state import State
from se.config import device
from se.jobs import map_job

app = FastAPI(title="subsurface-evidence worker", root_path=os.environ.get("ROOT_PATH", ""))
S: dict = {}


def st(target: str) -> State:
    if target not in S:
        S[target] = State(target)
    return S[target]


@app.get("/health")
def health():
    return {"ok": True, "device": device()}


@app.post("/run/map")
def run_map(p: dict):
    s = st(p.get("target", "green_clay"))
    out = map_job.run(s.layers["strat"], s.lab, p["formation"], float(p.get("res_deg", 0.02)), float(p.get("ell", 20.0)), float(p.get("k", 30.0)), bool(p.get("use_spatial", True)))
    if "error" in out:
        raise HTTPException(404, out["error"])
    return out


@app.post("/run/surfaces")
def run_surfaces(p: dict):
    s, t0 = st(p.get("target", "green_clay")), time.time()
    dev = device()
    out = [x for x in (scene.surface(s, f, float(p.get("lat_min", 0)), float(p.get("lat_max", 90)), dev=dev) for f in p["formations"]) if x]
    return {"surfaces": out, "device": dev, "seconds": round(time.time() - t0, 3)}
