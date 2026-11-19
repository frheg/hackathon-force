"""Seismic layer: PLANNED, not implemented. Registered so the frame is complete and the UI can say so.

Interface when built: needs per-unit attributes (e.g. mean amplitude, coherence, spectral shape) extracted from a cube at the unit's position and
two-way time (needs a well-seismic tie: Sleipner/Smeaheia after the licence step, see ../../docs/seismic-data.md). Until then it returns NaN.
"""
import numpy as np
import pandas as pd


class Seismic:
    name, title, needs = "seismic", "Seismic", ()
    doc = "Planned: seismic attributes at the unit. Needs a cube with wells (Sleipner/Smeaheia)."
    implemented = False

    def fit(self, tr: pd.DataFrame):
        return self

    def llr(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series(np.nan, index=df.index)

    def params(self) -> dict:
        return {"implemented": False}

    def why(self, row: pd.Series) -> str:
        return "not implemented yet"
