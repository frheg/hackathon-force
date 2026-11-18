"""Spud Brief: what the offset wells met, before you drill.

Havtil found that 71 % of NCS well-control incidents in 2013-2022 started with wrong or too-low pore-pressure
estimates, and asks for predictions by measured depth with bounds, shared offset data and checklists. This builds that
evidence pack: offsets by distance (and, in a backtest, only wells drilled before the target), their mud weights and
leak-off tests by depth, the hazards the model finds in each offset's drilling history (cited, cached per wellbore),
and a brief laid out by depth. Mud weight is a proxy for pore pressure, not a measurement, and the brief says so.
"""

import asyncio
import json
from statistics import median

import numpy as np

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from common import DATA_DIR, ModelBusy, chat, chat_json, clean, load_json, nearby, page, rows, save_json, wellbore
from sketches import wells

router = APIRouter(prefix="/spud")
CACHE = DATA_DIR / "spud" / "hazards.json"
HAZARDS = ["shallow gas", "shallow water flow", "kick", "losses", "overpressure", "tight hole", "stuck pipe",
           "wellbore instability", "H2S", "boulders", "other"]
SCHEMA = {
    "type": "object",
    "properties": {
        "hazards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": HAZARDS},
                    "depth_m": {"type": ["number", "null"]},
                    "formation": {"type": ["string", "null"]},
                    "quote": {"type": "string"},
                },
                "required": ["type", "depth_m", "formation", "quote"],
            },
        }
    },
    "required": ["hazards"],
}


def cache() -> dict:
    return load_json(CACHE)


def save(c: dict) -> None:
    save_json(CACHE, c)


async def hazards(name: str, store: dict) -> list[dict]:
    """Drilling hazards in one wellbore's FactPages drilling history, extracted once and cached."""
    if name in store:
        return store[name]
    text = wells.history(name)
    if not text:
        store[name] = []
        return []
    out = await chat_json(
        [
            {
                "role": "system",
                "content": "Extract every drilling hazard or problem the well history mentions: shallow gas, shallow "
                "water flow, kicks, losses, overpressure, tight hole, stuck pipe, wellbore instability, H2S, boulders. "
                "Give the measured depth in metres when stated (null if not), the formation if named, and a short "
                "exact quote. Shows of oil or gas in a reservoir are not hazards. Return an empty list if there are "
                "none.",
            },
            {"role": "user", "content": text[:6000]},
        ],
        SCHEMA,
        max_tokens=1200,
    )
    store[name] = out.get("hazards", [])
    return store[name]


def offsets(lat: float, lon: float, radius: float, before: str | None, exclude: str | None, limit: int) -> list[dict]:
    out = []
    for w in nearby(lat, lon, radius, 400):
        if exclude and w["name"] == exclude:
            continue
        if before and (w["entry"] is None or str(w["entry"]) >= before):
            continue
        out.append(w)
    # wells with a drilling history or mud data tell more; exploration wells describe their problems best
    have = {r["wlbName"] for r in rows("select distinct wlbName from wellbore_history")}
    out.sort(key=lambda w: (w["name"] not in have, w["kind"] != "exploration", w["km"]))
    return out[:limit]


def envelope(muds: dict[str, list[dict]], step: int = 100) -> list[dict]:
    bins: dict[int, list[float]] = {}
    for ms in muds.values():
        for m in ms:
            if m["md"] and m["weight"]:
                bins.setdefault(int(m["md"] // step * step), []).append(float(m["weight"]))
    return [
        {"md": b + step / 2, "min": min(v), "median": round(median(v), 3), "max": max(v), "n": len(v)}
        for b, v in sorted(bins.items())
        if len(v) >= 2
    ]


def margin(env: list[dict], lots: list[dict], tight: float = 0.06) -> dict | None:
    """The drilling window by depth: the offsets' leak-off and formation integrity tests (a fracture gradient proxy)
    against the heaviest offset mud weight at that depth. The test trend is the median test per 250 m band, made
    non-decreasing with depth and interpolated between tested depths only (no extrapolation above the shallowest or
    below the deepest test). Where the gap is under 0.06 g/cm3 the window is tight. Needs three tests or more."""
    pts = [(float(x["md"]), float(x["lot"])) for x in lots if x["md"] and x["lot"]]
    if len(pts) < 3 or not env:
        return None
    bands: dict[int, list[float]] = {}
    for d, v in pts:
        bands.setdefault(int(d // 250), []).append(v)
    knots = sorted((k * 250 + 125, float(np.median(v))) for k, v in bands.items())
    kd = np.array([k[0] for k in knots])
    kv = np.maximum.accumulate(np.array([k[1] for k in knots]))
    spread = float(np.std([v for _, v in pts]))
    out = []
    for e in env:
        if not kd[0] <= e["md"] <= kd[-1]:
            continue
        frac = float(np.interp(e["md"], kd, kv))
        out.append({"md": e["md"], "mud_max": e["max"], "frac": round(float(frac), 3), "margin": round(float(frac - e["max"]), 3)})
    narrow = [r for r in out if r["margin"] < tight]
    if not out:
        return None
    return {"fit": {"tests": len(pts), "knots": [[float(d), round(float(v), 3)] for d, v in zip(kd, kv)], "spread": round(spread, 3)},
            "rows": out, "tight": narrow, "min": min(out, key=lambda r: r["margin"])}

class Plan(BaseModel):
    wellbore: str | None = Field(None, max_length=40)  # backtest: a brief for an existing well from older wells
    lat: float | None = Field(None, ge=55, le=75)
    lon: float | None = Field(None, ge=-5, le=40)
    radius_km: float = Field(15, ge=1, le=80)
    offsets: int = Field(10, ge=2, le=25)
    td_m: float | None = Field(None, gt=0, lt=12000)


@router.get("")
def slash():
    return RedirectResponse("spud/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("spud.html")


@router.post("/api/brief")
async def brief(p: Plan):
    target = None
    if p.wellbore:
        target = wellbore(p.wellbore)
        if not target or target["lat"] is None:
            raise HTTPException(404, f"no wellbore {p.wellbore} with a position")
        lat, lon = target["lat"], target["lon"]
        before = str(target["entry"]) if target["entry"] else None
    elif p.lat is not None and p.lon is not None:
        lat, lon, before = p.lat, p.lon, None
    else:
        raise HTTPException(400, "give a wellbore or a position")
    offs = offsets(lat, lon, p.radius_km, before, target["name"] if target else None, p.offsets)
    if not offs:
        raise HTTPException(404, "no offset wells in reach: widen the radius")

    store = cache()
    try:
        found = await asyncio.gather(*[hazards(w["name"], store) for w in offs])
        target_hz = await hazards(target["name"], store) if target else []
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    finally:
        save(store)

    muds = {w["name"]: wells.mud(w["name"]) for w in offs}
    lots = [
        {"wellbore": w["name"], "md": c["depth"], "lot": c["lot_mud_density"], "test": c["test"], "casing": c["diameter"]}
        for w in offs
        for c in wells.casing(w["name"])
        if c["lot_mud_density"]
    ]
    tops = {w["name"]: [t for t in wells.tops(w["name"]) if t["level"] == "GROUP"] for w in offs}
    hz = [{**h, "wellbore": w["name"], "km": w["km"]} for w, hs in zip(offs, found) for h in hs]
    env = envelope(muds)
    window = margin(env, lots)

    lines = []
    for w, hs in zip(offs, found):
        lines.append(
            f"[{w['name']}] {w['km']} km, {w['kind']}, {w['content']}, entry {w['entry']}, TD {w['td']} m. "
            f"Groups: {', '.join(t['unit'] + ' ' + str(int(t['top'] or 0)) for t in tops[w['name']])}. "
            f"Hazards: {json.dumps(hs) if hs else 'none reported'}"
        )
    lot_text = "; ".join(f"{x['wellbore']} {x['test']} {x['lot']} g/cm3 at {x['md']} m" for x in lots[:40])
    env_text = "; ".join(f"{e['md']:.0f} m: {e['min']}-{e['max']} (median {e['median']})" for e in env[::2])
    if window:
        env_text += (f". Leak-off trend (fracture proxy, median per 250 m band) against the heaviest offset mud: narrowest "
                     f"window {window['min']['margin']} g/cm3 at {window['min']['md']:.0f} m; windows under 0.06 g/cm3 at "
                     + (", ".join(f"{r['md']:.0f} m" for r in window["tight"][:12]) or "no depth"))
    try:
        text = await chat(
            [
                {
                    "role": "system",
                    "content": "You write a pre-spud offset-well hazard brief for a drilling engineer on the Norwegian "
                    "Continental Shelf, following Havtil's recommendations: by measured depth interval, from top hole "
                    "down; for each interval the formations expected, hazards met in offsets (cite the offset wellbore "
                    "in brackets, like [15/9-19 A]), the offset mud-weight range and leak-off tests as the window "
                    "with lower and upper bounds, and what to watch. Then a checklist of 5 to 8 items. Mud weight is "
                    "a proxy for pore pressure, not a measurement: say so once. Plain text with short headings. No "
                    "invented numbers.",
                },
                {
                    "role": "user",
                    "content": f"Planned location {lat:.4f} N, {lon:.4f} E" + (f", planned TD {p.td_m} m" if p.td_m else "")
                    + f".\nOffsets:\n" + "\n".join(lines) + f"\nLeak-off and formation integrity tests: {lot_text or 'none'}"
                    + f"\nOffset mud weight by depth (g/cm3): {env_text or 'none'}",
                },
            ],
            max_tokens=1800,
        )
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")

    backtest = None
    if target:
        met = {h["type"] for h in target_hz}
        warned = {h["type"] for h in hz}
        backtest = {
            "target": target["name"],
            "met": sorted(met),
            "warned": sorted(met & warned),
            "missed": sorted(met - warned),
            "target_hazards": target_hz,
        }
    return {
        "center": {"lat": lat, "lon": lon},
        "target": clean(target) if target else None,
        "offsets": [clean({k: w[k] for k in ("name", "km", "kind", "content", "status", "entry", "td", "lat", "lon")}) for w in offs],
        "hazards": hz,
        "mud": muds,
        "lots": lots,
        "envelope": env,
        "window": window,
        "tops": tops,
        "text": text,
        "backtest": backtest,
    }


@router.get("/api/examples")
def examples():
    """Recent exploration wells whose drilling history mentions a hazard: good backtests."""
    r = rows(
        "select h.wlbName as name, e.wlbEntryYear as year, e.wlbMainArea as area from wellbore_history h "
        "join wellbore_exploration e on e.wlbWellboreName = h.wlbName "
        "where e.wlbEntryYear >= 2012 and regexp_matches(lower(h.wlbHistory), 'shallow gas|kick|losses|overpress|stuck') "
        "order by e.wlbEntryYear desc limit 12"
    )
    return r
