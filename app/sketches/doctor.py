"""Data Doctor: do the sources agree? FactPages, the FORCE 2020 well logs and the Diskos report text, cross-checked.

Every app inherits its inputs' errors. For each FORCE 2020 well this compares the log file's position, depth range
and formation boundaries with FactPages' header and formation tops, and spots systematic offsets (a constant shift
the size of the kelly-bushing elevation means two depth references were mixed). For wellbores with report passages,
the model extracts the facts the reports state (total depth, water depth, KB, dates) and compares them too. Each
wellbore gets a trust score other apps can show next to a fact. Conflicts are questions for a person, not verdicts.
"""

import json
from functools import lru_cache
from statistics import median

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from common import DATA_DIR, ModelBusy, chat_json, load_json, norm, page, save_json, wellbore
from sketches import reports, wells

router = APIRouter(prefix="/doctor")
F = DATA_DIR / "force2020"
SUMMARY = F / "well_summary.parquet"
CACHE = DATA_DIR / "doctor" / "reports.json"
TOP_TOL = 20  # m
POS_TOL = 250  # m: ED50 versus WGS84 alone moves a point about 100-200 m in the North Sea


def unit(name) -> str:
    """One spelling for a unit name: FORCE writes ÅSGARD as AASGARD and RØDBY as ROEDBY."""
    if not isinstance(name, str):
        return ""
    s = name.upper().replace(".", "").replace("Å", "AA").replace("Ø", "OE").replace("Æ", "AE")
    return " ".join(s.split())


@lru_cache(maxsize=1)
def logs() -> pd.DataFrame:
    """One row per FORCE 2020 well and unit: first and last log depth of each group and formation."""
    if SUMMARY.exists():
        return pd.read_parquet(SUMMARY)
    cols = ["WELL", "DEPTH_MD", "X_LOC", "Y_LOC", "GROUP", "FORMATION"]
    df = pd.concat([pd.read_csv(F / f, sep=";", usecols=cols) for f in ("train.csv", "hidden_test.csv")])
    out = []
    for w, g in df.groupby("WELL"):
        base = {"well": w, "x": g.X_LOC.median(), "y": g.Y_LOC.median(), "log_top": g.DEPTH_MD.min(), "log_base": g.DEPTH_MD.max()}
        for level in ("GROUP", "FORMATION"):
            for u, h in g.dropna(subset=[level]).groupby(level):
                out.append({**base, "level": level, "unit": unit(u), "top": h.DEPTH_MD.min(), "base": h.DEPTH_MD.max()})
        out.append({**base, "level": "WELL", "unit": "", "top": None, "base": None})
    s = pd.DataFrame(out)
    s.to_parquet(SUMMARY, index=False)
    return s


def check(well: str) -> dict:
    s = logs()
    g = s[s.well == well]
    if g.empty:
        raise HTTPException(404, f"{well} is not in FORCE 2020")
    w = wellbore(well)
    head = g.iloc[0]
    issues, checks = [], 0
    if not w:
        return {"well": well, "matched": None, "issues": [{"kind": "name", "severity": "high", "text": f"{well} not found in FactPages"}], "score": 0, "tops": []}
    # position: FORCE X/Y against FactPages UTM (both ED50 UTM for most wells)
    checks += 1
    pos = None
    if w["east"] and w["north"] and head.x == head.x:
        pos = round(((head.x - w["east"]) ** 2 + (head.y - w["north"]) ** 2) ** 0.5)
        if pos > POS_TOL:
            issues.append({"kind": "position", "severity": "medium" if pos < 2000 else "high",
                           "text": f"log file position is {pos} m from FactPages (zone {w['zone']})"})
    # depth: logs must sit inside the drilled hole
    checks += 1
    if w["td"] and head.log_base > w["td"] + 10:
        issues.append({"kind": "depth", "severity": "high", "text": f"logs reach {head.log_base:.0f} m, below the FactPages total depth {w['td']:.0f} m"})
    elif w["td"] and head.log_base < w["td"] - 300:
        issues.append({"kind": "coverage", "severity": "low", "text": f"logs stop at {head.log_base:.0f} m, {w['td'] - head.log_base:.0f} m above total depth"})
    # tops: first log depth of each unit against the FactPages top
    fp = {(t["level"], unit(t["unit"])): t for t in wells.tops(w["name"])}
    rows_, diffs = [], []
    for r in g[g.level.isin(["GROUP", "FORMATION"])].itertuples():
        if r.top <= head.log_top + 1:  # the unit was already under way where logging began: its top is not in the logs
            continue
        t = fp.get((r.level, r.unit))
        if t is None or t["top"] is None:
            rows_.append({"level": r.level, "unit": r.unit, "log_top": round(r.top, 1), "fp_top": None, "diff": None})
            continue
        d = round(r.top - t["top"], 1)
        diffs.append(d)
        rows_.append({"level": r.level, "unit": r.unit, "log_top": round(r.top, 1), "fp_top": t["top"], "diff": d})
    checks += len(diffs)
    bad = [x for x in rows_ if x["diff"] is not None and abs(x["diff"]) > TOP_TOL]
    shift = median(diffs) if diffs else 0
    if diffs and abs(shift) > TOP_TOL and w["kb"] and abs(abs(shift) - w["kb"]) < 8:
        issues.append({"kind": "depth reference", "severity": "high",
                       "text": f"log tops sit {shift:+.0f} m from FactPages on median, about the KB elevation ({w['kb']:.0f} m): one source is below sea level, the other below KB"})
    elif diffs and abs(shift) > TOP_TOL:
        issues.append({"kind": "depth shift", "severity": "medium", "text": f"log tops sit {shift:+.0f} m from FactPages on median"})
    for x in bad:
        if abs(x["diff"] - shift) > TOP_TOL:
            issues.append({"kind": "top", "severity": "medium" if abs(x["diff"]) < 100 else "high",
                           "text": f"{x['unit']}: log top {x['log_top']} m, FactPages {x['fp_top']} m ({x['diff']:+} m)"})
    missing = [x["unit"] for x in rows_ if x["fp_top"] is None and x["level"] == "FORMATION"]
    if missing:
        issues.append({"kind": "unmatched unit", "severity": "low", "text": f"in the logs but not in FactPages tops: {', '.join(missing[:6])}"})
    penalty = sum({"high": 1, "medium": 0.6, "low": 0.2}[i["severity"]] for i in issues)
    score = max(0, round(100 * (1 - penalty / max(checks, 1))))
    return {"well": well, "matched": w["name"], "position_m": pos, "kb": w["kb"], "td": w["td"], "log_base": float(head.log_base),
            "median_shift": shift, "tops": rows_, "issues": issues, "score": score}


@lru_cache(maxsize=1)
def audit() -> list[dict]:
    out = []
    for well in sorted(logs().well.unique()):
        try:
            r = check(well)
        except HTTPException:
            continue
        out.append({k: r.get(k) for k in ("well", "matched", "score", "position_m", "median_shift")} | {"issues": len(r["issues"]), "kinds": sorted({i["kind"] for i in r["issues"]}), "worst": max((i["severity"] for i in r["issues"]), key=lambda s: {"low": 0, "medium": 1, "high": 2}[s], default="none")})
    return out


@router.get("")
def slash():
    return RedirectResponse("doctor/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("doctor.html")


@router.get("/api/audit")
def audit_all():
    a = audit()
    kinds: dict[str, int] = {}
    for x in a:
        for k in x["kinds"]:
            kinds[k] = kinds.get(k, 0) + 1
    covered = sorted({w for ws in reports.corpus()[0].wellbores for w in ws})
    return {"wells": a, "kinds": kinds, "clean": sum(1 for x in a if not x["issues"]), "report_wells": covered[:400],
            "report_wellbores": len(covered)}


@router.get("/api/well/{name:path}")
def well(name: str):
    return check(name)


FACTS = {"type": "object", "properties": {"facts": {"type": "array", "items": {"type": "object", "properties": {
    "field": {"type": "string", "enum": ["total_depth_m", "water_depth_m", "kb_elevation_m", "spud_date", "completion_date", "formation_at_td", "content"]},
    "value": {"type": "string"}, "source": {"type": "string"}, "quote": {"type": "string"}},
    "required": ["field", "value", "source", "quote"]}}}, "required": ["facts"]}
FP_FIELD = {"total_depth_m": "td", "water_depth_m": "water_depth", "kb_elevation_m": "kb", "spud_date": "entry",
            "completion_date": "completion", "formation_at_td": "formation_td", "content": "content"}


def same(field: str, a, b) -> bool | None:
    if a in (None, "") or b in (None, ""):
        return None
    if field.endswith("_m"):
        try:
            return abs(float(str(a).split()[0].replace(",", "")) - float(b)) <= 5
        except ValueError:
            return None
    if field.endswith("_date"):
        return str(b)[:7] in str(a) or str(a)[:7] == str(b)[:7]
    return str(b).upper().replace(" FM", "") in str(a).upper() or str(a).upper() in str(b).upper()


@router.post("/api/reports/{name:path}")
async def report_check(name: str):
    """Facts the Diskos passages state about a wellbore, against FactPages (cached)."""
    w = wellbore(name)
    if not w:
        raise HTTPException(404, "unknown wellbore")
    cache = load_json(CACHE)
    key = norm(name)
    if key not in cache:
        found = reports.for_wellbore(name, "total depth water depth kelly bushing spudded completed TD formation", k=8)
        if not found:
            raise HTTPException(404, "no report passages for this wellbore")
        try:
            ext = await chat_json(
                [{"role": "system", "content": f"Extract what these report passages state about wellbore {w['name']} itself "
                  "(not other wells): total depth (MD, metres), water depth, KB elevation, spud and completion dates "
                  "(YYYY-MM-DD), formation at TD, content (oil, gas, dry). source is the passage tag [S#]. Skip facts not stated."},
                 {"role": "user", "content": "\n\n".join(f"[{p['ref']}] ({p['document']}) {p['text'][:2000]}" for p in found)}],
                FACTS, max_tokens=1200)
        except ModelBusy as e:
            raise HTTPException(503, f"the model is busy: {e}")
        cache[key] = {"facts": ext["facts"], "sources": [{k: p[k] for k in ("ref", "document", "chunk_id")} for p in found]}
        save_json(CACHE, cache)
    out = []
    for f in cache[key]["facts"]:
        if str(f.get("value", "")).strip().lower() in ("", "none", "not stated", "n/a", "unknown"):
            continue  # the passages did not state it: nothing to compare
        fp = w.get(FP_FIELD.get(f["field"], ""))
        out.append({**f, "factpages": str(fp) if fp is not None else None, "agree": same(f["field"], f["value"], fp)})
    return {"wellbore": w["name"], "facts": out, "sources": cache[key]["sources"]}
