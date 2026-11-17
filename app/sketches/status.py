"""Checks every connection the pod has: the model, embeddings, Postgres, Qdrant, SearXNG, the internet, the data."""

import asyncio
import os

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from common import DATA_DIR, LLM_URL, page

router = APIRouter(prefix="/status")
EMBED_URL = os.environ.get("EMBED_URL", "http://llm-cpu.llm/v1")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant.qdrant:6333")
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng.searxng")


async def get(url: str) -> str:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url)
        r.raise_for_status()
        return f"HTTP {r.status_code}"


async def postgres() -> str:
    import psycopg

    async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"], connect_timeout=5) as db:
        row = await (await db.execute("select current_database(), version()")).fetchone()
        return f"{row[0]}: {row[1].split(' on ')[0]}"


async def data() -> str:
    found = sorted(p.name for p in DATA_DIR.iterdir()) if DATA_DIR.is_dir() else []
    return f"{DATA_DIR}: {', '.join(found) or 'empty'}"


@router.get("")
def slash():
    return RedirectResponse("status/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("status.html")


@router.get("/api")
async def status():
    checks = {
        "llm": get(f"{LLM_URL}/models"),
        "embeddings": get(f"{EMBED_URL}/models"),
        "postgres": postgres(),
        "qdrant": get(f"{QDRANT_URL}/collections"),
        "searxng": get(f"{SEARXNG_URL}/healthz"),
        "internet": get("https://pypi.org/simple/fastapi/"),
        "data": data(),
    }
    results = await asyncio.gather(*checks.values(), return_exceptions=True)
    return {
        k: {"ok": not isinstance(v, Exception), "detail": f"{type(v).__name__}: {v}" if isinstance(v, Exception) else v}
        for k, v in zip(checks, results)
    }
