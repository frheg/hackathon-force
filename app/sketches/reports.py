"""Search a versioned corpus of DISKOS-QA gold passages and sampled official OCR passages.

Keyword (BM25) finds exact names that embeddings blur; vectors (bge-m3 in Qdrant) find meaning. Reciprocal rank
fusion merges them. The default corpus is deliberately a haystack: deterministic, document-stratified OCR distractors
are streamed from the 5.3 GB official CSV instead of searching only the 1,690 gold passages supplied with QA.

    uv run python -m sketches.reports --distractors 5000 --seed 2026

Set ``DISKOS_DISTRACTORS`` and ``DISKOS_SAMPLE_SEED`` to change the build defaults. A manifest beside the chunks and
collection payloads records provenance, counts, parameters and the corpus/index version.
"""

import argparse
import ast
import asyncio
import hashlib
import heapq
import json
import math
import os
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import httpx
import pandas as pd

from common import DATA_DIR, QDRANT_URL, embed, norm, rows

D = DATA_DIR / "diskosqa"
CHUNKS = D / "chunks.parquet"
MANIFEST = D / "chunks.manifest.json"
OFFICIAL_CSV = DATA_DIR / "official" / "text" / "Norway - Diskos reports.csv"
COLLECTION = "diskos_chunks"
CORPUS_VERSION = 2
DEFAULT_DISTRACTORS = int(os.environ.get("DISKOS_DISTRACTORS", "5000"))
DEFAULT_SEED = int(os.environ.get("DISKOS_SAMPLE_SEED", "2026"))
WORD = re.compile(r"[a-z0-9æøå]+(?:[/.-][a-z0-9]+)*")
TRUE_VALUES = {"1", "true", "t", "yes", "y"}


def lists(cell) -> list:
    try:
        value = ast.literal_eval(cell) if isinstance(cell, str) else []
        return value if isinstance(value, list) else []
    except (ValueError, SyntaxError, TypeError):
        return []


def _clean(cell) -> str:
    return "" if pd.isna(cell) else str(cell).strip()


def _flag(cell) -> bool:
    return _clean(cell).lower() in TRUE_VALUES


def _names(cell) -> list[str]:
    text = _clean(cell)
    return [part.strip() for part in re.split(r"[,;|]", text) if part.strip()] if text else []


def _text_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def natural_language(text: str) -> bool:
    """Conservative OCR gate; the CSV language flag is necessary but not sufficient."""
    text = text.strip()
    words = re.findall(r"[^\W\d_]{2,}", text, re.UNICODE)
    if len(text) < 100 or len(words) < 16:
        return False
    if sum(ch.isalpha() or ch.isspace() for ch in text) / max(len(text), 1) < 0.55:
        return False
    common = {"the", "and", "of", "to", "in", "was", "were", "is", "are", "this", "from", "for",
              "og", "av", "til", "med", "den", "det", "som", "var"}
    return bool(common.intersection(w.casefold() for w in words)) and len(set(w.casefold() for w in words)) >= 8


def _gold_passages(qa_csv: Path) -> tuple[list[dict], dict]:
    qa = pd.read_csv(qa_csv)
    seen = {}
    for _, r in qa.iterrows():
        texts, ids, docs, names = lists(r.Content), lists(r.Chunk_IDs), lists(r.Document_name), lists(r.Document_id)
        wbs, fields, fms = lists(r.Wellbore_names), lists(r.Field_names), lists(r.Formation_names)
        for i, cid in enumerate(ids):
            if str(cid) in seen or i >= len(texts):
                continue
            text = str(texts[i]).strip()
            if not text:
                continue
            seen[str(cid)] = {
                "chunk_id": str(cid), "text": text, "source": "gold",
                "doc_name": str(docs[i]).strip() if i < len(docs) else "",
                "doc_id": str(names[i]).strip() if i < len(names) else "",
                "page": None,
                "wellbores": [norm(w) for w in (wbs[i] if i < len(wbs) else [])],
                "fields": list(fields[i]) if i < len(fields) else [],
                "formations": list(fms[i]) if i < len(fms) else [],
            }
    return list(seen.values()), {"questions": len(qa), "questions_supported": int((qa.Entailed == True).sum())}  # noqa: E712


def _distractor_from_row(r: dict, priority: int, known_docs: dict[str, dict]) -> dict | None:
    raw = _clean(r.get("content_scrubbed_light")) or _clean(r.get("content"))
    raw_flag = _flag(r.get("content_could_be_natural_language"))
    light_flag = _flag(r.get("content_scrubbed_light_could_be_natural_language"))
    if not (raw_flag or light_flag) or not natural_language(raw):
        return None
    document = _clean(r.get("TITLE")) or _clean(r.get("filename"))
    known = known_docs.get(document.casefold(), {})
    wb = _names(r.get("WELLBORE NAME"))
    fields = _names(r.get("FIELD NAME") or r.get("FIELD")) or list(known.get("fields", []))
    formations = _names(r.get("FORMATION NAME") or r.get("FORMATION")) or list(known.get("formations", []))
    return {
        "chunk_id": "ocr-" + hashlib.sha256(f"{r.get('_id', '')}:{r.get('page', '')}:{raw}".encode()).hexdigest()[:24],
        "text": raw, "source": "official_ocr", "doc_name": document, "doc_id": _clean(r.get("_id")),
        "page": _clean(r.get("page")) or None,
        "wellbores": [norm(w) for w in (wb or known.get("wellbores", []))],
        "fields": fields, "formations": formations, "_priority": priority,
    }


def sample_distractors(official_csv: Path, gold: list[dict], limit: int = DEFAULT_DISTRACTORS,
                       seed: int = DEFAULT_SEED, chunksize: int = 1000) -> list[dict]:
    """Stream a bounded, deterministic hash sample, taking at most one representative per document first."""
    if limit <= 0:
        return []
    gold_texts = {_text_key(p["text"]) for p in gold}
    known_docs: dict[str, dict] = {}
    for p in gold:
        if p["doc_name"]:
            d = known_docs.setdefault(p["doc_name"].casefold(), {"wellbores": [], "fields": [], "formations": []})
            for key in ("wellbores", "fields", "formations"):
                d[key] = sorted(set(d[key]) | set(p[key]))
    capacity = max(limit * 2, 100)
    smallest: list[tuple[int, str, dict]] = []
    representatives: dict[str, dict] = {}
    for frame in pd.read_csv(official_csv, chunksize=chunksize, low_memory=False):
        for r in frame.to_dict("records"):
            raw = _clean(r.get("content_scrubbed_light")) or _clean(r.get("content"))
            key = _text_key(raw)
            if not key or key in gold_texts:
                continue
            identity = f"{r.get('_id', '')}\0{r.get('page', '')}\0{key}"
            digest = hashlib.sha256(f"{seed}\0{identity}".encode()).digest()
            priority = int.from_bytes(digest[:8], "big")
            item = _distractor_from_row(r, priority, known_docs)
            if item is None:
                continue
            doc = item["doc_name"].casefold() or item["doc_id"].casefold()
            old = representatives.get(doc)
            if old is None or priority < old["_priority"]:
                representatives[doc] = item
            entry = (-priority, item["chunk_id"], item)
            if len(smallest) < capacity:
                heapq.heappush(smallest, entry)
            elif entry[0] > smallest[0][0]:
                heapq.heapreplace(smallest, entry)

    candidates = list(representatives.values()) + [entry[2] for entry in smallest]
    candidates.sort(key=lambda x: (x["_priority"], x["chunk_id"]))
    reps = {p["chunk_id"]: p for p in representatives.values()}
    ordered = sorted(reps.values(), key=lambda x: (x["_priority"], x["chunk_id"]))
    ordered.extend(p for p in candidates if p["chunk_id"] not in reps)
    out, seen_texts, seen_ids = [], set(), set()
    for p in ordered:
        key, cid = _text_key(p["text"]), p["chunk_id"]
        if key in gold_texts or key in seen_texts or cid in seen_ids:
            continue
        clean = {k: v for k, v in p.items() if not k.startswith("_")}
        out.append(clean)
        seen_texts.add(key)
        seen_ids.add(cid)
        if len(out) == limit:
            break
    return out


def corpus_digest(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    for r in df.to_dict("records"):
        h.update(json.dumps({k: r[k] for k in sorted(r)}, sort_keys=True, default=str).encode())
        h.update(b"\n")
    return h.hexdigest()


def write_manifest(metadata: dict, path: Path = MANIFEST) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")


def corpus_metadata(df: pd.DataFrame | None = None) -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    if df is None:
        df = pd.read_parquet(CHUNKS)
    sources = df.source.value_counts().to_dict() if "source" in df else {"gold": len(df)}
    return {"corpus_version": CORPUS_VERSION, "corpus_sha256": corpus_digest(df),
            "sources": sources, "gold_count": int(sources.get("gold", 0)),
            "distractor_count": int(sources.get("official_ocr", 0)), "passages": len(df)}


def build_chunks(distractor_limit: int = DEFAULT_DISTRACTORS, seed: int = DEFAULT_SEED,
                 official_csv: Path = OFFICIAL_CSV, qa_csv: Path | None = None,
                 chunks_path: Path = CHUNKS, manifest_path: Path = MANIFEST,
                 chunksize: int = 1000) -> pd.DataFrame:
    qa_csv = qa_csv or D / "diskos_qa.csv"
    gold, qa_stats = _gold_passages(Path(qa_csv))
    distractors = sample_distractors(Path(official_csv), gold, int(distractor_limit), int(seed), chunksize)
    columns = ["chunk_id", "text", "source", "doc_name", "doc_id", "page", "wellbores", "fields", "formations"]
    df = pd.DataFrame(gold + distractors).reindex(columns=columns)
    df["document"] = df["doc_name"]
    Path(chunks_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(chunks_path, index=False)
    metadata = {
        "corpus_version": CORPUS_VERSION, "passages": len(df), "gold_count": len(gold),
        "distractor_count": len(distractors), "distractor_limit": int(distractor_limit),
        "sampling_seed": int(seed), "sampling": "sha256-priority; one representative per document, then globally smallest hashes",
        "qa_supported": qa_stats["questions_supported"], "qa_excluded": qa_stats["questions"] - qa_stats["questions_supported"],
        "qa_questions": qa_stats["questions"], "corpus_sha256": corpus_digest(df),
        "sources": {"qa": str(qa_csv), "official_ocr": str(official_csv)},
    }
    write_manifest(metadata, Path(manifest_path))
    return df


async def build_index(distractor_limit: int = DEFAULT_DISTRACTORS, seed: int = DEFAULT_SEED) -> None:
    df = build_chunks(distractor_limit, seed)
    metadata = corpus_metadata(df)
    print(f"{len(df)} passages ({metadata['gold_count']} gold, {metadata['distractor_count']} official OCR) "
          f"from {df.doc_name.nunique()} documents; corpus {metadata['corpus_sha256'][:12]}")
    vectors = await embed([t[:6000] for t in df.text.tolist()])
    async with httpx.AsyncClient(timeout=120) as c:
        await c.delete(f"{QDRANT_URL}/collections/{COLLECTION}")
        r = await c.put(f"{QDRANT_URL}/collections/{COLLECTION}", json={"vectors": {"size": len(vectors[0]), "distance": "Cosine"}})
        r.raise_for_status()
        for i in range(0, len(df), 256):
            points = []
            for j in range(i, min(i + 256, len(df))):
                row = df.iloc[j]
                payload = {
                    "chunk_id": row.chunk_id, "source": row.source, "document": row.doc_name,
                    "doc_name": row.doc_name, "doc_id": row.doc_id, "page": row.page,
                    "wellbores": list(row.wellbores), "fields": list(row.fields), "formations": list(row.formations),
                    "corpus_version": CORPUS_VERSION, "corpus_sha256": metadata["corpus_sha256"], "text_sha256": hashlib.sha256(row.text.encode()).hexdigest(),
                }
                points.append({"id": int(j), "vector": vectors[j], "payload": payload})
            r = await c.put(f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true", json={"points": points})
            r.raise_for_status()
    indexed = {**metadata, "index_version": 2, "collection": COLLECTION, "embedding_dimensions": len(vectors[0])}
    write_manifest(indexed)
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
    if "source" not in df:
        df["source"] = "gold"
    if "page" not in df:
        df["page"] = None
    if "document" not in df:
        df["document"] = df["doc_name"]
    return df, BM25((df.doc_name.fillna("") + " " + df.text).tolist())


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


async def vector_ranks(query: str, limit: int = 60, sources: set[str] | None = None) -> list[int]:
    if query not in _qcache:  # the scorecard asks the same question in several modes
        _qcache[query] = (await embed([query]))[0]
    body: dict = {"vector": _qcache[query], "limit": limit}
    if sources:
        body["filter"] = {"must": [{"key": "source", "match": {"any": sorted(sources)}}]}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{QDRANT_URL}/collections/{COLLECTION}/points/search", json=body)
        r.raise_for_status()
    return [int(p["id"]) for p in r.json()["result"]]


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


async def search(query: str, k: int = 6, mode: str = "hybrid", ents: dict | None = None,
                 sources: set[str] | None = None) -> list[dict]:
    """Search the indexed corpus; ``sources`` is intended only for comparing the gold-only benchmark haystack."""
    df, bm = corpus()
    allowed = [i for i, source in enumerate(df.source) if not sources or source in sources]
    allowed_set = set(allowed)
    ranked: dict[int, float] = {}
    vec = await vector_ranks(query, sources=sources)
    for r, i in enumerate(vec):
        if i in allowed_set:
            ranked[i] = ranked.get(i, 0) + 1 / (60 + r)
    if mode in ("hybrid", "filtered"):
        s = bm.scores(query)
        lex = sorted(allowed, key=lambda i: -s[i])[:60]
        for r, i in enumerate(lex):
            ranked[i] = ranked.get(i, 0) + 1 / (60 + r)
    order = sorted(ranked, key=lambda i: -ranked[i])
    if mode == "filtered":
        ents = ents if ents is not None else entities(query)
        kept = [i for i in order if matches(df.iloc[i], ents)]
        if not kept:  # nothing in the named entities: fall back to the selected corpus, not privileged QA content
            s = bm.scores(query)
            kept = [i for i in sorted(allowed, key=lambda i: -s[i]) if matches(df.iloc[i], ents)][:k] or order
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
        "source": getattr(row, "source", "gold"),
        "document": row.doc_name,
        "doc_name": row.doc_name,
        "doc_id": _clean(getattr(row, "doc_id", "")),
        "page": (None if pd.isna(getattr(row, "page", None)) else str(getattr(row, "page", None))),
        "wellbores": list(row.wellbores),
        "fields": list(row.fields),
        "formations": list(row.formations),
        "text": row.text,
        "score": round(float(score), 4),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--distractors", type=int, default=DEFAULT_DISTRACTORS,
                   help="maximum official OCR passages (0 makes a gold-only compatibility corpus)")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--chunks-only", action="store_true", help="build parquet and manifest without mutating Qdrant")
    args = p.parse_args()
    if args.chunks_only:
        build_chunks(args.distractors, args.seed)
    else:
        asyncio.run(build_index(args.distractors, args.seed))


if __name__ == "__main__":
    main()
