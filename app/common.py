"""What every sketch shares: settings from the pod's environment and one way to ask the model."""

import os
import re
from pathlib import Path

import httpx

LLM_URL = os.environ.get("LLM_URL", "http://llm.llm/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3.6-35b")
HERE = Path(__file__).parent
# the repo's data/ folder unless the pod says otherwise
DATA_DIR = Path(os.environ.get("DATA_DIR") or HERE.parent / "data")


class ModelBusy(Exception):
    """The GPU is reserved or held by another consumer (the gateway answers 503)."""


async def chat(messages: list[dict], *, think: bool = False, max_tokens: int = 1500) -> str:
    # the first call after a while waits for the model to load on the GPU (up to a minute or two)
    body = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": think},
    }
    async with httpx.AsyncClient(timeout=300) as c:
        r = await c.post(f"{LLM_URL}/chat/completions", json=body)
    if r.status_code == 503:
        raise ModelBusy(r.text.strip() or "the model is busy")
    r.raise_for_status()
    text = r.json()["choices"][0]["message"].get("content") or ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def page(name: str) -> str:
    return (HERE / "pages" / name).read_text()
