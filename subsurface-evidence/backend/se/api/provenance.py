"""Dataset and model lineage API: what exists, where it came from, and what was used."""
import json

from fastapi import APIRouter, HTTPException

from se.config import AREAS, OUT
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
