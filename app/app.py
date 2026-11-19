"""Subsurface Studio: oil and gas apps on Norwegian Continental Shelf data and language models, served together.

Each app is a module in sketches/ with a router; APPS below lists them for the sidebar and the overview page.
"""

import os

import httpx
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from common import HERE, LLM_MODEL, LLM_URL, ModelBusy, ModelError, model_choice, page
from sketches import atlas, atlas_seis, barrier, copilot, decline, detective, doctor, logs, losttime, seismic, spud, status, tieback

GROUPS = [
    {"id": "explore", "name": "Explore and appraise", "color": "#5aa8ff"},
    {"id": "drill", "name": "Drill and complete", "color": "#f5a524"},
    {"id": "produce", "name": "Produce", "color": "#2fd3b5"},
    {"id": "late", "name": "Late life and CO2", "color": "#a78bfa"},
    {"id": "data", "name": "Data and knowledge", "color": "#94a3b8"},
]
# path: URL and module; value: the money it goes after, in one line
APPS = [
    {
        "path": "detective",
        "name": "Diskos Detective",
        "group": "data",
        "tagline": "An agent over Diskos well reports and FactPages: cited answers, one-minute wellbore dossiers, "
        "and the first public DISKOS-QA scorecard.",
        "value": "Days of report digging per well review",
        "fresh": True,
        "router": detective.router,
    },
    {
        "path": "barrier",
        "name": "Barrier Ledger",
        "group": "late",
        "tagline": "Legacy wells around a CO2 store screened three ways, disagreements and data gaps shown, and each "
        "well's plugs and cement read from its file with citations.",
        "value": "NOK 50M to 1bn per P&A, 2,900 wells to go",
        "fresh": True,
        "router": barrier.router,
    },
    {
        "path": "spud",
        "name": "Spud Brief",
        "group": "drill",
        "tagline": "Before you drill: offset mud windows, leak-off tests and the hazards each offset met, as a brief "
        "in Havtil's format, backtested on real wells.",
        "value": "Well-control incidents at USD 0.4M per rig day",
        "fresh": True,
        "router": spud.router,
    },
    {
        "path": "losttime",
        "name": "Lost Time Hunter",
        "group": "drill",
        "tagline": "Reported, invisible and hidden lost time in Volve's 1,759 daily drilling reports, priced per rig "
        "day, with lessons learned cited to the report lines.",
        "value": "22% of Volve rig time is reported NPT",
        "fresh": True,
        "router": losttime.router,
    },
    {
        "path": "seismic",
        "name": "Seismic Lookalike",
        "group": "explore",
        "tagline": "Click a feature on a seismic section and find the patches that look like it from texture alone, "
        "scored on a held-out block, and explained from the numbers.",
        "value": "Weeks of manual interpretation per prospect",
        "fresh": True,
        "router": seismic.router,
    },
    {
        "path": "tieback",
        "name": "Tie-back Matchmaker",
        "group": "explore",
        "tagline": "Undeveloped discoveries ranked against the producing hosts that could take them, before the hosts "
        "close, with an outside-view production profile and a screening memo.",
        "value": "500+ million Sm³ o.e. waiting for a host",
        "fresh": True,
        "router": tieback.router,
    },
    {
        "path": "doctor",
        "name": "Data Doctor",
        "group": "data",
        "tagline": "FORCE 2020 log files, Diskos reports and FactPages cross-checked: positions, depth references and "
        "formation tops, with a trust score per wellbore.",
        "value": "Wrong inputs in every decision downstream",
        "fresh": True,
        "router": doctor.router,
    },
    {
        "path": "copilot",
        "name": "NCS Copilot",
        "group": "data",
        "tagline": "Ask the shelf in plain words: the model writes SQL over Sodir's FactPages and maps the wells.",
        "value": "Hours of data hunting per question",
        "router": copilot.router,
    },
    {
        "path": "logs",
        "name": "Log Lens",
        "group": "explore",
        "tagline": "Lithology from well logs on wells the model never saw, explained interval by interval.",
        "value": "Days of log interpretation per well",
        "router": logs.router,
    },
    {
        "path": "decline",
        "name": "Field Pulse",
        "group": "produce",
        "tagline": "Production, a decline forecast and Sodir's reserves side by side, with a field brief.",
        "value": "Reserve bias caught early",
        "router": decline.router,
    },
]

api = FastAPI(title="Subsurface Studio")
log = logging.getLogger("studio")


@api.exception_handler(ModelBusy)
async def busy(_: Request, e: ModelBusy):
    return JSONResponse({"detail": f"The model is busy (GPU reserved or held by another job): {e}"}, status_code=503)


@api.exception_handler(ModelError)
async def model_error(_: Request, e: ModelError):
    return JSONResponse({"detail": f"The model failed: {e}"}, status_code=502)


@api.exception_handler(Exception)
async def crash(request: Request, e: Exception):
    # every failure reaches the page as a sentence, and the log keeps the traceback
    log.exception("%s %s failed", request.method, request.url.path)
    return JSONResponse({"detail": f"Internal error: {type(e).__name__}: {str(e)[:300]}"}, status_code=500)

for a in APPS:
    api.include_router(a["router"])
api.include_router(status.router)
api.include_router(atlas.router)  # the data dashboard: its own page and menu, not one of the tools
api.include_router(atlas_seis.router)  # its seismic explorer


@api.get("/", response_class=HTMLResponse)
def index():
    return page("index.html")


@api.get("/api/apps")
def apps():
    return {"groups": GROUPS, "apps": [{k: v for k, v in a.items() if k != "router"} for a in APPS]}


@api.middleware("http")
async def pick_model(request: Request, call_next):
    """The model picker in the sidebar sends X-Model; every model call in this request uses it."""
    token = model_choice.set(request.headers.get("x-model", "").strip())
    try:
        return await call_next(request)
    finally:
        model_choice.reset(token)


@api.get("/api/models")
async def models():
    """The gateway's chat models (embedding models left out), for the picker."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{LLM_URL}/models")
        data = r.json().get("data", [])
    except (httpx.HTTPError, ValueError):
        data = []
    names = [m["id"] for m in data if "embed" not in m["id"] and "bge" not in m["id"]]
    return {"default": LLM_MODEL, "models": names or [LLM_MODEL]}


ASSETS = {"style.css": "text/css", "shell.js": "text/javascript", "theme.js": "text/javascript", "atlas.js": "text/javascript"}


@api.get("/{name}")
def asset(name: str):
    if name not in ASSETS:
        raise HTTPException(404)
    return Response((HERE / "pages" / name).read_text(), media_type=ASSETS[name], headers={"Cache-Control": "no-cache"})


class Prefix:
    """The proxy passes the full path (/hackathon/...). Setting root_path makes the routes match without the prefix."""

    def __init__(self, app, prefix: str):
        self.app, self.prefix = app, prefix.rstrip("/")

    async def __call__(self, scope, receive, send):
        if self.prefix and scope["type"] in ("http", "websocket") and scope["path"].startswith(self.prefix):
            scope = dict(scope, root_path=self.prefix)
        await self.app(scope, receive, send)


app = Prefix(api, os.environ.get("ROOT_PATH", ""))
