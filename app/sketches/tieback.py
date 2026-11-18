"""Tie-back Matchmaker: rank undeveloped discoveries against producing host fields before the hosts close.

For every undeveloped discovery with a resource estimate, each producing field within reach is scored on distance,
spare capacity (how far the host has declined from its peak), fluid match and timing (does the host live long
enough for a tie-back to be built and produce?). The discovery's production profile is a reference class: the
yearly profiles of small NCS fields, scaled to the discovery's volume (the outside view that beat operators'
forecasts in Nesvold and Bratvold 2022). The model writes a screening memo for a pair.
"""

import math
from datetime import date
from functools import lru_cache

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from common import ModelBusy, chat, km, nearby, page, rows, wellbore

router = APIRouter(prefix="/tieback")
UNDEVELOPED = ("Production in clarification phase", "Production likely but unclarified", "Production not evaluated")
REACH_KM = 60
LEAD_YEARS = 4  # decision to first oil for a subsea tie-back, roughly
RUNS = 2000  # Monte Carlo samples per discovery-host pair
YEAR = date.today().year


def decimal(deg, mins, sec, code) -> float | None:
    if deg is None:
        return None
    v = float(deg) + float(mins or 0) / 60 + float(sec or 0) / 3600
    return -v if code in ("S", "W") else v


@lru_cache(maxsize=1)
def hosts() -> dict:
    """Producing fields with position, rate history, remaining reserves and fluid."""
    fac = rows(
        "select fclBelongsToName as field, fclName, fclSurface, fclKind, fclNsDeg, fclNsMin, fclNsSec, fclNsCode, "
        "fclEwDeg, fclEwMin, fclEwSec, fclEwCode from facility_fixed where fclBelongsToKind = 'FIELD' "
        "and fclPhase = 'IN SERVICE'"
    )
    where = {}
    for f in sorted(fac, key=lambda f: f["fclSurface"] != "Y"):  # surface facilities first: that is where tie-backs land
        if f["field"] not in where:
            where[f["field"]] = (decimal(f["fclNsDeg"], f["fclNsMin"], f["fclNsSec"], f["fclNsCode"]),
                                 decimal(f["fclEwDeg"], f["fclEwMin"], f["fclEwSec"], f["fclEwCode"]), f["fclName"], f["fclKind"])
    prod = rows(
        "select prfInformationCarrier as field, prfYear as y, sum(prfPrdOeNetMillSm3) as oe from field_production_monthly "
        "group by all order by field, y"
    )
    years: dict[str, dict[int, float]] = {}
    for p in prod:
        years.setdefault(p["field"], {})[p["y"]] = p["oe"] or 0
    res = {
        r["fldName"]: r
        for r in rows(
            "select fldName, fldRemainingOE, fldRecoverableOE from field_reserves qualify row_number() over "
            "(partition by fldName order by fldVersion desc) = 1"
        )
    }
    out = {}
    for f in rows("select fldName, cmpLongName, fldCurrentActivitySatus, fldHcType, fldMainArea from field where fldCurrentActivitySatus = 'Producing'"):
        name = f["fldName"]
        if name not in where or name not in years or where[name][0] is None:
            continue
        ys = years[name]
        recent = [ys.get(y, 0) for y in (YEAR - 1, YEAR - 2) if ys.get(y)]
        rate = recent[0] if recent else 0  # MSm3 o.e. per year, last full year
        peak = max(ys.values())
        remaining = (res.get(name) or {}).get("fldRemainingOE")
        life = remaining / rate if rate and remaining is not None else None
        out[name] = {
            "field": name, "operator": f["cmpLongName"], "hc": f["fldHcType"], "area": f["fldMainArea"],
            "lat": where[name][0], "lon": where[name][1], "facility": where[name][2], "facility_kind": where[name][3],
            "rate": round(rate, 2), "peak": round(peak, 2), "spare": round(max(0.0, 1 - rate / peak), 2) if peak else 0,
            "remaining": remaining, "life_years": round(life, 1) if life is not None else None,
            "end_year": int(YEAR + life) if life is not None else None,
        }
    return out


@lru_cache(maxsize=1)
def discoveries() -> list[dict]:
    out = []
    for d in rows(
        "select d.dscName, d.cmpLongName, d.dscCurrentActivityStatus, d.dscHcType, d.wlbName, d.nmaName, "
        "d.dscDiscoveryYear, r.dscRecoverableOil, r.dscRecoverableGas, r.dscRecoverableOe, r.dscReservesRC "
        "from discovery d join discovery_reserves r using (dscNpdidDiscovery) "
        "where d.dscCurrentActivityStatus in (?, ?, ?) and r.dscRecoverableOe > 0",
        *UNDEVELOPED,
    ):
        w = wellbore(d["wlbName"] or "")
        if not w or w["lat"] is None:
            continue
        out.append({
            "name": d["dscName"], "operator": d["cmpLongName"], "status": d["dscCurrentActivityStatus"],
            "hc": d["dscHcType"], "well": d["wlbName"], "area": d["nmaName"], "year": d["dscDiscoveryYear"],
            "oe": d["dscRecoverableOe"], "oil": d["dscRecoverableOil"], "gas": d["dscRecoverableGas"],
            "lat": w["lat"], "lon": w["lon"],
        })
    return out


def fluid_fit(a: str | None, b: str | None) -> float:
    a, b = (a or "").upper(), (b or "").upper()
    if not a or not b:
        return 0.6
    oil = lambda s: "OIL" in s
    gas = lambda s: "GAS" in s or "CONDENSATE" in s
    if a == b:
        return 1.0
    if (oil(a) and oil(b)) or (gas(a) and gas(b)):
        return 0.85
    return 0.45


BUCKETS = ((0, 5), (5, 15), (15, 60))  # MSm3 o.e. recoverable


def bucket(oe: float) -> tuple:
    return next((b for b in BUCKETS if b[0] <= oe < b[1]), BUCKETS[-1])


@lru_cache(maxsize=4)
def reference_class(size: tuple = (0, 60)) -> dict:
    """Yearly production as a share of ultimate recovery, year by year from start, for small NCS fields that have
    produced at least 60 % of their recoverable volume (so their profile is mostly known). P10/P50/P90."""
    res = {r["fldName"]: r["fldRecoverableOE"] for r in rows(
        "select fldName, fldRecoverableOE from field_reserves qualify row_number() over (partition by fldName order by fldVersion desc) = 1")}
    prod = rows("select prfInformationCarrier as f, prfYear as y, sum(prfPrdOeNetMillSm3) as oe from field_production_monthly group by all")
    by: dict[str, dict[int, float]] = {}
    for p in prod:
        by.setdefault(p["f"], {})[p["y"]] = p["oe"] or 0
    curves = []
    for f, ys in by.items():
        ur = res.get(f)
        if not ur or not size[0] <= ur < size[1] or sum(ys.values()) < 0.6 * ur:
            continue
        start = min(y for y, v in ys.items() if v > 0)
        curves.append([ys.get(start + i, 0) / ur for i in range(25)])
    a = np.array(curves)
    return {"n": len(curves), **{p: np.percentile(a, q, axis=0).round(4).tolist() for p, q in (("p10", 10), ("p50", 50), ("p90", 90))}}


def odds(d: dict, h: dict, runs: int = RUNS, seed: int = 7) -> dict | None:
    """Monte Carlo: how likely is the discovery to be produced before the host closes?

    Uncertain: the discovery's volume (lognormal, about +-35 %, as for small NCS discoveries in clarification), its
    profile (a draw between the P10 and P90 curves of its size class), the build time (3 to 6 years) and the host's
    remaining life (remaining reserves over current rate, lognormal +-30 % for reserve revisions and decline). Returns
    the chance that 80 % of the discovery is produced before the host ends, and the expected share and volume.
    """
    if h["life_years"] is None:
        return None
    rng = np.random.default_rng(seed)
    rc = reference_class(bucket(d["oe"]))
    curves = np.array([rc["p10"], rc["p50"], rc["p90"]])
    curves = curves / curves.sum(1, keepdims=True)
    u = rng.uniform(0, 2, runs)  # 0 = P10 curve, 1 = P50, 2 = P90
    lo = np.floor(u).clip(0, 1).astype(int)
    frac = u - lo
    prof = curves[lo] * (1 - frac[:, None]) + curves[lo + 1] * frac[:, None]
    cum = np.cumsum(prof / prof.sum(1, keepdims=True), axis=1)
    life = h["life_years"] * rng.lognormal(0, 0.3, runs)
    lead = rng.uniform(3, 6, runs)
    years = np.clip(np.floor(life - lead), -1, cum.shape[1] - 1).astype(int)
    share = np.where(years >= 0, cum[np.arange(runs), years.clip(0)], 0.0)
    volume = d["oe"] * rng.lognormal(0, 0.35, runs)
    return {
        "p_fit": round(float((share >= 0.8).mean()), 3),
        "share": round(float(share.mean()), 3),
        "volume": round(float((share * volume).mean()), 2),
        "share_p10": round(float(np.percentile(share, 10)), 3),
        "share_p90": round(float(np.percentile(share, 90)), 3),
    }


def score(d: dict, h: dict) -> dict:
    dist = km(d["lat"], d["lon"], h["lat"], h["lon"])
    rc = reference_class(bucket(d["oe"]))
    # years for the discovery to produce 80 % of its volume on the median curve (scaled to sum to one)
    p50 = np.array(rc["p50"])
    cum, need = 0.0, 0
    for i, f in enumerate(p50 / p50.sum()):
        cum += f
        if cum >= 0.8:
            need = i + 1
            break
    need = need or 15
    window = None if h["life_years"] is None else h["life_years"] - LEAD_YEARS
    timing = 0.3 if window is None else max(0.0, min(1.0, window / need))
    s_dist = math.exp(-dist / 25)
    s_cap = min(1.0, 0.25 + h["spare"])
    s_fluid = fluid_fit(d["hc"], h["hc"])
    total = s_dist * 0.35 + s_cap * 0.2 + s_fluid * 0.2 + timing * 0.25
    flags = []
    if window is not None and window < need:
        flags.append(f"host may close before the discovery is {'half ' if window < need / 2 else ''}produced")
    if window is not None and window < 0:
        flags.append("host life shorter than the build time")
    if h["spare"] < 0.2:
        flags.append("host near its peak: little spare capacity")
    if s_fluid < 0.6:
        flags.append("different fluid: processing may not fit")
    return {
        "host": h["field"], "km": round(dist, 1), "score": round(total, 3), "fluid": round(s_fluid, 2),
        "timing": round(timing, 2), "spare": h["spare"], "host_end_year": h["end_year"], "years_needed": need,
        "flags": flags,
        "odds": odds(d, h),
    }


def matches(limit_hosts: int = 3) -> list[dict]:
    hs = hosts()
    out = []
    for d in discoveries():
        cand = [score(d, h) for h in hs.values() if km(d["lat"], d["lon"], h["lat"], h["lon"]) <= REACH_KM]
        cand.sort(key=lambda c: -c["score"])
        best = cand[0] if cand else None
        out.append({**d, "best": best, "hosts": cand[:limit_hosts], "urgency": urgency(d, best)})
    out.sort(key=lambda m: -(m["urgency"] or 0))
    return out


def urgency(d: dict, best: dict | None) -> float | None:
    """Volume at stake, weighted by how soon the best host closes: big discoveries next to closing hosts first."""
    if not best:
        return None
    years = (best["host_end_year"] or YEAR + 30) - YEAR
    return round(d["oe"] * best["score"] / max(1.0, years / 5), 3)


@router.get("")
def slash():
    return RedirectResponse("tieback/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("tieback.html")


@router.get("/api/board")
def board():
    m = matches()
    stranded = [x for x in m if not x["best"]]
    rc = {f"{a}-{b}": reference_class((a, b)) for a, b in BUCKETS}
    return {
        "discoveries": m,
        "hosts": list(hosts().values()),
        "reference": rc,
        "totals": {
            "discoveries": len(m),
            "oe": round(sum(x["oe"] for x in m), 1),
            "with_host": len(m) - len(stranded),
            "at_risk_oe": round(sum(x["oe"] for x in m if x["best"] and x["best"]["flags"]), 1),
        },
    }


class Memo(BaseModel):
    discovery: str
    host: str


@router.post("/api/memo")
async def memo(body: Memo):
    d = next((x for x in discoveries() if x["name"] == body.discovery), None)
    h = hosts().get(body.host)
    if not d or not h:
        raise HTTPException(404, "unknown discovery or host")
    s = score(d, h)
    desc = rows("select fldDescriptionHeading, fldDescriptionText from field_description where fldName = ?", h["field"])
    host_text = "\n".join(f"{x['fldDescriptionHeading']}: {x['fldDescriptionText']}" for x in desc)[:5000]
    near = [w for w in nearby(d["lat"], d["lon"], 8, 12)]
    near_text = "; ".join(f"{w['name']} ({w['km']} km, {w['content']}, {w['status']})" for w in near)
    rc = reference_class(bucket(d["oe"]))
    p50 = np.array(rc["p50"])
    profile = [round(f * d["oe"], 2) for f in (p50 / p50.sum())[:15]]
    try:
        text = await chat(
            [
                {
                    "role": "system",
                    "content": "You write tie-back screening memos for a licence team on the Norwegian Continental "
                    "Shelf. Plain text, short headed sections: Recommendation (study further, or not, in one line), "
                    "Why this host, Timing, Risks and unknowns, Next steps. 250 words at most. Use only the facts "
                    "given; say what must be checked (host ullage, processing, pipeline capacity) since those are not "
                    "public.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Discovery {d['name']}: {d['hc']}, {d['oe']} million Sm3 o.e. recoverable (Sodir), status "
                        f"\"{d['status']}\", found {d['year']} by well {d['well']}, operator {d['operator']}.\n"
                        f"Host field {h['field']} ({h['operator']}, {h['hc']}): {s['km']} km away; produced {h['rate']} million "
                        f"Sm3 o.e. last year against a peak of {h['peak']}, so it is {round(h['spare'] * 100)} % below its peak "
                        f"(a rough proxy for spare capacity, not a measured one); remaining reserves {h['remaining']} million Sm3 "
                        f"o.e., which at the current rate lasts until about {h['end_year']}.\n"
                        f"Timing: the discovery needs about {s['years_needed']} years to produce 80 % of its volume on the median "
                        f"reference-class profile, after about {LEAD_YEARS} years to build; {round(s['timing'] * 100)} % of that fits "
                        f"inside the host's remaining life. Monte Carlo over volume, profile, build time and host life: {s['odds']}. Fluid match {s['fluid']} (1 is identical). Flags: {s['flags'] or 'none'}.\n"
                        f"Median profile for the discovery, million Sm3 o.e. per year from start: {profile}\n"
                        f"Wellbores within 8 km: {near_text or 'none'}\n"
                        f"Host description:\n{host_text}"
                    ),
                },
            ],
            max_tokens=900,
        )
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    return {"text": text, "score": s, "profile": profile}
