"""Shared validation helpers for the earth model (PLAN P10.1: one definition instead of a copy per module)."""
import os

import numpy as np

BLOCK_KM = 40.0


def blocks(x, y, km: float = BLOCK_KM) -> np.ndarray:
    """Spatial block id per point (EPSG:3035 km): held-out folds are whole blocks, so a test point has no training well next to it."""
    return np.floor(np.asarray(x, float) / km).astype(np.int64) * 100003 + np.floor(np.asarray(y, float) / km).astype(np.int64)


def device() -> str:
    """Torch device for non-LLM work: cuda only when EARTH_DEVICE=cuda (the GPU arbiter gives the GPU to one consumer at a time)."""
    return os.environ.get("EARTH_DEVICE", "cpu")
