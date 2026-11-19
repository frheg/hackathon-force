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


def device() -> str:
    """cuda if torch sees a GPU, else cpu. Torch is optional (extra `gpu`)."""
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"
