"""Report facts for the earth model (PLAN P5, LOG L068).

P5.1 prefilter: pilot wells' completion-report pages (Diskos OCR JSON: page text, page tags and a page summary shipped with the data)
whose text has a number with a unit next to a keyword of a fact type. P5.2 extract: the local LLM (Naija-Petro 8B, extract profile,
through the cluster's llm service) returns facts as JSON with a verbatim quote; a fact is kept only if its quote and its number are
found in the page text (no invented values). P5.3 check: facts against FactPages DST and RealPore cores at the same well and depth.
"""
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from se.config import DATA, EARTH
from se.ingest.names import norm

ROOT = DATA / "official" / "completion_reports" / "4462 fully public wellbore completion reports from the Norwegian continental shelf expl appraisal production"
NUM = r"\d[\d.,]*\s?"
FACTS = {  # fact type -> a keyword and a number with a unit nearby (cheap, recall-oriented)
    "show": r"(oil show|gas show|fluorescen|hydrocarbon show|\bcut\b|oil stain|odou?r)",
    "porosity": r"porosit\w*[^.\n]{0,60}" + NUM + r"(%|percent|p\.u\.)",
    "permeability": r"permeabilit\w*[^.\n]{0,60}" + NUM + r"(md|mD|darcy)",
    "temperature": r"(bht|bottom.?hole temp\w*|temperature)[^.\n]{0,60}" + NUM + r"(°\s?c|deg\.?\s?c|degc|°\s?f|deg\.?\s?f)",
    "pressure": r"(pressure|rft|mdt|fmt|repeat formation)[^.\n]{0,60}" + NUM + r"(bar|psi|mpa|kpa|g/cc|sg|g/cm)",
    "deviation": r"(inclination|deviation|azimuth)[^.\n]{0,40}" + NUM + r"(°|deg)",
}
RX = {k: re.compile(v, re.I) for k, v in FACTS.items()}


def well_dir(wb: str) -> Path:
    return ROOT / wb.replace("/", "_").replace(" ", "_")


def pages(wells: list[str]):
    """(wellbore, file, page_no, quality, tags, summary, text) for every page of every report of these wells."""
    for wb in wells:
        d = well_dir(wb)
        if not d.exists():
            continue
        for f in d.rglob("*.JSON"):
            try:
                doc = json.loads(f.read_text())
            except Exception:
                continue
            for _, v in doc.items():
                for p in v.get("pages", []):
                    t = (p.get("OCR") or {}).get("ocr_markdown") or ""
                    ai = p.get("AI") or {}
                    yield wb, f.name, p.get("page_no"), (p.get("page_metadata") or {}).get("quality"), ai.get("tags") or [], ai.get("page_summary") or "", t


def prefilter() -> tuple[pd.DataFrame, dict]:
    w = pd.read_parquet(EARTH / "wells.parquet"); wells = sorted(w[w.pilot].wellbore)
    rows, n = [], 0; t0 = time.time()
    for wb, f, pg, q, tags, summ, text in pages(wells):
        n += 1
        hits = [k for k, r in RX.items() if r.search(text)]
        if hits:
            rows.append({"wellbore": wb, "file": f, "page": pg, "quality": q, "types": hits, "tags": tags, "summary": summ, "text": text[:8000]})
    c = pd.DataFrame(rows)
    stats = {"pilot_wells_with_reports": int(c.wellbore.nunique()) if len(c) else 0, "pages_read": n, "candidate_pages": int(len(c)),
             "by_type": {k: int(sum(k in h for h in c.types)) for k in FACTS} if len(c) else {}, "seconds": round(time.time() - t0, 1)}
    return c, stats


PROMPT = """You extract facts from one page of a Norwegian offshore well report. Return JSON: {"facts": [...]}.
Each fact: {"type": one of show|porosity|permeability|temperature|pressure|deviation, "value": number or null, "unit": string,
"depth_m": number or null, "depth_ref": "MD RKB"|"TVD RKB"|"TVDSS"|"unknown", "depth_unit": "m"|"ft", "formation": string or null,
"quote": the shortest verbatim span from the page that states the fact (copy exactly)}.
Only facts stated on the page, about this well. At most 20 facts, the most specific first. For shows, value is null and quote names the
show. No guesses. If none, {"facts": []}."""


SCHEMA = {"type": "object", "properties": {"facts": {"type": "array", "maxItems": 12, "items": {"type": "object", "properties": {
    "type": {"enum": ["show", "porosity", "permeability", "temperature", "pressure", "deviation"]}, "value": {"type": ["number", "null"]}, "unit": {"type": "string"},
    "depth_m": {"type": ["number", "null"]}, "depth_ref": {"enum": ["MD RKB", "TVD RKB", "TVDSS", "unknown"]}, "depth_unit": {"enum": ["m", "ft"]},
    "formation": {"type": ["string", "null"]}, "quote": {"type": "string", "maxLength": 200}},
    "required": ["type", "value", "unit", "depth_m", "depth_ref", "depth_unit", "formation", "quote"]}}}, "required": ["facts"]}
PROMPT_V2 = PROMPT + """
Not facts (leave them out): pressure tests of casing, BOP, plugs, packers, lines or valves; pump, choke or drawdown pressures; mud weight;
mobility in mD/cP; gas percentages (C1, C2); circulating or surface temperatures; drilling operations (tripping, reaming, running tools);
chart axis labels. A show names oil, gas, fluorescence, cut or stain in rock. Pressure means formation (pore) pressure from a test (DST,
RFT, MDT, FMT). Temperature means formation or bottom-hole temperature."""


def llm(text: str, url: str, model: str = "naija-petro-8b-extract", timeout: float = 300.0, v2: bool = False) -> tuple[dict, dict]:
    import httpx

    body = {"model": model, "messages": [{"role": "system", "content": PROMPT_V2 if v2 else PROMPT}, {"role": "user", "content": text[:7000]}],
            "temperature": 0, "max_tokens": 2000, "response_format": {"type": "json_object", "schema": SCHEMA} if v2 else {"type": "json_object"}}
    t0 = time.time(); r = httpx.post(f"{url}/chat/completions", json=body, timeout=timeout); r.raise_for_status(); j = r.json()
    u = j.get("usage", {}); msg = j["choices"][0]["message"]["content"]
    try:
        out = json.loads(msg)
    except json.JSONDecodeError:  # truncated or malformed: keep the complete fact objects only, and count the page as a parse error
        out = {"facts": [], "parse_error": True}
        for m in re.finditer(r"\{[^{}]*\}", msg):
            try:
                out["facts"].append(json.loads(m.group(0)))
            except json.JSONDecodeError:
                pass
    return out, {"prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"), "seconds": round(time.time() - t0, 2)}


def grounded(f: dict, text: str) -> bool:
    """The quote must be in the page (whitespace-insensitive) and, if a value is given, the number must be in the quote."""
    q = re.sub(r"\s+", " ", str(f.get("quote") or "")).strip().lower(); t = re.sub(r"\s+", " ", text).lower()
    if len(q) < 4 or q not in t:
        return False
    v = f.get("value")
    if v is None:
        return f.get("type") == "show"
    s = ("%g" % float(v)) if isinstance(v, (int, float)) else str(v)
    return s.replace(".0", "") in q.replace(",", ".") or s in q


def sample_run(c: pd.DataFrame, url: str, n: int = 200, seed: int = 0, v2: bool = False) -> tuple[pd.DataFrame, dict]:
    from concurrent.futures import ThreadPoolExecutor

    s = c.sample(min(n, len(c)), random_state=seed)
    facts, use = [], []

    def one(r):
        try:
            return r, *llm(r.text, url, v2=v2)
        except Exception as e:
            return r, None, {"error": f"{type(e).__name__}: {e}"[:200]}
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:  # the extract profile serves 4 parallel slots
        results = list(ex.map(one, s.itertuples()))
    wall = time.time() - t0
    for r, out, u in results:
        use.append(u)
        if out is None:
            continue
        u["parse_error"] = bool(out.get("parse_error"))
        for f in out.get("facts", []) if isinstance(out, dict) else []:
            if isinstance(f, dict):
                facts.append({"wellbore": r.wellbore, "file": r.file, "page": r.page, **{k: f.get(k) for k in ("type", "value", "unit", "depth_m", "depth_ref", "depth_unit", "formation", "quote")},
                              "grounded": grounded(f, r.text)})
    u = pd.DataFrame([x for x in use if "error" not in x])
    stats = {"pages": int(len(s)), "errors": int(sum("error" in x for x in use)), "facts": int(len(facts)), "grounded": int(sum(f["grounded"] for f in facts)),
             "prompt_tokens_mean": round(float(u.prompt_tokens.mean()), 1) if len(u) else None, "completion_tokens_mean": round(float(u.completion_tokens.mean()), 1) if len(u) else None,
             "seconds_per_page": round(float(u.seconds.mean()), 2) if len(u) else None, "wall_seconds": round(wall, 1), "pages_per_hour_4_slots": round(len(s) / wall * 3600) if wall else None,
             "parse_errors": int(u.parse_error.sum()) if "parse_error" in u else 0}
    f = pd.DataFrame(facts)
    if len(f):  # the model sometimes puts text in numeric fields: keep the raw text, and a number where one parses
        for c in ("value", "depth_m"):
            f[c + "_raw"] = f[c].astype(str); f[c] = pd.to_numeric(f[c], errors="coerce")
        for c in ("type", "unit", "depth_ref", "depth_unit", "formation", "quote"):
            f[c] = f[c].astype(str)
    return f, stats


def check(f: pd.DataFrame) -> dict:
    """P5.3: precision proxies for extracted facts. (1) grounding: the quote and number are on the page; (2) agreement with measured data in
    the same well within 20 m of depth: porosity vs RealPore plugs, temperature and pressure vs FactPages DST; (3) plausible ranges."""
    from se.ingest.names import norm as nm

    if not len(f):
        return {"facts": 0, "grounded": 0, "note": "no facts"}
    g = f[f.grounded].copy()
    out = {"facts": int(len(f)), "grounded": int(len(g)), "grounded_share": round(float(f.grounded.mean()), 3) if len(f) else None,
           "by_type": g.type.value_counts().to_dict()}
    g["d"] = np.where(g.depth_unit.str.lower().str.startswith("ft"), g.depth_m * 0.3048, g.depth_m)
    ok_range = {"porosity": (0, 50), "permeability": (0, 1e5), "temperature": (0, 250), "pressure": (0, 2000), "deviation": (0, 100)}
    g["plausible"] = [True if t not in ok_range or pd.isna(v) else ok_range[t][0] <= v <= ok_range[t][1] for t, v in zip(g.type, g.value)]
    out["plausible_share"] = round(float(g.plausible.mean()), 3) if len(g) else None
    core = pd.read_parquet(DATA / "official/realpore/realpore.parquet", columns=["wellbore", "md", "porosity"]).dropna(); core["wellbore"] = core.wellbore.map(nm)
    po = g[(g.type == "porosity") & g.value.notna() & g.d.notna()]; agree = []
    for r in po.itertuples():
        c = core[(core.wellbore == r.wellbore) & ((core.md - r.d).abs() <= 20)]
        if len(c):
            agree.append(abs(r.value - c.porosity.mean()))
    out["porosity_vs_core"] = {"pairs": len(agree), "median_abs_diff_pct": round(float(np.median(agree)), 2) if agree else None,
                               "within_5_points": round(float(np.mean(np.array(agree) <= 5)), 3) if agree else None}
    p = pd.read_parquet(EARTH / "pressure_obs.parquet"); dst = p[p.kind == "pore"]
    te = g[(g.type == "temperature") & g.value.notna() & g.d.notna() & g.unit.str.contains("c", case=False)]; at = []
    for r in te.itertuples():
        c = dst[(dst.wellbore == r.wellbore) & ((dst.md - r.d).abs() <= 50) & (dst.temp_C > 0)]
        if len(c):
            at.append(abs(r.value - c.temp_C.mean()))
    out["temperature_vs_dst"] = {"pairs": len(at), "median_abs_diff_C": round(float(np.median(at)), 1) if at else None}
    out["note"] = "Hand check of 100 facts is still to do: these are automatic proxies, not measured precision."
    return out
