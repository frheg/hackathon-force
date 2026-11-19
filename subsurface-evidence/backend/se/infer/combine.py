"""Combine layers: posterior logit = base logit + sum of LLRs (NaN counts as 0 and is reported). Optional Platt calibration (binomial).

Assumption (stated, not hidden): layers are conditionally independent given the target. They are not fully (spatial and formation share
information; logs and text share the rock), so raw probabilities tend to be overconfident: calibration measures and corrects that. LOG L013.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from se.evidence import Logs, Spatial, Strat
from se.evidence.base import logit

ORDER = ("strat", "spatial", "logs")


def fit_layers(tr: pd.DataFrame, ell: float = 20.0, a: float = 30.0, k: float = 30.0, C: float = 0.3, n_boot: int = 0) -> dict:
    strat = Strat(a).fit(tr)
    return {"strat": strat, "spatial": Spatial(ell, k, strat).fit(tr), "logs": Logs(C, n_boot).fit(tr), "base": float(logit(strat.p0))}


def contributions(layers: dict, df: pd.DataFrame, use=ORDER) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["base"] = layers["base"]
    for n in ORDER:
        llr = layers[n].llr(df) if n in use else pd.Series(np.nan, index=df.index)
        out[n] = llr
        out[n + "_speaks"] = llr.notna()
    out["logit"] = out["base"] + out[list(ORDER)].fillna(0.0).sum(axis=1)
    out["p"] = 1 / (1 + np.exp(-out["logit"]))
    return out


class Platt:
    """Two-parameter map from raw logit to calibrated probability, fitted on out-of-fold predictions."""

    def fit(self, logit_raw, n_green, coverage):
        """Binomial fit on rows: n_green successes and coverage-n_green failures at each unit's raw logit."""
        x = np.asarray(logit_raw, float).reshape(-1, 1)
        ng, cov = np.asarray(n_green, float), np.asarray(coverage, float)
        self.m = LogisticRegression(C=1e6, max_iter=300).fit(np.vstack([x, x]), np.r_[np.ones(len(x)), np.zeros(len(x))], sample_weight=np.r_[ng, cov - ng])
        return self

    def __call__(self, logit_raw):
        return self.m.predict_proba(np.asarray(logit_raw).reshape(-1, 1))[:, 1]

    def params(self) -> dict:
        return {"slope": float(self.m.coef_[0][0]), "intercept": float(self.m.intercept_[0])}
