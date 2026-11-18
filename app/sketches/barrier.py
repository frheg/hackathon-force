"""Barrier Ledger: legacy wells around a CO2 storage site (or any area), screened for leakage risk, with the facts
a P&A or CCS engineer needs and the gaps that block a decision.

About 2,900 NCS wellbores await permanent plugging at NOK 50M to over 1bn each, the state paying 78 %; every relevant
legacy well near a CO2 store needs a risk assessment, and Emmel et al. (2025) found that published screening methods
classify the same Norwegian wells differently, with no machine-readable P&A database to settle it. This lays the
facts side by side (penetration of reservoir and seal, casing across the seal, abandonment date and status), runs
three screening schemes, flags where they disagree and which missing fact drives it, and on request extracts plugs
and cement from the well's history and reports, cited. Candidate barriers only: NORSOK D-010 tables decide.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from common import ModelBusy, chat, chat_json, clean, nearby, page, rows, wellbore
from sketches import reports, wells

router = APIRouter(prefix="/barrier")
SITES = {
    "northern-lights": {"name": "Northern Lights (Aurora, Eos 31/5-7)", "center": "31/5-7", "radius": 12,
                        "reservoir": ["JOHANSEN FM", "COOK FM"], "seal": ["DRAKE FM"]},
    "smeaheia": {"name": "Smeaheia (32/4-1)", "center": "32/4-1", "radius": 12,
                 "reservoir": ["SOGNEFJORD FM"], "seal": ["DRAUPNE FM"]},
}
OPEN = {"SUSPENDED", "CLOSED", "JUNKED", "BLOWOUT", None}
LEVEL = {"low": 0, "medium": 1, "high": 2, "unknown": 3}


def dates(name: str) -> dict:
    r = rows(
        "select wlbPluggedAbandonDate as pa, wlbPluggedDate as plugged from wellbore_exploration where wlbWellboreName = ? "
        "union all select wlbPluggedAbandonDate, wlbPluggedDate from wellbore_development where wlbWellboreName = ?",
        name, name,
    )
    return clean(r[0]) if r else {"pa": None, "plugged": None}


def assess(w: dict, reservoir: list[str], seal: list[str], res_depth: float | None) -> dict:
    tops = wells.tops(w["name"])
    names = {t["unit"] for t in tops}
    seal_top = min((t["top"] for t in tops if t["unit"] in seal and t["top"] is not None), default=None)
    seal_base = max((t["base"] for t in tops if t["unit"] in seal and t["base"] is not None), default=None)
    res_top = min((t["top"] for t in tops if t["unit"] in reservoir and t["top"] is not None), default=None)
    casing = wells.casing(w["name"])
    deepest = max((c["depth"] for c in casing if c["depth"]), default=None)
    d = dates(w["name"])
    year = int(str(d["pa"] or d["plugged"] or w["completion"] or "0")[:4] or 0) or None
    if tops:
        penetrates_res = bool(set(reservoir) & names)
        penetrates_seal = bool(set(seal) & names)
        estimated = False
    else:  # no tops (most development wells): compare total depth with the reservoir depth at the site well
        deep = w["td"] is not None and res_depth is not None and w["td"] >= res_depth
        penetrates_res = penetrates_seal = deep if w["td"] is not None and res_depth is not None else None
        estimated = True
    km_ = w.get("km")
    facts = {
        "penetrates_reservoir": penetrates_res,
        "penetrates_seal": penetrates_seal,
        "penetration_estimated": estimated,
        "seal_top": seal_top, "seal_base": seal_base, "reservoir_top": res_top,
        "deepest_casing": deepest, "casing_strings": len(casing),
        "casing_across_seal": None if deepest is None or seal_base is None else deepest >= seal_base,
        "abandon_year": year, "status": w["status"], "td": w["td"], "km": km_,
        "has_history": bool(wells.history(w["name"])),
    }
    missing = []
    if not tops:
        missing.append("formation tops (penetration estimated from total depth)")
    if not casing:
        missing.append("casing record")
    if year is None:
        missing.append("abandonment date")
    if not facts["has_history"]:
        missing.append("drilling history")
    schemes = {
        "status_age": status_age(facts),
        "barrier_depth": barrier_depth(facts),
        "proximity": proximity(facts),
    }
    known = [v for v in schemes.values() if v != "unknown"]
    disagree = len(set(known)) > 1 or ("unknown" in schemes.values() and known)
    return {"facts": facts, "schemes": schemes, "disagree": bool(disagree), "missing": missing,
            "worst": max(known, key=lambda v: LEVEL[v]) if known else "unknown"}


def status_age(f: dict) -> str:
    """Like the UK Southern North Sea screening: open or temporarily abandoned wells first, then old abandonments
    (before NORSOK D-010 rev 3, 2004, and before 1990 especially)."""
    if f["status"] in OPEN:
        return "high"
    if f["abandon_year"] is None:
        return "unknown"
    if f["abandon_year"] < 1990:
        return "high" if f["penetrates_reservoir"] is not False else "medium"
    if f["abandon_year"] < 2004:
        return "medium"
    return "low"


def barrier_depth(f: dict) -> str:
    """From the well's construction: does casing (and so likely cement) cover the seal where the well crosses it?"""
    if f["penetrates_reservoir"] is None:
        return "unknown"
    if not f["penetrates_seal"] and not f["penetrates_reservoir"]:
        return "low"
    if f["casing_across_seal"] is None:
        return "unknown"
    if f["casing_across_seal"]:
        return "low" if f["status"] not in OPEN else "medium"
    return "high" if f["penetrates_reservoir"] else "medium"


def proximity(f: dict) -> str:
    """Where the plume will be: distance to the injection point and whether the well reaches the storage unit."""
    if f["km"] is None or f["penetrates_reservoir"] is None:
        return "unknown"
    if not f["penetrates_reservoir"]:
        return "low"
    if f["km"] <= 5:
        return "high"
    if f["km"] <= 12:
        return "medium"
    return "low"


class Area(BaseModel):
    site: str | None = "northern-lights"
    center: str | None = Field(None, max_length=40)
    radius_km: float | None = Field(None, ge=1, le=60)
    reservoir: list[str] | None = Field(None, max_length=10)
    seal: list[str] | None = Field(None, max_length=10)


@router.get("")
def slash():
    return RedirectResponse("barrier/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("barrier.html")


@router.get("/api/sites")
def sites():
    return SITES


@router.post("/api/screen")
def screen(a: Area):
    s = SITES.get(a.site or "", {})
    center = wellbore(a.center or s.get("center", ""))
    if not center or center["lat"] is None:
        raise HTTPException(404, "unknown centre wellbore")
    radius = a.radius_km or s.get("radius", 12)
    reservoir = [x.upper() for x in (a.reservoir or s.get("reservoir", []))]
    seal = [x.upper() for x in (a.seal or s.get("seal", []))]
    res_depth = min((t["top"] for t in wells.tops(center["name"]) if t["unit"] in reservoir and t["top"]), default=None)
    out = []
    for w in nearby(center["lat"], center["lon"], radius, 200):
        if w["status"] in ("WILL NEVER BE DRILLED", "PREDRILLED"):
            continue
        out.append({**clean({k: w[k] for k in ("name", "kind", "status", "content", "entry", "completion", "td", "lat", "lon", "km", "field", "operator")}),
                    **assess(w, reservoir, seal, res_depth)})
    out.sort(key=lambda x: (-LEVEL[x["worst"]] if x["worst"] != "unknown" else -1.5, x["km"]))
    units = sorted({t["unit"] for x in out[:40] for t in wells.tops(x["name"]) if t["level"] == "FORMATION"})
    return {
        "center": clean(center), "radius": radius, "reservoir": reservoir, "seal": seal, "wells": out, "units": units,
        "totals": {
            "wells": len(out),
            "into_reservoir": sum(x["facts"]["penetrates_reservoir"] for x in out),
            "disagree": sum(x["disagree"] for x in out),
            "high": sum(x["worst"] == "high" for x in out),
            "missing": sum(bool(x["missing"]) for x in out),
        },
    }


PLUGS = {
    "type": "object",
    "properties": {
        "plugs": {"type": "array", "items": {"type": "object", "properties": {
            "kind": {"type": "string"}, "top_m": {"type": ["number", "null"]}, "base_m": {"type": ["number", "null"]},
            "source": {"type": "string"}, "quote": {"type": "string"}}, "required": ["kind", "top_m", "base_m", "source", "quote"]}},
        "cement": {"type": "array", "items": {"type": "object", "properties": {
            "casing": {"type": "string"}, "top_m": {"type": ["number", "null"]}, "source": {"type": "string"}, "quote": {"type": "string"}},
            "required": ["casing", "top_m", "source", "quote"]}},
        "abandonment": {"type": "string"},
    },
    "required": ["plugs", "cement", "abandonment"],
}


class Well(BaseModel):
    wellbore: str = Field(max_length=40)
    reservoir: list[str] = Field([], max_length=10)
    seal: list[str] = Field([], max_length=10)


@router.post("/api/ledger")
async def ledger(b: Well):
    c = wells.card(b.wellbore)
    if not c["header"]:
        raise HTTPException(404, "unknown wellbore")
    found = reports.for_wellbore(b.wellbore, "plug abandon cement casing barrier squeeze retainer", k=6)
    evidence = (
        f"[F:history] {c['history'][:5000]}\n\n"
        + "\n\n".join(f"[{p['ref']}] ({p['document']}) {p['text'][:1500]}" for p in found)
    )
    try:
        ext = await chat_json(
            [
                {"role": "system", "content": "From the evidence, extract permanent and temporary plugs (cement plugs, "
                 "bridge plugs, retainers) with top and base depth, cement tops behind casing, and how the well was "
                 "abandoned. source is the tag the fact came from ([F:history] or [S#]). Only what the evidence says."},
                {"role": "user", "content": evidence},
            ],
            PLUGS,
            max_tokens=1500,
        )
        text = await chat(
            [
                {"role": "system", "content": "You are a well integrity engineer screening a legacy well for P&A and for a "
                 "nearby CO2 store. Plain text, short sections: Barrier picture (casing, cement, plugs against the seal and "
                 "reservoir, with depths), Risk view, Data gaps and what to request from Diskos, Recommendation. Cite "
                 "[F:casing], [F:tops], [F:history] or [S#]. Say 'candidate barrier, check against NORSOK D-010' rather "
                 "than certifying anything. 220 words at most."},
                {"role": "user", "content": f"Seal units: {b.seal}. Reservoir units: {b.reservoir}.\n{wells.facts_text(c)}\n"
                 f"Extracted plugs and cement: {ext}\nReport passages:\n" + "\n".join(f"[{p['ref']}] {p['text'][:900]}" for p in found)},
            ],
            max_tokens=900,
        )
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    return {"card": c, "extracted": ext, "sources": found, "text": text}
