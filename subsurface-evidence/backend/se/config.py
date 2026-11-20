"""Paths, target and device. Env: DATA_DIR (datasets), SE_DATA (derived tables), WORKER_URL (GPU worker)."""
import os
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PROJECT = BACKEND.parent
REPO = PROJECT.parent
DATA = Path(os.environ.get("DATA_DIR", REPO / "data"))
OUT = Path(os.environ.get("SE_DATA", DATA / "subsurface-evidence"))  # derived tables, never committed
LOG_MD = PROJECT / "LOG.md"
WORKER_URL = os.environ.get("WORKER_URL", "")  # empty: heavy jobs run in this process, on CPU

# L007: the target is a *reported* presence of any of these in a unit
# L019: the trials are described CLAY rows (claystone, shale, mudstone); the target is the share that name a green mineral. Lithology is out of the label.
TARGET = {"name": "green_clay_in_clay_rows", "kinds": ("glauconite", "green clay", "chlorite", "nontronite", "celadonite"), "lith": ("clay",)}
MIN_COVERAGE = 3  # L009: described rows (of the target lithology) needed in a unit before "no mention" counts as a negative
BLOCK_KM = 40.0  # spatial fold size, same as the depth test in the hackathon app (LOG L011)
AREAS = {
    "smeaheia": {
        "title": "Smeaheia",
        "bbox": {"lat_min": 59.9, "lat_max": 60.8, "lon_min": 3.0, "lon_max": 4.2},
        "surveys": ("gn1101", "tne01"),
        "use_cases": ("co2 storage", "legacy wells", "seismic context"),
    },
    "sleipner": {
        "title": "Sleipner",
        "bbox": {"lat_min": 58.0, "lat_max": 58.8, "lon_min": 1.5, "lon_max": 2.4},
        "surveys": tuple(f"sleipner_{v}" for v in ("94p01", "94p07", "94p08", "94p10", "99p01", "01p01", "01p07", "04p07", "06p07", "08p08", "10p10", "10p11")),
        "use_cases": ("co2 storage", "4d time lapse", "seismic context"),
    },
    "northern-lights": {
        "title": "Northern Lights / Aurora-Eos",
        "center_well": "31/5-7",
        "radius_km": 12.0,
        "surveys": (),
        "use_cases": ("co2 storage", "legacy wells", "barriers"),
    },
}


def device() -> str:
    """cuda if torch sees a GPU, else cpu. Torch is optional (extra `gpu`)."""
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"

# Earth-model pilot (PLAN.md, LOG L053): Horda Platform / northern Viking Graben
# Earth-model regions (PLAN P8). The pipeline runs for one region at a time: EARTH_REGION=<name>; artefacts in OUT/earth/<name>.
# "PILOT" below is the active region's box (the code was written for the pilot; every module reads the box from here).
REGIONS = {
    "pilot": {"lat": (59.5, 61.5), "lon": (1.5, 4.5), "step_km": 2.0, "title": "Northern North Sea (Horda Platform)", "short": "Northern North Sea"},  # id "pilot": the first region built
    "north_sea_south": {"lat": (56.0, 59.5), "lon": (1.5, 7.5), "step_km": 3.0, "title": "Southern North Sea (Norwegian sector)", "short": "Southern North Sea"},
    "norwegian_sea": {"lat": (62.0, 69.0), "lon": (2.0, 15.0), "step_km": 4.0, "title": "Norwegian Sea", "short": "Norwegian Sea"},
    "barents": {"lat": (69.5, 74.5), "lon": (15.0, 37.0), "step_km": 4.0, "title": "Barents Sea", "short": "Barents Sea"},
}
REGION = os.environ.get("EARTH_REGION", "pilot")
PILOT = REGIONS[REGION]
EARTH = OUT / "earth" / REGION  # earth-model artefacts, never committed


def in_pilot(lat, lon):
    """True where a point (or array of points) lies inside the pilot box."""
    import numpy as np

    la, lo = np.asarray(lat, float), np.asarray(lon, float)
    return (la >= PILOT["lat"][0]) & (la <= PILOT["lat"][1]) & (lo >= PILOT["lon"][0]) & (lo <= PILOT["lon"][1])
