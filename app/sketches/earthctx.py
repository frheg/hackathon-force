"""Earth-model evidence for Strata Desk: what the subsurface-evidence model says, how sure it is, which tested rules bear on it.

Read from the model's artefacts on disk (data/subsurface-evidence/earth/<region>, the rules file in the repo); the app mounts the repo,
so no call to the other service is needed. Each entry is an excerpt with a reference (M:...) the answer can cite, like the report (S#)
and FactPages (F:...) excerpts. These are model outputs and tested assumptions, not observations, and the prompt says so.
"""
import json
import re
from functools import lru_cache

import numpy as np
import pandas as pd

from common import DATA_DIR as DATA

EARTH = DATA / "subsurface-evidence" / "earth"
NAMES = {"pilot": "Northern North Sea (Horda Platform)", "north_sea_south": "Southern North Sea", "norwegian_sea": "Norwegian Sea", "barents": "Barents Sea"}
name = lambda r: NAMES.get(r, r.replace("_", " "))
GENERIC = {"INTRA", "UPPER", "LOWER", "MIDDLE", "UNDIFFERENTIATED", "UNKNOWN"}
TARGET_RULES = {"hydrocarbons": ["R-SEAL", "R-DRAUPNE", "R-MATURE", "R-MATURE-MAX", "R-CHARGE", "R-TRAP"], "reservoir": ["R-ATHY", "R-DPHI", "R-QTZ", "R-UPLIFT"],
                "overpressure": ["R-HYD"], "co2_storage": ["R-CO2", "R-SEAL", "R-GEO", "R-HYD", "R-LEGACY", "R-SEABEDT", "R-SALT"], "sandy_delta": ["R-BRENT"]}
TARGET_RULES["oil"] = TARGET_RULES["gas"] = TARGET_RULES["chance_of_success"] = TARGET_RULES["hydrocarbons"]
METHOD = {
    "published": "Each target is a binary event observed in wells (per unit). The published number per cell is the simplest form that is not worse on "
                 "held-out wells: the model, the unit's own rate (unit prior) or the region's base rate. A model is published only if it beats both on "
                 "held-out 40 km blocks (features chosen inside each training fold) and also has skill forward in time (trained on wells completed "
                 "before 2005, scored on later wells).",
    "probability": "P(event | a well is drilled here): training wells are not a random sample (exploration wells target structures), so between wells "
                   "and in undrilled settings the number is an extrapolation. The 90 percent range comes from correlated Monte Carlo draws of the inputs.",
    "support": "Support (0-1) is how much data stands behind the cell: kernel-weighted observations of the same unit nearby, distance to the nearest one, "
               "and the target's held-out skill. Low support means the number is mostly the unit or regional average.",
}


def _json(p):
    return json.loads(p.read_text()) if p.exists() else None


@lru_cache(maxsize=8)
def _region(region: str) -> dict:
    d = EARTH / region
    if not (d / "targets" / "report.json").exists():
        return {}
    rules = {r["id"]: r for r in (_json(d / "earth_rules_report.json") or [])}
    cells = pd.read_parquet(d / "targets" / "cells.parquet")
    wells = pd.read_parquet(d / "wells.parquet") if (d / "wells.parquet").exists() else pd.DataFrame()
    return {"report": _json(d / "targets" / "report.json"), "rules": rules, "cells": cells, "wells": wells, "capacity": _json(d / "targets" / "co2_capacity.json"),
            "factors": dict(np.load(d / "factors.npz")) if (d / "factors.npz").exists() else None, "dir": d}


def _num(v, d=3):
    return round(float(v), d) if v is not None and np.isfinite(float(v)) else None


def method(region: str, target: str) -> dict | None:
    R = _region(region); e = (R.get("report") or {}).get(target)
    if not e:
        return None
    if target in ("co2_storage", "chance_of_success"):
        text = f"{target} is a composite, not calibrated: {e.get('composite', {}).get('terms')}. {e.get('why', '')}."
        if e.get("test"):
            text += f" Held-out check against hydrocarbon observations (deviance gain over the base rate, 0 = none): {e['test']}."
        if target == "co2_storage" and R.get("capacity"):
            c = R["capacity"]; text += f" Region capacity P10/P50/P90 {c['total_mt']} Mt; atlas comparison: {[(a['aquifer'], a['atlas_capacity_gt'], a['our_capacity_at_atlas_E_gt']) for a in c['atlas']]} (atlas Gt, ours at the atlas efficiency, Gt); {c['caveat']}."
    else:
        tt = e.get("time_test") or {}
        text = (f"{target} in {name(region)}: published as {e.get('published')} (family {e.get('family', 'logistic')}); base rate {e.get('base_rate')} from {e.get('rows')} "
                f"unit observations in {e.get('wells')} wells. Held-out deviance gain over the base rate: nested {e.get('gain_nested')} (features chosen on the scored "
                f"folds: {e.get('gain_selected_on_same_folds')}); unit prior alone {e.get('gain_unit_prior_vs_base')}; forward in time {tt.get('gain_selected_features')} "
                f"on {tt.get('test_wells')} later wells. Inputs: {e.get('features')}. {('Model rejected: ' + e['model_rejected'] + '.') if e.get('model_rejected') else ''}")
    return {"ref": f"M:method-{target}", "kind": "model", "document": f"Earth model · {name(region)} · how {target} is computed and tested", "page": None,
            "text": text + " " + METHOD["published"] + " " + METHOD["probability"] + " " + METHOD["support"], "excerpted": False}


def cell(region: str, target: str, k: int) -> dict | None:
    R = _region(region)
    if not R or not 0 <= k < len(R["cells"]):
        return None
    c = R["cells"].iloc[k]; p = R["dir"] / "targets" / f"{target}.npz"; d = dict(np.load(p)) if p.exists() else {}
    t = [f"Unit {c.unit} (group {c.group}), {c.top:.0f}-{c.base:.0f} m TVDSS ({c.thick:.0f} m, {c.zb:.0f} m below the seabed), column at {c.x:.0f}, {c.y:.0f} km (EPSG:3035)."]
    if d:
        t.append(f"{target}: p {_num(d['p'][k])} (90 percent range {_num(d['p05'][k])}-{_num(d['p95'][k])}), support {_num(d['support'][k], 2)}.")
        if "limit" in d:
            el = ["reservoir", "seal", "charge", "trap"]; t.append("Elements: " + ", ".join(f"{e} {_num(d[e][k])}" for e in el if e in d) + f"; limiting: {el[int(d['limit'][k])]}.")
    for col, lab in (("T_C", "temperature C"), ("seal_m", "shale within 300 m above, m"), ("sand", "sand share")):
        if col in c and pd.notna(c[col]):
            t.append(f"{lab}: {_num(c[col], 2)}.")
    f = R.get("factors")
    if f is not None:
        i = int(np.abs(f["x"] - c.x).argmin()); j = int(np.abs(f["y"] - c.y).argmin()); li = int(c.label)
        t.append(f"Petroleum system: nearest mature source {f['kit_oil'][j, i]:.0f} km ({f['kit_max'][j, i]:.0f} km at maximum burial); p(source below in oil window) "
                 f"{f['p_oil'][j, i]:.2f}; nearest mapped fault {f['fault_km'][j, i]:.0f} km; on a structural high: {bool(f['on_high'][j, i])}; closure on the unit top "
                 f"{f['closure'][li, j, i]:.0f} m; migrating oil reaches it with p {f['p_charge'][li, j, i]:.2f}." if "p_charge" in f else "")
    return {"ref": "M:cell", "kind": "model", "document": f"Earth model · {name(region)} · selected cell {k}", "page": None, "text": " ".join(x for x in t if x), "excerpted": False}


def rules(region: str, target: str) -> list[dict]:
    R = _region(region); out = []
    for rid in TARGET_RULES.get(target, []):
        r = R.get("rules", {}).get(rid)
        if not r:
            continue
        test = {k: v for k, v in r["test"].items() if k not in ("why",)}
        out.append({"ref": f"M:{rid}", "kind": "rule", "document": f"Rule {rid} ({r['status']}) · tested on {name(region)} wells", "page": None,
                    "text": f"{r['statement']} Test verdict in {name(region)}: {test.get('verdict')}. Numbers: {json.dumps({k: v for k, v in test.items() if k != 'verdict'})[:500]}. "
                            f"Use: {r.get('use')}. Guard: {r.get('guard')}. Sources: {'; '.join(s['says'] for s in r['sources'])}", "excerpted": False})
    return out


def well(region: str, wellbore: str) -> dict | None:
    w = _region(region).get("wells")
    if w is None or w.empty or wellbore not in set(w.wellbore):
        return None
    r = w.set_index("wellbore").loc[wellbore]
    how = {"force": "true path from FORCE 2020 logs", "factpages": "FactPages TVD at TD with an inferred path", "estimated": "no TVD in FactPages: estimated",
           "vertical": "no TVD: assumed vertical (least reliable)"}.get(r.get("source"), r.get("source"))
    tvd = f"TVD at TD {r.tvd_est:.0f} m below the rig floor (sd {r.tvd_sd:.0f} m, by {r.tvd_how})" if "tvd_est" in r and pd.notna(r.tvd_est) else "TVD at TD unknown"
    return {"ref": f"M:well-{re.sub(r'[^A-Za-z0-9]', '', wellbore)}", "kind": "model", "document": f"Earth model frame · {wellbore}", "page": None,
            "text": f"{wellbore}: {r.kind} wellbore, rig floor {r.kb} m above sea level, water depth {r.wd} m, total depth {r.td} m measured along the hole (MD); {tvd}. "
                    f"Depth source in the model: {how}. MD is the length along the hole; TVD and TVDSS are vertical depths (below the rig floor, below sea level).",
            "excerpted": False}


def unit(region: str, target: str, name: str) -> dict | None:
    R = _region(region); p = R.get("dir") and R["dir"] / "targets" / f"{target}_obs.parquet"
    if not p or not p.exists():
        return None
    o = pd.read_parquet(p); u = o[o.unit == name]
    if u.empty:
        return None
    c = R["cells"]; cu = c[c.unit == name]
    rate = float(np.average(u.ev, weights=u.w))
    return {"ref": f"M:unit-{re.sub(r'[^A-Za-z0-9]', '', name)}", "kind": "model", "document": f"Earth model · {name(region)} · observations of {name}", "page": None,
            "text": f"{name} in {NAMES.get(region, region)}: {target} observed in {len(u)} unit observations from {u.wellbore.nunique()} wells, weighted rate {rate:.3f} "
                    f"(region base rate {R['report'][target].get('base_rate') if target in R['report'] else None}). The unit fills {len(cu)} model cells, "
                    f"{cu.top.median():.0f} m TVDSS median top, {cu.thick.median():.0f} m median thickness.", "excerpted": False}


def evidence(region: str, target: str, cell_id: int | None, wellbores: list[str], question: str) -> list[dict]:
    """All earth-model excerpts for a question: method and skill of the target, the selected cell, rules, named wells and units."""
    if not region or not _region(region):
        return []
    out = [x for x in (method(region, target), cell(region, target, cell_id) if cell_id is not None else None) if x]
    out += rules(region, target)
    out += [x for x in (well(region, w) for w in wellbores[:2]) if x]
    names = set(_region(region)["cells"].unit)
    key = lambda n: n.split(" ")[0]  # "UTSIRA FM" -> "UTSIRA"; generic first words are not names
    for n in [n for n in names if len(key(n)) >= 4 and key(n) not in GENERIC and re.search(r"\b" + re.escape(key(n)) + r"\b", question, re.I)][:2]:
        x = unit(region, target, n)
        if x:
            out.append(x)
    return out
