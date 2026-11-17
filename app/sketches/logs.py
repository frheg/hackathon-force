"""Log Lens: a well's logs next to its lithology, as interpreted and as predicted by a model trained on other wells.

The 10 wells shown were never seen in training (FORCE 2020's hidden test set). Zoom to an interval and the LLM
reads its numbers like a petrophysicist would, with the model's lithology and the formations it crosses.
"""

import json

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from common import DATA_DIR, ModelBusy, chat, page

router = APIRouter(prefix="/logs")
D = DATA_DIR / "force2020"
CURVES = ["GR", "RHOB", "NPHI", "DTC", "RDEP", "RMED", "PEF", "CALI"]
UNITS = {"GR": "API", "RHOB": "g/cm3", "NPHI": "v/v", "DTC": "us/ft", "RDEP": "ohm.m", "RMED": "ohm.m", "PEF": "b/e", "CALI": "in"}
MAX_POINTS = 4000

_cache: dict = {}


def load() -> tuple[pd.DataFrame, dict]:
    f = D / "wells.parquet"
    if not f.exists():
        raise HTTPException(503, "no model yet: run python -m sketches.train_logs")
    if _cache.get("mtime") != f.stat().st_mtime:
        _cache.update(mtime=f.stat().st_mtime, df=pd.read_parquet(f), metrics=json.loads((D / "metrics.json").read_text()))
    return _cache["df"], _cache["metrics"]


def well(name: str) -> pd.DataFrame:
    df, _ = load()
    w = df[df["WELL"] == name]
    if w.empty:
        raise HTTPException(404, f"no well {name}")
    return w.sort_values("DEPTH_MD")


def column(s: pd.Series) -> list:
    return [None if pd.isna(v) else round(float(v), 4) for v in s]


@router.get("")
def slash():
    return RedirectResponse("logs/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("logs.html")


@router.get("/api/wells")
def wells():
    df, metrics = load()
    rows = []
    for name, g in df.groupby("WELL"):
        rows.append(
            {
                "well": name,
                "top": round(float(g["DEPTH_MD"].min())),
                "base": round(float(g["DEPTH_MD"].max())),
                **metrics["wells"][name],
            }
        )
    return {"wells": rows, **{k: metrics[k] for k in ("accuracy", "score", "lithology", "train_wells")}}


@router.get("/api/well/{name:path}")
def curves(name: str):
    w = well(name)
    step = max(1, len(w) // MAX_POINTS)  # enough points for the screen
    s = w.iloc[::step]
    return {
        "well": name,
        "depth": column(s["DEPTH_MD"]),
        "curves": {c: column(s[c]) for c in CURVES},
        "true": s["TRUE"].fillna(-1).astype(int).tolist(),
        "pred": s["PRED"].astype(int).tolist(),
        "group": s["GROUP"].fillna("").tolist(),
    }


class Interval(BaseModel):
    well: str
    top: float
    base: float


def summary(w: pd.DataFrame, lithology: list[str]) -> str:
    lines = [f"{len(w)} samples, {w['DEPTH_MD'].min():.0f} to {w['DEPTH_MD'].max():.0f} m MD."]
    for c in CURVES:
        v = w[c].dropna()
        if len(v) > 10:
            p10, p50, p90 = np.percentile(v, [10, 50, 90])
            lines.append(f"{c} ({UNITS[c]}): P10 {p10:.3g}, median {p50:.3g}, P90 {p90:.3g}")
    for label, col in (("Model's lithology", "PRED"), ("Interpreted lithology", "TRUE")):
        share = w[col].dropna().astype(int).map(lambda i: lithology[i]).value_counts(normalize=True)
        lines.append(f"{label}: " + ", ".join(f"{k} {v:.0%}" for k, v in share.items() if v >= 0.02))
    for c in ("GROUP", "FORMATION"):
        names = w[c].dropna().unique().tolist()
        if names:
            lines.append(f"{c.title()}s: {', '.join(names[:8])}")
    lines.append(f"Model confidence: median {w['CONFIDENCE'].median():.2f}")
    return "\n".join(lines)


@router.post("/api/explain")
async def explain(body: Interval):
    _, metrics = load()
    w = well(body.well)
    w = w[(w["DEPTH_MD"] >= min(body.top, body.base)) & (w["DEPTH_MD"] <= max(body.top, body.base))]
    if len(w) < 10:
        raise HTTPException(400, "pick a longer interval")
    facts = summary(w, metrics["lithology"])
    try:
        text = await chat(
            [
                {
                    "role": "system",
                    "content": "You are a petrophysicist on the Norwegian Continental Shelf. From the log statistics "
                    "of one depth interval, write a short interpretation: likely lithology and why (which curves "
                    "say so), any sign of hydrocarbons or porosity worth a closer look, and where the model's "
                    "lithology disagrees with the interpreted one. 120 words at most, plain text, no headings. "
                    "Say what is uncertain.",
                },
                {"role": "user", "content": f"Well {body.well}.\n{facts}"},
            ],
            max_tokens=500,
        )
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    return {"facts": facts, "text": text}
