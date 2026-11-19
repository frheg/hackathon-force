"""Spatial layer: do nearby wells name green minerals more or less in the same formation? Residual over the formation rate.

Weights exp(-d/ell) over training units of the same formation (never the same wellbore). Local rate = (sum w*green + k*formation rate) / (sum w*rows + k):
`k` pseudo-rows shrink it to the formation rate. LLR = logit(local) - logit(formation). Assumption: a smooth regional trend of scale ell. LOG L014/L015.
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .base import logit
from .strat import Strat

KM_LAT = 110.57


def xy(df: pd.DataFrame, lat0: float = 60.0) -> np.ndarray:
    return np.c_[df.lon.to_numpy() * 111.32 * np.cos(np.radians(lat0)), df.lat.to_numpy() * KM_LAT]


class Spatial:
    name, title, needs = "spatial", "Neighbours", ("name", "lat", "lon", "wellbore", "n_green", "coverage")
    doc = "Neighbouring same-formation units' green-row share, beyond the formation rate."

    def __init__(self, ell: float = 20.0, k: float = 30.0, strat: Strat | None = None):
        self.ell, self.k, self._strat = ell, k, strat

    def fit(self, tr: pd.DataFrame):
        t = tr[tr.label >= 0]
        self.strat = self._strat or Strat().fit(tr)
        self.groups = {f: (cKDTree(xy(g)), g.n_green.to_numpy(float), g.coverage.to_numpy(float), g.wellbore.to_numpy()) for f, g in t.groupby("name")}
        return self

    def terms(self, df: pd.DataFrame) -> pd.DataFrame:
        """Per unit: sum w*green, sum w*rows, neighbours within 3 ell. Also feeds the explanation."""
        out = np.zeros((len(df), 3))
        P = xy(df)
        wb_df = df.wellbore.to_numpy()
        for f, idx in df.reset_index(drop=True).groupby("name").indices.items():
            if f not in self.groups:
                continue
            tree, ng, cov, wb = self.groups[f]
            for i, nb in zip(idx, tree.query_ball_point(P[idx], 3 * self.ell)):
                nb = np.array(nb, dtype=int)
                nb = nb[wb[nb] != wb_df[i]] if len(nb) else nb  # not the same wellbore: no self-leak
                if not len(nb):
                    continue
                w = np.exp(-np.linalg.norm(tree.data[nb] - P[i], axis=1) / self.ell)
                out[i] = ((w * ng[nb]).sum(), (w * cov[nb]).sum(), len(nb))
        return pd.DataFrame(out, columns=["wy", "wc", "n"], index=df.index)

    def llr(self, df: pd.DataFrame) -> pd.Series:
        t = self.terms(df)
        pf = df.name.map(lambda f: self.strat.table[f][0] if f in self.strat.table else self.strat.p0).to_numpy(float)
        local = (t.wy.to_numpy() + self.k * pf) / (t.wc.to_numpy() + self.k)
        return pd.Series(logit(local) - logit(pf), index=df.index)

    def params(self) -> dict:
        return {"ell_km": self.ell, "pseudo_rows": self.k, "reach_km": 3 * self.ell}

    def why(self, row: pd.Series) -> str:
        t = self.terms(pd.DataFrame([row])).iloc[0]
        return (f"{int(t.n)} same-formation units within {3 * self.ell:.0f} km; distance-weighted green share {t.wy / t.wc:.1%}" if t.n
                else f"no same-formation unit within {3 * self.ell:.0f} km: no effect")
