"""Diskos Detective: answers from Diskos well reports and FactPages, every claim cited, plus wellbore dossiers and the
DISKOS-QA scorecard.

The agent follows the TADI design (arXiv 2605.00060): typed tools over structured tables and report search, called
by the model, and an answer that cites [S#] report passages and [F:table] FactPages facts.
"""

import json
import re
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Literal

from pydantic import BaseModel, Field

from common import DATA_DIR, ModelBusy, chat, chat_json, complete, page
from sketches import reports, wells

router = APIRouter(prefix="/detective")
MAX_STEPS = 6

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_reports",
            "description": "Search Diskos well report passages (geology, cores, logs, tests, drilling, VSP). Name the "
            "wellbore, field or formation when the question does, so the search stays inside it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "wellbore": {"type": "string", "description": "e.g. 9/2-1 or 15/9-F-12"},
                    "field": {"type": "string", "description": "upper case, e.g. YME"},
                    "formation": {"type": "string", "description": "e.g. SANDNES FM"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wellbore_facts",
            "description": "FactPages facts for one wellbore: header (operator, dates, depths, content, position), "
            "formation tops, casing and leak-off tests, mud weights, drill-stem tests, cores and the drilling history.",
            "parameters": {"type": "object", "properties": {"wellbore": {"type": "string"}}, "required": ["wellbore"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nearby_wellbores",
            "description": "Wellbores within a radius of a wellbore, with distance, content and status.",
            "parameters": {
                "type": "object",
                "properties": {"wellbore": {"type": "string"}, "radius_km": {"type": "number"}},
                "required": ["wellbore"],
            },
        },
    },
]

SYSTEM = """You answer questions about Norwegian Continental Shelf wells from evidence only.
Use the tools: search_reports for what the reports say, wellbore_facts for official FactPages numbers,
nearby_wellbores for neighbours. Call tools until you have the evidence, then answer in a few sentences.
Cite every claim: [S3] for a report passage, [F:tops], [F:casing], [F:dst], [F:mud], [F:cores], [F:history] or
[F:wellbore] for FactPages. Read each passage to the end. Give what the evidence says even if it answers only part
of the question; say the evidence is missing only when nothing bears on it. Never invent numbers."""


class Session:
    """The evidence one answer collected: passages get stable [S#] numbers across tool calls."""

    def __init__(self):
        self.passages: list[dict] = []
        self.trace: list[dict] = []

    def add(self, found: list[dict]) -> list[dict]:
        out = []
        for p in found:
            known = next((q for q in self.passages if q["chunk_id"] == p["chunk_id"]), None)
            if not known:
                known = {**p, "ref": f"S{len(self.passages) + 1}"}
                self.passages.append(known)
            out.append(known)
        return out

    async def run(self, name: str, args: dict) -> str:
        t = time.time()
        if name == "search_reports":
            ents = {
                "wellbores": [args["wellbore"]] if args.get("wellbore") else [],
                "fields": [args["field"].upper()] if args.get("field") else [],
                "formations": [args["formation"].upper()] if args.get("formation") else [],
            }
            mode = "filtered" if any(ents.values()) else "hybrid"
            found = self.add(await reports.search(args.get("query", ""), k=5, mode=mode, ents=ents if any(ents.values()) else None))
            result = "\n\n".join(f"[{p['ref']}] ({p['document']}; {', '.join(p['wellbores'])}) {p['text']}" for p in found)
        elif name == "wellbore_facts":
            c = wells.card(args.get("wellbore", ""))
            result = wells.facts_text(c) if c["header"] else f"no wellbore named {args.get('wellbore')} in FactPages"
        elif name == "nearby_wellbores":
            w = wells.header(args.get("wellbore", ""))
            if not w or w.get("lat") is None:
                result = "unknown wellbore"
            else:
                from common import nearby

                near = nearby(w["lat"], w["lon"], float(args.get("radius_km") or 10), 25)
                result = "\n".join(f"{n['name']}: {n['km']} km, {n['content']}, {n['status']}, {n['kind']}" for n in near if n["name"] != w["name"])
        else:
            result = f"unknown tool {name}"
        self.trace.append({"tool": name, "args": args, "ms": int((time.time() - t) * 1000), "chars": len(result)})
        return result


async def agent(question: str) -> dict:
    s = Session()
    messages: list[dict] = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    t0 = time.time()
    for _ in range(MAX_STEPS):
        msg = await complete(messages, tools=TOOLS, max_tokens=1200)
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"answer": msg["content"], "sources": s.passages, "trace": s.trace, "seconds": round(time.time() - t0, 1)}
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for call in calls:
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = await s.run(call["function"]["name"], args)
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": result[:30000]})
    messages.append({"role": "user", "content": "Answer now from the evidence you have, with citations."})
    answer = await chat(messages, max_tokens=900)
    return {"answer": answer, "sources": s.passages, "trace": s.trace, "seconds": round(time.time() - t0, 1)}


async def rag(question: str, mode: str) -> dict:
    """One-shot retrieval and answer (the scorecard's configurations); mode 'closed' answers without evidence."""
    t0 = time.time()
    found = [] if mode == "closed" else await reports.search(question, k=5, mode=mode)
    context = "\n\n".join(f"[{p['ref']}] ({p['document']}) {p['text']}" for p in found)
    sys = (
        "Answer the question about Norwegian wells in one to three sentences. "
        + ("Use only the passages and cite them like [S2]. Read every passage to the end; the answer is often in a "
           "detail. Give what the passages do say, even if it answers only part of the question; say the evidence is "
           "missing only when no passage bears on it." if found else "Answer from what you know.")
    )
    answer = await chat(
        [{"role": "system", "content": sys}, {"role": "user", "content": (f"Passages:\n{context}\n\n" if found else "") + f"Question: {question}"}],
        max_tokens=400,
    )
    return {"answer": answer, "sources": found, "trace": [], "seconds": round(time.time() - t0, 1)}


class Ask(BaseModel):
    q: str = Field(min_length=3, max_length=2000)
    mode: Literal["agent", "filtered", "hybrid", "vector", "closed"] = "agent"


@router.get("")
def slash():
    return RedirectResponse("detective/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("detective.html")


@router.post("/api/ask")
async def ask(body: Ask):
    try:
        out = await (agent(body.q) if body.mode == "agent" else rag(body.q, body.mode))
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    out["entities"] = reports.entities(body.q)
    return out


@router.get("/api/wellbores")
def find(q: str = ""):
    df, _ = reports.corpus()
    covered = {w for ws in df.wellbores for w in ws}
    hits = wells.search_names(q, 30) if q else []
    for h in hits:
        h["reports"] = sum(1 for ws in df.wellbores if wells.norm(h["name"]) in ws)
    if not q:  # the wellbores with the most report passages
        from collections import Counter

        top = Counter(w for ws in df.wellbores for w in ws).most_common(30)
        hits = [{"name": w, "reports": n} for w, n in top]
    return {"wellbores": hits, "covered": len(covered)}


@router.get("/api/dossier/{name:path}")
async def dossier(name: str):
    t0 = time.time()
    c = wells.card(name)
    if not c["header"]:
        raise HTTPException(404, f"no wellbore {name} in FactPages")
    found = reports.for_wellbore(name, "summary results reservoir test core drilling problems", k=8)
    context = "\n\n".join(f"[{p['ref']}] ({p['document']}) {p['text'][:1600]}" for p in found)
    try:
        text = await chat(
            [
                {
                    "role": "system",
                    "content": "Write a one-page wellbore dossier for a geoscientist, in plain text with short headed "
                    "sections: Summary, Stratigraphy and reservoir, Shows, cores and tests, Drilling events, Open "
                    "questions. Cite every fact: [F:tops], [F:casing], [F:dst], [F:mud], [F:cores], [F:history], "
                    "[F:wellbore] for FactPages and [S#] for report passages. Say where sources disagree. No "
                    "invented numbers.",
                },
                {"role": "user", "content": f"Wellbore {c['header']['name']}.\n\nFactPages:\n{wells.facts_text(c)}\n\nReport passages:\n{context or 'none'}"},
            ],
            max_tokens=1600,
        )
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    return {"card": c, "sources": found, "text": text, "seconds": round(time.time() - t0, 1)}


@router.get("/api/scorecard")
def scorecard():
    f = DATA_DIR / "diskosqa" / "scorecard.json"
    if not f.exists():
        return {"ready": False}
    return {"ready": True, **json.loads(f.read_text())}


# -- claim check: is each sentence that cites a report passage actually supported by it? --

VERDICTS = {"type": "object", "properties": {"claims": {"type": "array", "items": {"type": "object", "properties": {
    "i": {"type": "integer"}, "verdict": {"type": "string", "enum": ["supported", "partly", "unsupported"]},
    "why": {"type": "string"}}, "required": ["i", "verdict", "why"]}}}, "required": ["claims"]}


def sentences(text: str) -> list[str]:
    """Sentences (and lines), each keeping its trailing citations."""
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])|\n+", text.strip()) if p.strip()]


class Check(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)
    sources: list[dict] = Field(default_factory=list, max_length=40)


@router.post("/api/verify")
async def verify(b: Check):
    texts = {s.get("ref"): str(s.get("text", ""))[:5000] for s in b.sources}
    claims = []
    for s in sentences(b.answer):
        refs = re.findall(r"\[(S\d+)\]", s)
        facts = re.findall(r"\[F:(\w+)\]", s)
        claims.append({"text": s, "refs": refs, "facts": facts})
    to_check = [(i, c) for i, c in enumerate(claims) if any(r in texts for r in c["refs"])]
    if to_check:
        listing = "\n\n".join(
            f"Claim {i}: {c['text']}\n" + "\n".join(f"[{r}] {texts[r]}" for r in c["refs"] if r in texts) for i, c in to_check
        )
        out = await chat_json(
            [{"role": "system", "content": "For each claim, decide if the cited passages support it: 'supported' (every fact "
              "in the claim is in the passages), 'partly' (some facts are, some are not), or 'unsupported'. Numbers must "
              "match. Say in a few words what is missing when it is not supported."},
             {"role": "user", "content": listing}],
            VERDICTS, max_tokens=1500)
        got = {x["i"]: x for x in out.get("claims", [])}
        for i, c in to_check:
            v = got.get(i)
            c["verdict"], c["why"] = (v["verdict"], v["why"]) if v else ("unchecked", "")
    for c in claims:
        c.setdefault("verdict", "table" if c["facts"] else "uncited")
        c.setdefault("why", "")
    n = sum(c["verdict"] in ("supported", "partly", "unsupported") for c in claims)
    return {"claims": claims, "checked": n, "supported": sum(c["verdict"] == "supported" for c in claims),
            "unsupported": sum(c["verdict"] == "unsupported" for c in claims)}
