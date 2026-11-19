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



def _writable() -> Path:
    """First writable of: $SE_TARGETS, the repo data dir, $HOME/se-targets. The pod mounts the repo read-only, so there it falls to the persistent cache."""
    for d in ([Path(os.environ["SE_TARGETS"])] if os.environ.get("SE_TARGETS") else []) + [OUT / "targets", Path(os.environ.get("HOME", "/tmp")) / "se-targets"]:
        try:
            d.mkdir(parents=True, exist_ok=True)
            if os.access(d, os.W_OK):
                return d
        except OSError:
            continue
    raise OSError("no writable directory for saved targets")


ROOT = _writable()  # new targets go here
ROOTS = list(dict.fromkeys([ROOT, OUT / "targets"]))  # saved ones are read from here and the repo's
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
    """Where a target lives: the writable root first, then the read-only repo copy."""
    return next((r / tid for r in ROOTS if (r / tid / "spec.json").exists()), ROOT / tid)


def words(spec: dict) -> dict:
    return spec.get("words") or {"rows": "trials", "hit": "succeeded", "short": "success", "unit": "unit"}


def evaluate(spec: dict) -> dict:
    """Build the unit table, validate it, save everything. Returns the saved spec with a summary."""
    spec = {**spec, "id": spec_id(spec)}
    d = ROOT / spec["id"]  # always the writable copy
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
    seen = {}
    for r in ROOTS:  # the writable copy wins over the repo copy of the same id
        for p in sorted(r.glob("*/spec.json")) if r.exists() else []:
            seen.setdefault(p.parent.name, json.loads(p.read_text()))
    return sorted(seen.values(), key=lambda t: t.get("built", ""))


def remove(tid: str):
    if tid == "green_clay":
        raise ValueError("the built-in target cannot be removed")
    for r in ROOTS:
        try:
            shutil.rmtree(r / tid)
        except FileNotFoundError:
            pass
        except OSError as e:
            raise ValueError(f"cannot delete {tid}: {r} is read-only here")
