"""GPU worker: heavy jobs only. A gpuctl consumer in the cluster (scaled to 0, started by gpuproxy on the first request); runs fine on CPU too."""
import os

from fastapi import FastAPI, HTTPException

from se.api.state import State
from se.jobs import map_job

app = FastAPI(title="subsurface-evidence worker", root_path=os.environ.get("ROOT_PATH", ""))
S: State | None = None


@app.get("/health")
def health():
    from se.config import device

    return {"ok": True, "device": device()}


@app.post("/run/map")
def run_map(p: dict):
    global S
    S = S or State()
    out = map_job.run(S.layers["strat"], S.lab, p["formation"], float(p.get("res_deg", 0.02)), float(p.get("ell", 20.0)), float(p.get("k", 30.0)), bool(p.get("use_spatial", True)))
    if "error" in out:
        raise HTTPException(404, out["error"])
    return out
