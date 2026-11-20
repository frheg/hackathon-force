"""Dataset and model lineage API: what exists, where it came from, and what was used."""
import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from se.config import AREAS, OUT
from se.modeling import well_tie
from se.modeling.relations import relation_plan
from se.modeling.rock_porosity import RESULT as ROCK_POROSITY_OUT
from se.modeling.seismic_coverage import RELATIVE_OUT as COVERAGE_OUT
from se.modeling.smeaheia_support import RESULT as SMEAHEIA_SUPPORT_OUT
from se.modeling.smeaheia_velocity import RELATIVE_OUT
from se.provenance import catalog, model_lineage

router = APIRouter(prefix="/api/provenance")


@router.get("/datasets")
def datasets():
    return catalog()


@router.get("/areas")
def areas():
    return AREAS


@router.get("/model")
def model(target: str = "green_clay"):
    try:
        return model_lineage(target)
    except OSError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/proof")
def proof():
    path = OUT / "proof_core" / "metrics.json"
    if not path.exists():
        raise HTTPException(404, "GPU proof model has not been run")
    return json.loads(path.read_text())


@router.get("/relations")
def relations():
    return relation_plan()


@router.get("/velocity")
def velocity():
    path = OUT / RELATIVE_OUT
    if not path.exists():
        raise HTTPException(404, "GN1101 velocity pilot has not been run")
    return json.loads(path.read_text())


@router.get("/velocity/picks")
def velocity_picks():
    from pyproj import Transformer

    receipt = velocity()
    controls = []
    for well in receipt["controls"]:
        transform = Transformer.from_crs(well["horizontal_epsg"], 3035, always_xy=True)
        for pick in well["picks"]:
            x, y = transform.transform(pick["east_m"], pick["north_m"])
            controls.append({**pick, "x_km": x / 1000, "y_km": y / 1000,
                             "water_depth_m": well["factpages"]["water_depth_m"], "factpages_npdid": well["factpages"]["npdid"],
                             "seabed_twt_ms": well["seabed_time"]["positive_down_value"], "site_link": well["site_link"]})
    return {"picks": controls, "source": receipt["sources"]["picks"], "status": receipt["status"]}


@router.get("/seismic-coverage")
def seismic_coverage():
    path = OUT / COVERAGE_OUT
    if not path.exists():
        raise HTTPException(404, "Seismic coverage audit has not been run")
    return json.loads(path.read_text())


@router.get("/smeaheia-support")
def smeaheia_support():
    path = OUT / SMEAHEIA_SUPPORT_OUT
    if not path.is_file():
        raise HTTPException(404, "Smeaheia depth support audit has not been run")
    return json.loads(path.read_text())


@router.get("/rock-porosity")
def rock_porosity():
    path = OUT / ROCK_POROSITY_OUT / "metrics.json"
    if not path.is_file():
        raise HTTPException(404, "Rock-physics porosity comparison has not been run")
    return json.loads(path.read_text())


TieVersion = Annotated[str, Query(pattern=f"^{well_tie.VERSION}$")]


def _tie(version: str) -> dict:
    try:
        return well_tie.load(OUT, version)
    except FileNotFoundError as e:
        raise HTTPException(404, "well-tie receipt unavailable") from e
    except ValueError as e:
        raise HTTPException(503, str(e)) from e


@router.get("/well-ties")
def well_ties():
    rows = []
    for path in sorted((OUT / well_tie.STORE).glob("*.json")):
        d = _tie(path.stem)
        rows.append({"version": path.stem, **{k: d[k] for k in ("well", "npdid", "survey", "survey_label", "registration", "window_ms", "limits", "credit")},
                     "inline": d["trace"]["inline"], "crossline": d["trace"]["crossline"], "trace_distance_m": d["trace"]["distance_m"]})
    return rows


@router.get("/well-ties/receipt")
def well_tie_receipt(version: TieVersion):
    return {"version": version, **_tie(version)}


@router.get("/well-ties/compare")
def well_tie_compare(
    version: TieVersion,
    hz: Annotated[float, Query(ge=10, le=50)] = 25,
    phase: Annotated[float, Query(ge=-90, le=90)] = 0,
    polarity: Annotated[int, Query(ge=-1, le=1)] = 1,
    shift: Annotated[int, Query(ge=-40, le=40, multiple_of=2)] = 0,
    top: Annotated[float | None, Query(ge=0, le=5000)] = None,
    base: Annotated[float | None, Query(ge=0, le=5000)] = None,
    dv_pct: Annotated[float, Query(ge=-20, le=20)] = 0,
    drho_pct: Annotated[float, Query(ge=-10, le=10)] = 0,
):
    if polarity not in (-1, 1):
        raise HTTPException(422, "polarity must be +1 or -1")
    data = _tie(version)
    try:
        return {"version": version, **well_tie.compare(data, hz=hz, phase=phase, polarity=polarity, shift=shift,
                                                       top=top, base=base, dv=dv_pct / 100, drho=drho_pct / 100)}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
