"""What every app shares: settings from the environment, the model calls, embeddings, the FactPages database and
the wellbore lookups."""

import asyncio
import contextvars
import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path

import duckdb
import httpx

LLM_URL = os.environ.get("LLM_URL", "http://llm.llm/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3.6-35b")
EMBED_URL = os.environ.get("EMBED_URL", "http://llm-cpu.llm/v1")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "bge-m3")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant.qdrant:6333")
HERE = Path(__file__).parent
# the repo's data/ folder unless the pod says otherwise
DATA_DIR = Path(os.environ.get("DATA_DIR") or HERE.parent / "data")
DB = DATA_DIR / "ncs.duckdb"

# the model a request asked for (header X-Model, set from the picker in the sidebar); empty means LLM_MODEL
model_choice: contextvars.ContextVar[str] = contextvars.ContextVar("model_choice", default="")


class ModelBusy(Exception):
    """The GPU is reserved or held by another consumer (the gateway answers 503)."""


class ModelError(Exception):
    """The model answered with an error, or could not be reached."""


def current_model() -> str:
    return model_choice.get() or LLM_MODEL


async def complete(messages: list[dict], *, think: bool = False, max_tokens: int = 1500, tools: list | None = None,
                   schema: dict | None = None, model: str | None = None, temperature: float = 0.2) -> dict:
    """One chat completion; returns the message (content, tool_calls). The first call after a while waits for the
    model to load on the GPU (up to a minute or two)."""
    body = {
        "model": model or current_model(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": think},
    }
    if tools:
        body["tools"] = tools
    if schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "answer", "schema": schema}}
    r = None
    for attempt in range(3):  # the gateway can drop a connection while it swaps models; try again, then give up
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=15)) as c:
                r = await c.post(f"{LLM_URL}/chat/completions", json=body)
            if r.status_code not in (502, 504):
                break
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
            if attempt == 2:
                raise ModelError(f"model {body['model']} unreachable: {e}") from e
        await asyncio.sleep(3 * (attempt + 1))
    assert r is not None
    if r.status_code == 503:
        raise ModelBusy(r.text.strip()[:300] or "the model is busy")
    if r.status_code >= 400:
        raise ModelError(f"model {body['model']}: HTTP {r.status_code}: {r.text[:300]}")
    msg = r.json()["choices"][0]["message"]
    msg["content"] = re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S).strip()
    return msg


async def chat(messages: list[dict], **kw) -> str:
    return (await complete(messages, **kw))["content"]


async def chat_json(messages: list[dict], schema: dict, **kw):
    """A reply that follows a JSON schema (llama.cpp turns the schema into a grammar). A reply cut off by the token
    limit is not valid JSON: try once more with twice the room."""
    for attempt in range(2):
        text = await chat(messages, schema=schema, **kw)
        m = re.search(r"[\[{].*[\]}]", text, re.S)
        try:
            return json.loads(m.group(0) if m else text)
        except json.JSONDecodeError:
            kw["max_tokens"] = kw.get("max_tokens", 1500) * 2
    raise ModelError("the model's reply was not valid JSON twice")


def save_json(path: Path, data) -> None:
    """Write a cache file atomically, so a crash or a parallel request never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {} if default is None else default


async def embed(texts: list[str], batch: int = 16) -> list[list[float]]:
    out = []
    async with httpx.AsyncClient(timeout=600) as c:
        for i in range(0, len(texts), batch):
            r = await c.post(f"{EMBED_URL}/embeddings", json={"model": EMBED_MODEL, "input": texts[i : i + batch]})
            r.raise_for_status()
            out += [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]
    return out


def page(name: str) -> str:
    return (HERE / "pages" / name).read_text()


# -- the FactPages database --


def ncs():
    """Read-only connection to the FactPages tables (fetch_data.py sodir builds it)."""
    return duckdb.connect(str(DB), read_only=True)


def rows(sql: str, *args) -> list[dict]:
    with ncs() as db:
        cur = db.execute(sql, list(args))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def norm(name: str) -> str:
    """One spelling for a wellbore name: 'NO 15/9-F-12', '15/9-F- 12' and '15/9 F 12' all become '15/9-F-12'."""
    s = re.sub(r"^\s*NO\s+", "", str(name).upper()).strip()
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s


@lru_cache(maxsize=1)
def _wellbores() -> tuple[dict, ...]:
    return tuple(
        rows(
            "select wlbWellboreName as name, wlbWell as well, wlbDrillingOperator as operator, wlbPurpose as purpose, "
            "wlbStatus as status, wlbContent as content, 'exploration' as kind, wlbEntryDate as entry, "
            "wlbCompletionDate as completion, wlbField as field, wlbDiscovery as discovery, wlbTotalDepth as td, "
            "wlbWaterDepth as water_depth, wlbKellyBushElevation as kb, wlbFinalVerticalDepth as tvd, "
            "wlbFormationAtTd as formation_td, wlbAgeAtTd as age_td, wlbMainArea as area, "
            "wlbNsDecDeg as lat, wlbEwDecDeg as lon, wlbNsUtm as north, wlbEwUtm as east, wlbUtmZone as zone, "
            "wlbNpdidWellbore as npdid, wlbFactPageUrl as url from wellbore_exploration "
            "union all by name "
            "select wlbWellboreName as name, wlbWell as well, wlbDrillingOperator as operator, wlbPurpose as purpose, "
            "wlbStatus as status, wlbContent as content, 'development' as kind, wlbEntryDate as entry, "
            "wlbCompletionDate as completion, wlbField as field, wlbDiscovery as discovery, wlbTotalDepth as td, "
            "wlbWaterDepth as water_depth, wlbKellyBushElevation as kb, wlbFinalVerticalDepth as tvd, "
            "null as formation_td, null as age_td, wlbMainArea as area, "
            "wlbNsDecDeg as lat, wlbEwDecDeg as lon, wlbNsUtm as north, wlbEwUtm as east, wlbUtmZone as zone, "
            "wlbNpdidWellbore as npdid, wlbFactPageUrl as url from wellbore_development"
        )
    )


def wellbores() -> tuple[dict, ...]:
    return _wellbores()


@lru_cache(maxsize=1)
def _by_name() -> dict:
    return {norm(w["name"]): w for w in _wellbores()}


def wellbore(name: str) -> dict | None:
    return _by_name().get(norm(name))


def km(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def nearby(lat: float, lon: float, radius: float, limit: int = 50) -> list[dict]:
    out = []
    for w in _wellbores():
        if w["lat"] is not None and w["lon"] is not None:
            d = km(lat, lon, w["lat"], w["lon"])
            if d <= radius:
                out.append({**w, "km": round(d, 2)})
    return sorted(out, key=lambda w: w["km"])[:limit]


def plain(v):
    """A JSON-safe value (dates as ISO text, NaN as None)."""
    if isinstance(v, str):
        return v.strip()  # FactPages pads some text columns with spaces
    if v is None or isinstance(v, (bool, int)):
        return v
    if isinstance(v, float):
        return None if math.isnan(v) else v
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def clean(d: dict) -> dict:
    return {k: plain(v) for k, v in d.items()}
