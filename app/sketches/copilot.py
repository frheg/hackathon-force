"""NCS Copilot: questions about the Norwegian shelf in plain words, answered with SQL over Sodir's FactPages tables.

The model writes one DuckDB query, the server runs it read-only (no file or network access from SQL), and the model
sums up the rows. Wellbore rows with positions go on a map.
"""

import asyncio
import datetime as dt
import re
import threading

import duckdb
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from common import DATA_DIR, ModelBusy, chat, page

router = APIRouter(prefix="/copilot")
DB = DATA_DIR / "ncs.duckdb"
MAX_ROWS = 500

# columns that only cost tokens: links, sync dates, coordinates in other notations, name parts
SKIP = re.compile(r"(Url|DateUpdated|DateUpdatedMax|NamePart\d|Utm|UtmZone|(Ns|Ew)(Deg|Min|Sec|Code)|PlotSymbol|GeodeticDatum)$")
NOTES = """Notes:
- field_production_monthly: net production per month and field (prfInformationCarrier = field name, as field.fldName).
  Oil, NGL, condensate and oe (oil equivalents) in million Sm3, gas in billion Sm3, water in million Sm3.
- field_reserves: one row per field and fldVersion (year of the estimate); use the newest fldVersion per field.
  Oil, NGL, condensate, OE in million Sm3, gas in billion Sm3.
- Wellbores: wellbore_exploration (wildcat, appraisal) and wellbore_development. wlbNsDecDeg is latitude,
  wlbEwDecDeg longitude. wlbContent is what was found (OIL, GAS, OIL/GAS, GAS/CONDENSATE, DRY, SHOWS, ...).
  Depths and water depth in metres. wlbEntryYear and wlbCompletionYear are years.
- Names are upper case (TROLL, JOHAN SVERDRUP, 'Equinor Energy AS'); compare names with ILIKE.
- Join keys: fldNpdidField, wlbNpdidWellbore, dscNpdidDiscovery, cmpNpdidCompany.
"""
SYSTEM = """You turn questions about the Norwegian Continental Shelf into one DuckDB SQL query over the tables below.
Reply with only the query in a ```sql block. One SELECT (WITH is fine), no other statements.
When the rows are wellbores, include wlbWellboreName, wlbNsDecDeg and wlbEwDecDeg so they can be shown on a map.
Return at most 200 rows unless the question asks for every row. Round decimals to 2 places.

{schema}
{notes}"""

_schema: tuple[float, str] | None = None


def schema() -> str:
    global _schema
    mtime = DB.stat().st_mtime
    if _schema is None or _schema[0] != mtime:
        with connect() as db:
            rows = db.execute(
                "select table_name, column_name, data_type from information_schema.columns order by table_name, ordinal_position"
            ).fetchall()
        tables: dict[str, list[str]] = {}
        for t, c, d in rows:
            if not SKIP.search(c):
                tables.setdefault(t, []).append(f"{c} {d.lower()}")
        _schema = (mtime, "\n".join(f"{t}({', '.join(cols)})" for t, cols in tables.items()))
    return _schema[1]


def connect():
    return duckdb.connect(str(DB), read_only=True, config={"enable_external_access": False})


def extract_sql(text: str) -> str:
    m = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S | re.I)
    sql = (m.group(1) if m else text).strip().rstrip(";").strip()
    if not re.match(r"(?is)^\s*(select|with)\b", sql) or ";" in sql:
        raise ValueError(f"not a single SELECT: {sql[:200]}")
    return sql


def run(sql: str) -> tuple[list[str], list[list]]:
    with connect() as db:
        timer = threading.Timer(20, db.interrupt)  # a runaway query stops after 20 s
        timer.start()
        try:
            cur = db.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchmany(MAX_ROWS)
        finally:
            timer.cancel()
    return cols, [[plain(v) for v in r] for r in rows]


def plain(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return str(v)


def points(cols: list[str], rows: list[list]) -> list[dict]:
    if "wlbNsDecDeg" not in cols or "wlbEwDecDeg" not in cols:
        return []
    la, lo = cols.index("wlbNsDecDeg"), cols.index("wlbEwDecDeg")
    name = next((cols.index(c) for c in ("wlbWellboreName", "wlbWell", "fldName") if c in cols), None)
    return [
        {"lat": r[la], "lon": r[lo], "label": r[name] if name is not None else ""}
        for r in rows
        if isinstance(r[la], (int, float)) and isinstance(r[lo], (int, float))
    ]


class Question(BaseModel):
    q: str


@router.get("")
def slash():
    return RedirectResponse("copilot/")


@router.get("/", response_class=HTMLResponse)
def index():
    return page("copilot.html")


@router.post("/api/ask")
async def ask(body: Question):
    if not DB.exists():
        raise HTTPException(503, "no database yet: run fetch_data.py sodir")
    messages = [
        {"role": "system", "content": SYSTEM.format(schema=schema(), notes=NOTES)},
        {"role": "user", "content": body.q},
    ]
    sql, error = "", ""
    try:
        for _ in range(2):  # one retry with the error, which fixes most wrong column names
            reply = await chat(messages)
            try:
                sql = extract_sql(reply)
                cols, rows = await asyncio.to_thread(run, sql)
                error = ""
                break
            except (ValueError, duckdb.Error) as e:
                error = str(e).splitlines()[0][:400]
                messages += [
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": f"That failed: {error}\nWrite a corrected query."},
                ]
        if error:
            return {"sql": sql, "error": error}
        sample = "\n".join([",".join(cols)] + [",".join(str(v) for v in r) for r in rows[:40]])
        answer = await chat(
            [
                {
                    "role": "system",
                    "content": "Answer the question in 2 to 4 plain sentences from the query result. Use the numbers "
                    "with their units (million Sm3 or billion Sm3 as in the column names). If the result is empty, "
                    "say so. Do not invent facts that are not in the result.",
                },
                {"role": "user", "content": f"Question: {body.q}\nSQL: {sql}\nResult ({len(rows)} rows):\n{sample}"},
            ],
            max_tokens=600,
        )
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    return {"sql": sql, "columns": cols, "rows": rows, "answer": answer, "points": points(cols, rows)}
