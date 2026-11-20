"""The DISKOS-QA scorecard, with explicit gold-only and distractor-inclusive retrieval metrics.

    uv run python -m sketches.scorecard retrieval
    uv run python -m sketches.scorecard answers --n 40

``retrieval`` reports the historical gold-only comparison and the defensible ``full_haystack`` result separately.
The latter searches all indexed gold and official OCR passages; no question's Content is injected at query time.
Citation precision and claim-trace coverage are cheap diagnostics attached to model-answer examples.
"""

import argparse
import asyncio
import json
import re
import time
from collections import defaultdict
from datetime import date

import pandas as pd

from common import DATA_DIR, chat_json, current_model
from sketches import detective, reports

D = DATA_DIR / "diskosqa"
OUT = D / "scorecard.json"
MODES = ["vector", "hybrid", "filtered"]
ANSWER_MODES = ["closed", "vector", "filtered", "agent"]


def load() -> pd.DataFrame:
    qa = pd.read_csv(D / "diskos_qa.csv")
    qa = qa[qa.Entailed == True].copy()  # noqa: E712 - pandas
    qa["gold"] = qa.Chunk_IDs.map(lambda c: {str(x) for x in reports.lists(c)})
    return qa


def saved() -> dict:
    return json.loads(OUT.read_text()) if OUT.exists() else {}


async def retrieval() -> dict:
    qa = load()
    metadata = reports.corpus_metadata(reports.corpus()[0])
    full_available = (metadata.get("distractor_count", 0) > 0 and metadata.get("index_version") == 2)
    out = {"gold_haystack": {}, "full_haystack": {}}
    variants = [("gold_haystack", {"gold"})]
    if full_available:
        variants.append(("full_haystack", None))
    else:
        print("full_haystack skipped: corpus index has not been rebuilt with OCR distractors; gold metrics are comparison-only")
    for haystack, source_filter in variants:
        for mode in MODES:
            hits1 = hits5 = 0
            rr = 0.0
            by_topic = defaultdict(lambda: [0, 0])
            t0 = time.time()
            for _, q in qa.iterrows():
                found = await reports.search(q.Question, k=10, mode=mode, sources=source_filter)
                ranks = [i for i, p in enumerate(found) if p["chunk_id"] in q.gold]
                first = ranks[0] if ranks else None
                hits1 += first == 0
                hits5 += first is not None and first < 5
                rr += 1 / (first + 1) if first is not None else 0
                by_topic[q.Topic][0] += first is not None and first < 5
                by_topic[q.Topic][1] += 1
            n = len(qa)
            out[haystack][mode] = {
                "recall_at_1": round(hits1 / n, 3), "recall_at_5": round(hits5 / n, 3),
                "mrr_at_10": round(rr / n, 3),
                "by_topic": {t: round(h / c, 3) for t, (h, c) in sorted(by_topic.items())},
                "n": n, "seconds": round(time.time() - t0),
            }
            print(haystack, mode, out[haystack][mode]["recall_at_5"], out[haystack][mode]["mrr_at_10"])
    return out


JUDGE = {
    "type": "object",
    "properties": {"correct": {"type": "boolean"}, "why": {"type": "string"}},
    "required": ["correct", "why"],
}


async def judge(question: str, reference: str, answer: str) -> dict:
    return await chat_json(
        [
            {
                "role": "system",
                "content": "You grade answers about well reports. An answer is correct when it states the same facts "
                "as the reference (numbers within rounding, same units or a correct conversion); extra correct detail "
                "is fine; saying the evidence is missing is incorrect. Reply in JSON.",
            },
            {"role": "user", "content": f"Question: {question}\nReference: {reference}\nAnswer: {answer}"},
        ],
        JUDGE,
        max_tokens=300,
    )


def citation_metrics(answer: str, sources: list[dict]) -> dict:
    available = {p.get("ref") for p in sources if p.get("ref")}
    cited = set(re.findall(r"\[S\d+\]", answer))
    available_cites = {f"[{ref}]" for ref in available}
    claims = [s for s in detective.sentences(answer) if s]
    traced = sum(bool(re.search(r"\[(?:S\d+|F:[A-Za-z0-9_]+)\]", s)) for s in claims)
    return {
        "citation_precision": round(len(cited & available_cites) / len(cited), 3) if cited else 0.0,
        "claim_trace_coverage": round(traced / len(claims), 3) if claims else 0.0,
        "cited_sources": sorted(cited), "unknown_citations": sorted(cited - available_cites),
    }


async def answers(n: int, modes: list[str]) -> dict:
    qa = load()
    per_topic = max(1, n // qa.Topic.nunique())
    # a stratified sample; groupby().apply would drop the Topic column in pandas 3
    sample = pd.concat([g.sample(min(len(g), per_topic), random_state=7) for _, g in qa.groupby("Topic")])
    out, rows_ = {}, []
    for mode in modes:
        ok, secs = 0, 0.0
        citation_precision, trace_coverage = 0.0, 0.0
        by_topic = defaultdict(lambda: [0, 0])
        for _, q in sample.iterrows():
            r = await (detective.agent(q.Question) if mode == "agent" else detective.rag(q.Question, mode))
            j = await judge(q.Question, q.Answer, r["answer"])
            cited = {p["chunk_id"] for p in r["sources"]}
            metrics = citation_metrics(r["answer"], r["sources"])
            citation_precision += metrics["citation_precision"]
            trace_coverage += metrics["claim_trace_coverage"]
            ok += bool(j["correct"])
            secs += r["seconds"]
            by_topic[q.Topic][0] += bool(j["correct"])
            by_topic[q.Topic][1] += 1
            rows_.append({"mode": mode, "id": q.Question_ID, "topic": q.Topic, "question": q.Question, "reference": q.Answer,
                          "answer": r["answer"], "correct": bool(j["correct"]), "why": j.get("why", ""),
                          "gold_found": bool(cited & q.gold), "seconds": r["seconds"], "citation_metrics": metrics})
        k = len(sample)
        out[mode] = {"accuracy": round(ok / k, 3), "n": k, "mean_seconds": round(secs / k, 1),
                     "citation_precision": round(citation_precision / k, 3),
                     "claim_trace_coverage": round(trace_coverage / k, 3),
                     "by_topic": {t: round(h / c, 3) for t, (h, c) in sorted(by_topic.items())}}
        print(mode, out[mode])
    return {"answers": out, "examples": rows_}


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("part", choices=["retrieval", "answers"])
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--modes", default=",".join(ANSWER_MODES))
    a = p.parse_args()
    data = saved()
    if a.part == "retrieval":
        metrics = await retrieval()
        # Keep the old top-level shape for the Detective UI; the legacy comparison has an explicit name elsewhere.
        data["retrieval"] = metrics["full_haystack"]
        data["retrieval_gold_haystack"] = metrics["gold_haystack"]
    else:
        new = await answers(a.n, a.modes.split(","))  # merge by mode, so a rerun of some modes keeps the others
        data["answers"] = {**data.get("answers", {}), **new["answers"]}
        data["examples"] = [e for e in data.get("examples", []) if e["mode"] not in new["answers"]] + new["examples"]
        data["model"] = current_model()
    data["updated"] = date.today().isoformat()
    metadata = reports.corpus_metadata(reports.corpus()[0])
    data["corpus"] = {
        "passages": len(reports.corpus()[0]), "gold_passages": metadata.get("gold_count", len(reports.corpus()[0])),
        "distractor_passages": metadata.get("distractor_count", 0), "questions_supported": int(len(load())),
        "corpus_version": metadata.get("corpus_version"), "corpus_sha256": metadata.get("corpus_sha256"),
        "sampling_seed": metadata.get("sampling_seed"), "qa_excluded": metadata.get("qa_excluded"),
        "full_haystack": (metadata.get("distractor_count", 0) > 0 and metadata.get("index_version") == 2),
        "index_version": metadata.get("index_version"),
    }
    OUT.write_text(json.dumps(data, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    asyncio.run(main())
