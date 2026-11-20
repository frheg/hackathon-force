"""The default screen only serves verified receipt bytes. No live model fit or mutable region lookup."""
import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from se.config import OUT
from se.modeling.smeaheia_screen import BUILD, STORE

router = APIRouter(prefix="/api/screen")
RELEASE = "50fe1fd2c6ab16d51bc3e1bb7bf4c573d2bcaf65fa5864fa9ad95f442f89eb7c"


@router.get("/smeaheia")
def smeaheia(version: Annotated[str, Query(pattern="^[a-f0-9]{64}$")] = RELEASE):
    try:
        payload = (OUT / STORE / f"{version}.json").read_bytes()
    except FileNotFoundError as e:
        raise HTTPException(404, "Smeaheia screen receipt is not installed; no substitute build was used.") from e
    if hashlib.sha256(payload).hexdigest() != version:
        raise HTTPException(503, "Smeaheia screen receipt failed its content check.")
    receipt = json.loads(payload)
    if (receipt.get("schema") not in (1, 2) or receipt.get("region") != "pilot"
            or (version == RELEASE and (receipt.get("earth_build") != BUILD or receipt.get("schema") != 2))):
        raise HTTPException(503, "Unsupported screen receipt or mismatched Earth build.")
    return {"version": version, **receipt}
