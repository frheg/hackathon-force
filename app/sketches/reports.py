"""Search over the Diskos report text: the passages in DISKOS-QA (or the event's chunk set), indexed two ways.

Keyword (BM25) finds exact well, formation and tool names that embeddings blur; vectors (bge-m3 in Qdrant) find the
meaning. Reciprocal rank fusion merges them. An entity filter keeps passages about the wells, fields and formations
the question names, which is the idea DISKOS-QA itself was built on.

    uv run python -m sketches.reports        builds data/diskosqa/chunks.parquet and the Qdrant collection
"""

import ast
import asyncio
import math
import re
from collections import Counter
from functools import lru_cache

import httpx
import pandas as pd

from common import DATA_DIR, QDRANT_URL, embed, norm, rows

D = DATA_DIR / "diskosqa"
CHUNKS = D / "chunks.parquet"
COLLECTION = "diskos_chunks"
WORD = re.compile(r"[a-z0-9æøå]+(?:[/.-][a-z0-9]+)*")


def lists(cell) -> list:
    try:
        return ast.literal_eval(cell) if isinstance(cell, str) else []
    except (ValueError, SyntaxError):
        return []


def build_chunks() -> pd.DataFrame:
    qa = pd.read_csv(D / "diskos_qa.csv")
    seen = {}
    for _, r in qa.iterrows():
        texts, ids, docs, names = lists(r.Content), lists(r.Chunk_IDs), lists(r.Document_name), lists(r.Document_id)
        wbs, fields, fms = lists(r.Wellbore_names), lists(r.Field_names), lists(r.Formation_names)
        for i, cid in enumerate(ids):
            if cid in seen or i >= len(texts):
                continue
            seen[cid] = {
                "chunk_id": str(cid),
                "text": texts[i],
                "doc_name": docs[i] if i < len(docs) else "",
                "doc_id": names[i] if i < len(names) else "",
                "wellbores": [norm(w) for w in (wbs[i] if i < len(wbs) else [])],
                "fields": list(fields[i]) if i < len(fields) else [],
                "formations": list(fms[i]) if i < len(fms) else [],
            }
    df = pd.DataFrame(list(seen.values()))
    df.to_parquet(CHUNKS, index=False)
    return df


async def build_index() -> None:
    df = build_chunks()
    print(f"{len(df)} passages from {df.doc_name.nunique()} documents")
    vectors = await embed([t[:6000] for t in df.text.tolist()])
    async with httpx.AsyncClient(timeout=120) as c:
        await c.delete(f"{QDRANT_URL}/collections/{COLLECTION}")
        r = await c.put(f"{QDRANT_URL}/collections/{COLLECTION}", json={"vectors": {"size": len(vectors[0]), "distance": "Cosine"}})
        r.raise_for_status()
        for i in range(0, len(df), 256):
            points = [
                {"id": int(j), "vector": vectors[j], "payload": {"chunk_id": df.chunk_id[j]}}
                for j in range(i, min(i + 256, len(df)))
            ]
            r = await c.put(f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true", json={"points": points})
            r.raise_for_status()
    print(f"indexed {len(df)} vectors of {len(vectors[0])} dimensions")


# -- search --


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.4, b: float = 0.75):
        self.toks = [WORD.findall(d.lower()) for d in docs]
        self.len = [len(t) for t in self.toks]
        self.avg = sum(self.len) / max(len(self.len), 1)
        self.tf = [Counter(t) for t in self.toks]
        df = Counter(w for t in self.tf for w in t)
        n = len(docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query: str) -> list[float]:
        q = WORD.findall(query.lower())
        out = []
        for tf, ln in zip(self.tf, self.len):
            s = 0.0
            for w in q:
                f = tf.get(w)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * ln / self.avg))
            out.append(s)
        return out


@lru_cache(maxsize=1)
def corpus():
    df = pd.read_parquet(CHUNKS)
    return df, BM25((df.doc_name + " " + df.text).tolist())


@lru_cache(maxsize=1)
def vocab() -> dict:
    """Names to look for in a question: fields and formations from FactPages, wellbores from the corpus and FactPages."""
    df, _ = corpus()
    fields = {r["fldName"] for r in rows("select fldName from field")} | {f for fs in df.fields for f in fs}
    units = {r["lsuName"] for r in rows("select lsuName from strat_litho_overview")} | {f for fs in df.formations for f in fs}
    return {"fields": sorted(fields, key=len, reverse=True), "formations": sorted(units, key=len, reverse=True)}


def entities(text: str) -> dict:
    """Wellbores, fields and formations named in a question ('Sandnes Formation' matches 'SANDNES FM')."""
    up = " " + re.sub(r"\s+", " ", text.upper()) + " "
    up = re.sub(r"\bFORMATION\b", "FM", re.sub(r"\bGROUP\b", "GP", up))
    up = re.sub(r"[^\w/ -]", " ", up)  # "Sandnes Formation?" must still match "SANDNES FM"
    wbs = {norm(m) for m in re.findall(r"\b\d{1,2}/\d{1,2}-[A-Z]?-?\d{1,3}(?:\s?[A-Z](?:T\d)?)?(?:\s?ST\d)?\b", text.upper())}
    found = {"wellbores": sorted(wbs), "fields": [], "formations": []}
    v = vocab()
    for key in ("fields", "formations"):
        for name in v[key]:
            if len(name) > 2 and f" {name} " in up:
                found[key].append(name)
                up = up.replace(f" {name} ", " ")
    return found


_qcache: dict[str, list[float]] = {}


async def vector_ranks(query: str, limit: int = 60) -> list[int]:
    if query not in _qcache:  # the scorecard asks the same question in several modes
        _qcache[query] = (await embed([query]))[0]
    v = _qcache[query]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{QDRANT_URL}/collections/{COLLECTION}/points/search", json={"vector": v, "limit": limit})
        r.raise_for_status()
    return [p["id"] for p in r.json()["result"]]


def matches(row, ents: dict) -> bool:
    if not any(ents.values()):
        return True
    wb = set(row.wellbores)
    # a wellbore also matches its well (9/2-1 covers 9/2-1 A)
    if any(w in wb or any(x.startswith(w + " ") for x in wb) for w in ents["wellbores"]):
        return True
    if set(ents["fields"]) & set(row.fields) or set(ents["formations"]) & set(row.formations):
        return True
    return False


async def search(query: str, k: int = 6, mode: str = "hybrid", ents: dict | None = None) -> list[dict]:
    """mode: 'vector' (embeddings only), 'hybrid' (BM25 + vector), 'filtered' (hybrid inside the named entities)."""
    df, bm = corpus()
    ranked: dict[int, float] = {}
    vec = await vector_ranks(query)
    for r, i in enumerate(vec):
        ranked[i] = ranked.get(i, 0) + 1 / (60 + r)
    if mode in ("hybrid", "filtered"):
        s = bm.scores(query)
        for r, i in enumerate(sorted(range(len(s)), key=lambda i: -s[i])[:60]):
            ranked[i] = ranked.get(i, 0) + 1 / (60 + r)
    order = sorted(ranked, key=lambda i: -ranked[i])
    if mode == "filtered":
        ents = ents if ents is not None else entities(query)
        kept = [i for i in order if matches(df.iloc[i], ents)]
        if not kept:  # nothing in the named entities: fall back to everything, so the answer can still be found
            s = bm.scores(query)
            kept = [i for i in sorted(range(len(s)), key=lambda i: -s[i]) if matches(df.iloc[i], ents)][:k] or order
        order = kept
    return [passage(df.iloc[i], n + 1, ranked.get(i, 0)) for n, i in enumerate(order[:k])]


def for_wellbore(name: str, query: str = "", k: int = 8) -> list[dict]:
    """Passages about one wellbore (or its well), best matching the query first."""
    df, bm = corpus()
    w = norm(name)
    idx = [i for i, wbs in enumerate(df.wellbores) if w in wbs or any(x.split(" ")[0] == w.split(" ")[0] for x in wbs)]
    if query:
        s = bm.scores(query)
        idx.sort(key=lambda i: -s[i])
    return [passage(df.iloc[i], n + 1, 0) for n, i in enumerate(idx[:k])]


def passage(row, n: int, score: float) -> dict:
    return {
        "ref": f"S{n}",
        "chunk_id": row.chunk_id,
        "document": row.doc_name,
        "wellbores": list(row.wellbores),
        "fields": list(row.fields),
        "formations": list(row.formations),
        "text": row.text,
        "score": round(float(score), 4),
    }


if __name__ == "__main__":
    asyncio.run(build_index())
