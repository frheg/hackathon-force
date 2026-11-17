"""Field Pulse: a field's monthly production, an Arps decline fitted from a chosen month, and the forecast's remaining
volume next to Sodir's own remaining reserves. The LLM writes a field brief from Sodir's description and the numbers.
"""

import asyncio
import datetime as dt

import duckdb
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from scipy.optimize import curve_fit

from common import DATA_DIR, ModelBusy, chat, page

router = APIRouter(prefix="/decline")
DB = DATA_DIR / "ncs.duckdb"
# product: (production column, reserves column, unit)
PRODUCTS = {
    "oe": ("prfPrdOeNetMillSm3", "fldRemainingOE", "million Sm3 o.e."),
    "oil": ("prfPrdOilNetMillSm3", "fldRemainingOil", "million Sm3"),
    "gas": ("prfPrdGasNetBillSm3", "fldRemainingGas", "billion Sm3"),
}
HORIZON = 25 * 12  # months
LIMIT = 0.02  # stop the forecast when the rate falls below 2 % of the fitted start rate


def query(sql: str, *args) -> list[tuple]:
    with duckdb.connect(str(DB), read_only=True) as db:
        return db.execute(sql, list(args)).fetchall()


def arps(t, qi, di, b):
    return qi / np.power(1 + b * di * t, 1 / b)


def analyse(name: str, product: str, start: str | None) -> dict:
    if product not in PRODUCTS:
        raise HTTPException(400, f"product: one of {', '.join(PRODUCTS)}")
    col, res_col, unit = PRODUCTS[product]
    rows = query(
        "select prfYear, prfMonth, prfPrdOilNetMillSm3, prfPrdGasNetBillSm3, prfPrdOeNetMillSm3, "
        "prfPrdProducedWaterInFieldMillSm3, " + col + " from field_production_monthly "
        "where prfInformationCarrier = ? order by prfYear, prfMonth",
        name,
    )
    if not rows:
        raise HTTPException(404, f"no production for {name}")
    months = [f"{y}-{m:02d}" for y, m, *_ in rows]
    q = np.array([r[6] for r in rows], dtype=float)

    # fit from the chosen month, or by default from the highest month of the last 8 years
    if start and start in months:
        i0 = months.index(start)
    else:
        recent = max(0, len(q) - 96)
        i0 = recent + int(np.argmax(q[recent:]))
    if len(q) - i0 < 12:
        i0 = max(0, len(q) - 36)
    t = np.arange(len(q) - i0, dtype=float)
    y = q[i0:]
    fit, forecast = None, []
    ok = y > 0
    if ok.sum() >= 6:
        try:
            p, _ = curve_fit(
                arps, t[ok], y[ok], p0=[y[ok][0], 0.02, 0.5], bounds=([0, 1e-4, 1e-3], [y.max() * 3, 1.0, 1.5]), maxfev=20000
            )
            pred = arps(t[ok], *p)
            r2 = 1 - ((y[ok] - pred) ** 2).sum() / max(((y[ok] - y[ok].mean()) ** 2).sum(), 1e-12)
            tf = np.arange(len(t), len(t) + HORIZON, dtype=float)
            qf = arps(tf, *p)
            qf = qf[qf >= LIMIT * p[0]]
            last = dt.date(int(months[-1][:4]), int(months[-1][5:]), 1)
            forecast = [
                [f"{last.year + (last.month + k) // 12 - (1 if (last.month + k) % 12 == 0 else 0)}-"
                 f"{((last.month + k - 1) % 12) + 1:02d}", round(float(v), 5)]
                for k, v in enumerate(qf, start=1)
            ]
            fit = {
                "start": months[i0],
                "qi": round(float(p[0]), 4),
                "decline_per_year": round(float(1 - (arps(12, *p) / p[0])), 3),  # effective first-year decline
                "b": round(float(p[2]), 2),
                "r2": round(float(r2), 3),
                "remaining": round(float(qf.sum()), 2),
                "until": forecast[-1][0] if forecast else months[-1],
            }
        except RuntimeError:
            fit = None

    info = query(
        "select f.cmpLongName, f.fldCurrentActivitySatus, f.fldHcType, f.fldMainArea, f.wlbName, "
        "d.dscDiscoveryYear from field f left join discovery d on d.wlbName = f.wlbName and d.fldName = f.fldName "
        "where f.fldName = ? limit 1",
        name,
    )
    reserves = query(
        f"select fldVersion, {res_col}, fldRecoverableOE, fldRemainingOE from field_reserves where fldName = ? "
        "order by fldVersion desc limit 1",
        name,
    )
    facts = dict(zip(["operator", "status", "hc_type", "area", "discovery_well", "discovery_year"], info[0])) if info else {}
    if reserves:
        facts.update(reserves_year=reserves[0][0], sodir_remaining=reserves[0][1], recoverable_oe=reserves[0][2])
    return {
        "field": name,
        "product": product,
        "unit": unit,
        "months": months,
        "series": {
            "oil": [r[2] for r in rows],
            "gas": [r[3] for r in rows],
            "oe": [r[4] for r in rows],
            "water": [r[5] for r in rows],
        },
        "cumulative": round(float(np.nansum(q)), 2),
        "fit": fit,
        "forecast": forecast,
        "facts": facts,
    }


@router.get("")
def slash():
    return RedirectResponse("decline/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("decline.html")


@router.get("/api/fields")
def fields():
    if not DB.exists():
        raise HTTPException(503, "no database yet: run fetch_data.py sodir")
    rows = query(
        "select f.fldName, f.cmpLongName, f.fldCurrentActivitySatus, f.fldHcType, "
        "round(sum(p.prfPrdOeNetMillSm3), 1) as cum, max(p.prfYear * 100 + p.prfMonth) as last "
        "from field f join field_production_monthly p on p.prfInformationCarrier = f.fldName "
        "group by all order by cum desc"
    )
    return [
        {"field": r[0], "operator": r[1], "status": r[2], "hc_type": r[3], "cumulative_oe": r[4], "last": f"{r[5] // 100}-{r[5] % 100:02d}"}
        for r in rows
    ]


@router.get("/api/field/{name}")
async def field(name: str, product: str = "oe", start: str | None = None):
    return await asyncio.to_thread(analyse, name, product, start)


class Brief(BaseModel):
    field: str
    product: str = "oe"
    start: str | None = None


@router.post("/api/brief")
async def brief(body: Brief):
    a = await asyncio.to_thread(analyse, body.field, body.product, body.start)
    texts = query(
        "select fldDescriptionHeading, fldDescriptionText from field_description where fldName = ?", body.field
    )
    description = "\n".join(f"{h}: {t}" for h, t in texts)[:6000]
    years = {}
    for m, v in zip(a["months"], a["series"]["oe"]):
        years[m[:4]] = years.get(m[:4], 0) + (v or 0)
    recent = ", ".join(f"{y}: {v:.2f}" for y, v in list(years.items())[-8:])
    numbers = (
        f"Facts: {a['facts']}\nCumulative {body.product}: {a['cumulative']} {a['unit']}.\n"
        f"Yearly o.e. production, million Sm3: {recent}.\n"
        f"Decline fit: {a['fit']} (remaining is the forecast's volume in {a['unit']}; sodir_remaining in facts is "
        f"Sodir's estimate for the same product)."
    )
    try:
        text = await chat(
            [
                {
                    "role": "system",
                    "content": "You write field briefs for engineers on the Norwegian Continental Shelf. Three short "
                    "paragraphs, plain text: the field (where, what, how it is developed), the production trend and "
                    "what the decline forecast says against Sodir's remaining reserves (say which is higher and what "
                    "could explain the gap, such as new wells or projects), and what to check next. 200 words at most. "
                    "Use only the facts given.",
                },
                {"role": "user", "content": f"Field {body.field}.\n{numbers}\nSodir's description:\n{description}"},
            ],
            max_tokens=700,
        )
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    return {"text": text}
