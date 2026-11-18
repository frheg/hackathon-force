"""Lost Time Hunter: where the rig time went in Volve's 1,759 daily drilling reports (Equinor, WITSML, CC BY 4.0 copy
on Hugging Face), and what was learned.

Three kinds of lost time:
- reported NPT: activities coded 'interruption' or with state 'fail' (repair, waiting on weather, fishing, ...);
- invisible lost time (ILT): drilling slower than the 75th percentile rate of penetration for the same depth band
  across all Volve wells (the percentile benchmark of SPE 188238, not a composite best);
- hidden NPT: lines logged as fine whose comments describe a problem (tight hole, overpull, losses, repeated
  attempts); the model classifies them per wellbore (as in the CSIRO study that found 923 h among 'normal' entries).
Rig time is priced at a day rate you set.
"""

import json
import re
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from common import DATA_DIR, ModelBusy, chat, chat_json, load_json, norm, page, save_json
from sketches.reports import BM25

router = APIRouter(prefix="/losttime")
D = DATA_DIR / "volve"
HIDDEN = D / "hidden.json"
SUSPECT = re.compile(
    r"tight|overpull|over-pull|pack.?off|stuck|loss|losses|kick|influx|leak|fail|unable|problem|repair|wait|"
    r"again|re-?run|re-?attempt|attempted|fish|junk|washout|cavings|stall|torque|drag|restrict|obstruct", re.I)
CAUSES = ["wellbore instability / tight hole", "stuck pipe", "losses", "well control / influx", "equipment failure",
          "waiting (weather, orders, equipment)", "repeated operation / rework", "fishing", "other"]


@lru_cache(maxsize=1)
def activities() -> pd.DataFrame:
    d = pd.read_parquet(D / "ddr.parquet")
    rows_ = []
    for r in d.itertuples():
        for a in r.activity if r.activity is not None else []:
            rows_.append({**a, "wellbore": norm(r.nameWellbore), "report": r.docName})
    a = pd.DataFrame(rows_)
    a["start"] = pd.to_datetime(a.dTimStart, utc=True, errors="coerce")
    a["end"] = pd.to_datetime(a.dTimEnd, utc=True, errors="coerce")
    a["hours"] = ((a.end - a.start).dt.total_seconds() / 3600).clip(lower=0, upper=24)
    a["md"] = pd.to_numeric(a.md, errors="coerce")
    a[["major", "minor"]] = a.proprietaryCode.fillna("unknown -- unknown").str.split(" -- ", n=1, expand=True)
    a["npt"] = (a.major == "interruption") | (a.state == "fail")
    a = a.sort_values(["wellbore", "start"]).reset_index(drop=True)
    a["id"] = a.index
    # invisible lost time on drilling: hours beyond what the P75 rate of penetration for the depth band would take
    drill = a[(a.proprietaryCode == "drilling -- drill") & a.md.notna()].copy()
    drill["prev_md"] = drill.groupby("wellbore").md.shift()
    drill["dmd"] = (drill.md - drill.prev_md).where(lambda s: s > 0)
    drill["rop"] = drill.dmd / drill.hours.where(drill.hours > 0)
    drill["band"] = (drill.md // 500) * 500
    p75 = drill.groupby("band").rop.quantile(0.75)
    drill["ilt"] = (drill.hours - drill.dmd / drill.band.map(p75)).clip(lower=0)
    a["ilt"] = drill.ilt.reindex(a.index).fillna(0)
    a["rop"] = drill.rop.reindex(a.index)
    return a


def hidden_cache() -> dict:
    return load_json(HIDDEN)


def summary(a: pd.DataFrame, hidden: list[dict]) -> dict:
    hid_hours = sum(h["hours"] for h in hidden if h.get("hidden"))
    return {
        "days": round(float(a.hours.sum()) / 24, 1),
        "npt_days": round(float(a[a.npt].hours.sum()) / 24, 1),
        "ilt_days": round(float(a.ilt.sum()) / 24, 1),
        "hidden_days": round(hid_hours / 24, 1),
        "reports": int(a.report.nunique()),
        "activities": int(len(a)),
    }


@router.get("")
def slash():
    return RedirectResponse("losttime/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("losttime.html")


@router.get("/api/overview")
def overview():
    a = activities()
    hc = hidden_cache()
    per = []
    for w, g in a.groupby("wellbore"):
        s = summary(g, hc.get(w, []))
        per.append({"wellbore": w, **s, "scanned": w in hc,
                    "start": str(g.start.min())[:10], "max_md": float(g.md.max()) if g.md.notna().any() else None})
    per.sort(key=lambda x: -x["npt_days"])
    causes = a[a.npt].groupby("minor").hours.sum().sort_values(ascending=False) / 24
    return {"total": summary(a, [h for v in hc.values() for h in v]), "wellbores": per,
            "npt_by_cause": {k: round(float(v), 1) for k, v in causes.head(12).items()}}


@router.get("/api/wellbore/{name:path}")
def wellbore_detail(name: str):
    a = activities()
    g = a[a.wellbore == norm(name)]
    if g.empty:
        raise HTTPException(404, f"no reports for {name}")
    hidden = hidden_cache().get(norm(name), [])
    hid = {h["id"]: h for h in hidden}
    t0 = g.start.min()
    g = g.assign(day=(g.start - t0).dt.total_seconds() / 86400, depth=g.md.ffill().cummax())
    events = g[g.npt | (g.ilt > 1) | g.id.isin(hid)]
    return {
        "wellbore": norm(name),
        "summary": summary(g, hidden),
        "curve": {"day": g.day.round(3).tolist(), "md": [None if pd.isna(x) else float(x) for x in g.depth],
                  "npt": g.npt.tolist(), "major": g.major.tolist()},
        "phase_hours": {k: round(float(v), 1) for k, v in g.groupby("major").hours.sum().sort_values(ascending=False).items()},
        "npt_by_cause": {k: round(float(v), 1) for k, v in g[g.npt].groupby("minor").hours.sum().sort_values(ascending=False).items()},
        "events": [
            {"id": int(r.id), "date": str(r.start)[:16], "day": round(r.day, 2), "md": None if pd.isna(r.md) else float(r.md),
             "code": r.proprietaryCode, "detail": r.stateDetailActivity, "hours": round(r.hours, 2), "ilt": round(r.ilt, 2),
             "kind": "reported" if r.npt else ("hidden" if r.id in hid else "slow drilling"),
             "cause": hid.get(r.id, {}).get("cause"), "comment": r.comments}
            for r in events.itertuples()
        ][:400],
        "scanned": bool(hidden),
    }


SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "integer"}, "hidden": {"type": "boolean"}, "cause": {"type": "string", "enum": CAUSES},
    "why": {"type": "string"}}, "required": ["id", "hidden", "cause", "why"]}}}, "required": ["lines"]}


@router.post("/api/scan/{name:path}")
async def scan(name: str):
    """Classify the 'ok' lines with suspect words in one wellbore's reports (cached)."""
    a = activities()
    w = norm(name)
    g = a[(a.wellbore == w) & ~a.npt & a.comments.fillna("").str.contains(SUSPECT)]
    out = []
    try:
        for i in range(0, len(g), 25):
            batch = g.iloc[i : i + 25]
            listing = "\n".join(f"{r.id} | {r.proprietaryCode} | {r.hours:.1f} h | {r.comments}" for r in batch.itertuples())
            res = await chat_json(
                [
                    {"role": "system", "content": "These daily drilling report lines were logged as normal operations. "
                     "For each, decide if it hides non-productive time: time lost to a problem (tight hole, overpull, "
                     "losses, stuck pipe, influx, equipment failure, waiting, or repeating an operation that failed). "
                     "Routine work that mentions a word like 'wait' or 'torque' as normal practice is not hidden NPT."},
                    {"role": "user", "content": listing},
                ],
                SCHEMA,
                max_tokens=3000,
            )
            hours = dict(zip(batch.id, batch.hours))
            out += [{**x, "hours": round(float(hours.get(x["id"], 0)), 2)} for x in res["lines"] if x["id"] in hours]
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    c = hidden_cache()
    c[w] = out
    save_json(HIDDEN, c)
    return {"scanned": len(g), "hidden": sum(x["hidden"] for x in out), "hours": round(sum(x["hours"] for x in out if x["hidden"]), 1)}


@lru_cache(maxsize=1)
def lessons_index():
    a = activities()
    rows_ = a[a.npt | a.comments.fillna("").str.contains(SUSPECT)].reset_index(drop=True)
    return rows_, BM25((rows_.proprietaryCode.fillna("") + " " + rows_.comments.fillna("")).tolist())


class Lesson(BaseModel):
    q: str = Field(min_length=3, max_length=1000)


@router.post("/api/lessons")
async def lessons(b: Lesson):
    r, bm = lessons_index()
    s = np.array(bm.scores(b.q))
    top = r.iloc[np.argsort(-s)[:25]]
    lines = "\n".join(f"[{x.wellbore} {str(x.start)[:10]}] {x.proprietaryCode}, {x.hours:.1f} h, MD {x.md}: {x.comments}" for x in top.itertuples())
    try:
        text = await chat(
            [{"role": "system", "content": "You are a drilling engineer writing lessons learned from daily drilling reports "
              "on the Volve field. Answer the question from the report lines only: what happened, how much time it cost, "
              "what was done, and the lesson for the next well. Cite lines as [wellbore date]. 200 words at most."},
             {"role": "user", "content": f"Question: {b.q}\n\nReport lines:\n{lines}"}],
            max_tokens=800,
        )
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    return {"text": text, "lines": [{"wellbore": x.wellbore, "date": str(x.start)[:10], "code": x.proprietaryCode,
                                     "hours": round(x.hours, 2), "md": None if pd.isna(x.md) else x.md, "comment": x.comments}
                                    for x in top.head(12).itertuples()]}
