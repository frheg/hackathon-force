"""Spatial layer: do nearby wells name green minerals more or less in the same formation? Residual over the formation rate.

Weights exp(-d/ell) over training units of the same formation (never the same wellbore). Local rate = (sum w*green + k*formation rate) / (sum w*rows + k):
`k` pseudo-rows shrink it to the formation rate. LLR = logit(local) - logit(formation). Assumption: a smooth regional trend of scale ell. LOG L014/L015.
"""
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

from .base import logit
from .strat import Strat

KM_LAT = 110.57  # retained for the UI-only display frame; model distances use EPSG:3035
PROJECTED = Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True)


def project(lon, lat) -> np.ndarray:
    """EPSG:3035 equal-area coordinates in km, appropriate across the North Sea latitude range."""
    x, y = PROJECTED.transform(np.asarray(lon, float), np.asarray(lat, float))
    return np.c_[x, y] / 1000.0


def xy(df: pd.DataFrame, lat0: float = 60.0) -> np.ndarray:
    return project(df.lon.to_numpy(), df.lat.to_numpy())


class Spatial:
    name, title, needs = "spatial", "Neighbours", ("name", "lat", "lon", "wellbore", "n_green", "coverage")
    doc = "Neighbouring same-group units' success share, beyond the group rate."
    words = {"rows": "described rows", "hit": "name a green mineral", "short": "green"}

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
        return (f"{int(t.n)} same-group units within {3 * self.ell:.0f} km; distance-weighted share ({self.words["short"] if hasattr(self, "words") else "green"}) {t.wy / t.wc:.1%}" if t.n
                else f"no same-group unit within {3 * self.ell:.0f} km: no effect")
