"""Target builder API: list saved targets, what a recipe can use, build one, remove one."""
import threading
from functools import lru_cache

from fastapi import APIRouter, Body, HTTPException

from se.api import explore
from se.targets import builder, store

router = APIRouter(prefix="/api")
LOCK = threading.Lock()  # one build at a time: each runs a 5-fold validation


@lru_cache(maxsize=1)
def _options() -> dict:
    c = explore.con()
    out = {"well": [], "interval": [], "ops": {"eq": "equals", "ne": "not equal", "in": "is one of (a,b,c)", "notin": "is none of", "has": "contains", "gt": ">", "lt": "<", "ge": ">=", "le": "<=", "null": "is empty", "notnull": "is filled"}}
    for mode, tabs in (("well", builder.WELL_TABLES), ("interval", builder.INTERVAL_TABLES)):
        for t in tabs:
            cols = []
            for k, ty in explore.cols(c, t).items():
                num = ty.split("(")[0] in explore.NUM
                n, lo, hi = c.execute(f'select count(distinct "{k}"), min("{k}")::varchar, max("{k}")::varchar from "{t}"').fetchone()
                vals = [r[0] for r in c.execute(f'select "{k}"::varchar from "{t}" where "{k}" is not null group by 1 order by count(*) desc limit 25').fetchall()] if (not num and n <= 60) else []
                if not k.lower().endswith(("npdid", "url")) and "Date" not in k:
                    cols.append({"name": k, "numeric": num, "distinct": n, "min": lo if num else None, "max": hi if num else None, "values": vals})
            out[mode].append({"table": t, "columns": cols, "rows": c.execute(f'select count(*) from "{t}"').fetchone()[0]})
    return out


@router.get("/targets/options")
def options():
    t = builder.text_lines()
    return {**_options(), "text": {"lines": int(len(t)), "wells": int(t.wellbore.nunique()), "liths": {k: int(v) for k, v in t.lith.value_counts().items()}}}


@router.get("/text/preview")
def text_preview(keywords: str, lith: str = "clay,sand,carbonate"):
    """How many report lines a keyword recipe matches, and a few of them with their source (well, file, page), before anything is built."""
    try:
        rx = builder.keyword_regex(keywords.split(","))
    except ValueError as e:
        raise HTTPException(400, str(e))
    t = builder.text_lines()
    t = t[t.lith.isin([x for x in lith.split(",") if x])]
    hit = t[t.text.str.contains(rx)]
    ex = hit.sample(min(8, len(hit)), random_state=0) if len(hit) else hit
    return {"lines": int(len(t)), "matches": int(len(hit)), "share": float(len(hit) / max(len(t), 1)), "wells": int(hit.wellbore.nunique()),
            "examples": [{"wellbore": r.wellbore, "file": r.file, "page": int(r.page), "depth": float(r.depth_from), "lith": r.lith, "text": r.text} for r in ex.itertuples()]}


@router.get("/targets")
def targets():
    return {"builtin": store.GREEN, "saved": store.saved(), "presets": store.PRESETS}


@router.post("/targets/build")
def build(spec: dict = Body(...)):
    from se.api import main  # drop the cached state of a rebuilt target

    if spec.get("mode") == "text":
        if not any((k or "").strip() for k in spec.get("keywords") or []):
            raise HTTPException(400, "a text recipe needs at least one keyword")
    else:
        if spec.get("mode") not in ("well", "interval") or not spec.get("success"):
            raise HTTPException(400, "a recipe needs a mode (well or interval) and at least one success filter")
        tabs = builder.WELL_TABLES if spec["mode"] == "well" else builder.INTERVAL_TABLES
        if spec.get("table") not in tabs:
            raise HTTPException(400, f"table must be one of {list(tabs)}")
    if not LOCK.acquire(blocking=False):
        raise HTTPException(409, "another target is being built, try again in a minute")
    try:
        out = store.evaluate({**spec, "title": spec.get("title") or "Untitled target"})
    except (ValueError, KeyError) as e:
        raise HTTPException(422, str(e))
    finally:
        LOCK.release()
    main.S.pop(out["id"], None)
    return out


@router.delete("/targets/{tid}")
def remove(tid: str):
    from se.api import main

    try:
        store.remove(tid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    main.S.pop(tid, None)
    return {"removed": tid}
