"""The contract of an evidence layer. One layer = one kind of data = one log-likelihood ratio (LLR) per unit.

LLR > 0: this layer raises the odds of the target. NaN: the layer cannot speak (no data): it adds nothing and says so.
Add a data type: write a Layer, register it in se/evidence/__init__.py. Nothing else changes.
"""
from typing import Protocol

import numpy as np
import pandas as pd


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


class Layer(Protocol):
    name: str  # id used in tables and the UI
    title: str  # short label
    needs: tuple  # columns it reads from the unit table
    doc: str  # one line: what it does and its main assumption

    def fit(self, tr: pd.DataFrame) -> "Layer": ...

    def llr(self, df: pd.DataFrame) -> pd.Series: ...

    def params(self) -> dict: ...

    def why(self, row: pd.Series) -> str: ...
