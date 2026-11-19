"""Saved targets: OUT/targets/<id>/{spec.json, units.parquet, results.json, oof.parquet}. green_clay is built in and lives at the OUT root."""
import json
import os
import shutil
import time
from pathlib import Path

import pandas as pd

from se.config import OUT
from se.targets.builder import build, spec_id
from se.validate import cv

ROOT = Path(os.environ.get("SE_TARGETS", OUT / "targets"))  # the pod mounts the repo read-only: it points this at a writable directory
GREEN = {"id": "green_clay", "title": "Green clay in described clay rows", "mode": "interval", "builtin": True,
         "words": {"rows": "described clay rows", "hit": "name a green mineral", "short": "green", "unit": "well x formation interval"}}

# Ready-made recipes (user can edit them in the builder). Reasoning for each is in LOG L029.
PRESETS = [
    {"title": "Hydrocarbons found by a wildcat well", "mode": "well", "table": "wellbore_exploration", "population": ["wlbPurpose|eq|WILDCAT"],
     "success": ["wlbContent|in|OIL,GAS,OIL/GAS,GAS/CONDENSATE,OIL/GAS/CONDENSATE"], "group": "wlbMainArea",
     "words": {"rows": "wildcat wells", "hit": "found oil or gas", "short": "discovery", "unit": "wellbore"}},
    {"title": "DST flowed oil", "mode": "interval", "table": "wellbore_dst", "population": [], "success": ["wlbDstOilProd|gt|0"],
     "words": {"rows": "drill-stem tests", "hit": "flowed oil", "short": "oil flow", "unit": "well x formation interval"}},
    {"title": "Heavy mud (> 1.6 sg) in a formation", "mode": "interval", "table": "wellbore_mud", "population": [], "success": ["wlbMudWeightAtMD|gt|1.6"],
     "words": {"rows": "mud measurements", "hit": "needed mud heavier than 1.6 sg", "short": "heavy mud", "unit": "well x formation interval"}},
]


def path(tid: str):
    return ROOT / tid


def words(spec: dict) -> dict:
    return spec.get("words") or {"rows": "trials", "hit": "succeeded", "short": "success", "unit": "unit"}


def evaluate(spec: dict) -> dict:
    """Build the unit table, validate it, save everything. Returns the saved spec with a summary."""
    spec = {**spec, "id": spec_id(spec)}
    d = path(spec["id"])
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    u = build(spec)
    lab = u[u.label >= 0]
    if len(lab) < 200 or lab.n_green.sum() < 20 or lab.wellbore.nunique() < 40:
        shutil.rmtree(d, ignore_errors=True)
        raise ValueError(f"too little data to validate: {len(lab)} labelled units, {int(lab.n_green.sum())} successes, {lab.wellbore.nunique()} wells (need 200, 20, 40)")
    u.to_parquet(d / "units.parquet")
    bins = [1, 2, 3, 5, 8, 13, 26, 61, 10**9] if spec["mode"] == "interval" else [1, 2]
    r = cv.run(u, d, quick=True, name=f"share of {words(spec)['rows']} that {words(spec)['hit']}", cov_bins=bins)
    spec["summary"] = {"units": r["data"]["labelled"], "wells": r["data"]["wellbores_labelled"], "trials": r["data"]["rows"], "successes": r["data"]["green_rows"], "base_rate": r["data"]["base_rate"],
                       "gain_formation": r["delta"]["strat_over_constant"], "gain_spatial": r["delta"]["spatial_over_strat"], "seconds": round(time.time() - t0)}
    spec["built"] = time.strftime("%Y-%m-%d %H:%M")
    (d / "spec.json").write_text(json.dumps(spec, indent=1, default=float))
    return spec


def saved() -> list:
    return [json.loads(p.read_text()) for p in sorted(ROOT.glob("*/spec.json"))] if ROOT.exists() else []


def remove(tid: str):
    if tid == "green_clay":
        raise ValueError("the built-in target cannot be removed")
    shutil.rmtree(path(tid), ignore_errors=True)
