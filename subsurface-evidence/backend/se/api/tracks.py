"""Read-only well evidence. The index pins every pack and the Smeaheia comparison."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from se.config import DATA, OUT
from se.modeling import well_tracks
from se.modeling.artifacts import sha256

router = APIRouter(prefix="/api/tracks")
RELEASE = "d92d14a3bce5e33d44fddec575a7e544ed392cbdb99d2dc39e64746b813bb5ca"
Version = Annotated[str, Query(pattern="^[a-f0-9]{64}$")]


def receipt(version):
    try:
        item = well_tracks.read(OUT / well_tracks.STORE, version)
    except FileNotFoundError as e:
        raise HTTPException(
            404, "Track release not installed; no substitute used."
        ) from e
    except ValueError as e:
        raise HTTPException(503, "Track release failed its content check.") from e
    if item.get("schema") != 1 or "packs" not in item:
        raise HTTPException(422, "Not a track index.")
    return item


@router.get("")
def index(version: Version = RELEASE):
    r = receipt(version)
    return {
        "version": version,
        **{k: r[k] for k in ("index", "columns", "scopes", "focus_version")},
        "coverage": r.get("coverage"),
    }


@router.get("/receipt")
def manifest(version: Version = RELEASE):
    return receipt(version)


@router.get("/search")
def search(
    version: Version = RELEASE,
    scope: str = "all",
    q: Annotated[str, Query(max_length=100)] = "",
    pa: bool = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    r = receipt(version)
    if scope not in r["scopes"]:
        raise HTTPException(422, "Unknown track scope.")
    term = q.strip().casefold()
    rows = [
        row
        for row in r["index"]
        if (scope == "all" or scope in row[3])
        and (not pa or row[2] == "P&A")
        and (term in row[1].casefold() or term == str(row[0]))
    ]
    return {
        "version": version,
        "columns": r["columns"],
        "total": len(rows),
        "rows": rows[offset : offset + limit],
    }


@router.get("/wells/{npdid}")
def well(npdid: int, version: Version = RELEASE):
    r = receipt(version)
    row = next((row for row in r["index"] if row[0] == npdid), None)
    if row is None:
        raise HTTPException(404, "Borehole not in this track release.")
    try:
        pack = r["packs"][str(npdid // r["pack_size"])]
        w = well_tracks.read(OUT / well_tracks.STORE, pack)[str(npdid)]
        if [w[k] for k in r["columns"]] != row:
            raise ValueError("Well identity disagrees with index")
    except (FileNotFoundError, ValueError, KeyError) as e:
        raise HTTPException(
            503, "Pinned well pack missing or damaged; not a negative finding."
        ) from e
    return {
        "version": version,
        "pack": pack,
        "well": w,
        "focus_version": r["focus_version"],
        "reports": r["rules"]["reports"],
        "inputs": r["inputs"],
    }


@router.get("/sources/sleipner")
def public_report(version: Version = RELEASE):
    ref = receipt(version)["rules"]["reports"]["sleipner"]
    # Only the public curated completion report, not arbitrary catalogue files or licensed archives.
    path = (DATA / ref["path"]).resolve()
    if (
        not path.is_relative_to((DATA / "official/completion_reports").resolve())
        or not path.is_file()
    ):
        raise HTTPException(404, "Reviewed public PDF not installed.")
    if sha256(path) != ref["sha256"]:
        raise HTTPException(503, "Reviewed public PDF has changed.")
    return FileResponse(path, media_type="application/pdf")
