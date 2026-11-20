"""Dataset and model lineage API: what exists, where it came from, and what was used."""
import json

from fastapi import APIRouter, HTTPException

from se.config import AREAS, OUT
from se.modeling.relations import relation_plan
from se.modeling.seismic_coverage import RELATIVE_OUT as COVERAGE_OUT
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


@router.get("/seismic-coverage")
def seismic_coverage():
    path = OUT / COVERAGE_OUT
    if not path.exists():
        raise HTTPException(404, "Seismic coverage audit has not been run")
    return json.loads(path.read_text())
