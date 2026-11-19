"""Log layer: do the logs look different from this formation's usual? Anomaly features -> logistic regression.

Each curve is turned into a robust z-score against the *formation's* training median (removes depth and formation, LOG L012). Weights are
learned; their signs are then checked against the sourced rules (se.knowledge). Only units with logs speak (7 % of labelled units).
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

FEATURES = ("GR", "RHOB", "NPHI", "PEF", "DTC", "RDEP", "DNSEP")


class Logs:
    name, title, needs = "logs", "Well logs", ("name", "n_green", "coverage") + FEATURES
    doc = "Log anomalies against the formation norm; learned weights; only where logs exist."

    def __init__(self, C: float = 0.3, n_boot: int = 100, seed: int = 0):
        self.C, self.n_boot, self.seed = C, n_boot, seed

    def z(self, df: pd.DataFrame) -> pd.DataFrame:
        z = pd.DataFrame(0.0, index=df.index, columns=FEATURES)
        for c in FEATURES:
            med = df.name.map(lambda f: self.norm.get((f, c), (self.glob[c][0], self.glob[c][1]))[0])
            mad = df.name.map(lambda f: self.norm.get((f, c), (self.glob[c][0], self.glob[c][1]))[1])
            z[c] = ((df[c] - med) / mad).clip(-5, 5)
        return z.fillna(0.0)  # a missing curve is "no anomaly", not a guess

    def _fit(self, t: pd.DataFrame):
        """Binomial fit: each unit is `n_green` successes and `coverage - n_green` failures at its anomaly vector (LOG L015)."""
        X = self.z(t).to_numpy()
        return LogisticRegression(C=self.C, max_iter=500).fit(np.vstack([X, X]), np.r_[np.ones(len(X)), np.zeros(len(X))],
                                                              sample_weight=np.r_[t.n_green.to_numpy(float), (t.coverage - t.n_green).to_numpy(float)])

    def fit(self, tr: pd.DataFrame):
        t = tr[(tr.label >= 0) & tr.GR.notna()].copy()
        self.norm, self.glob = {}, {}
        for c in FEATURES:
            v = t[c].dropna()
            self.glob[c] = (float(v.median()), float(max(1.4826 * (v - v.median()).abs().median(), 1e-6)))
            for f, g in t.groupby("name")[c]:
                g = g.dropna()
                if len(g) >= 8:
                    self.norm[(f, c)] = (float(g.median()), float(max(1.4826 * (g - g.median()).abs().median(), self.glob[c][1] * 0.25)))
        self.n_train = len(t)
        self.ok = len(t) >= 60 and t.n_green.sum() >= 10
        if self.ok:
            self.m = self._fit(t)
            self.coef = dict(zip(FEATURES, self.m.coef_[0]))
            rng, wells = np.random.default_rng(self.seed), t.wellbore.unique()  # sign stability: resample whole wells
            boots = []
            for _ in range(self.n_boot):
                pick = rng.choice(wells, len(wells))
                b = pd.concat([t[t.wellbore == w] for w in pick])
                if b.n_green.sum() > 0:
                    boots.append(self._fit(b).coef_[0])
            self.boot = np.array(boots)
        return self

    def llr(self, df: pd.DataFrame) -> pd.Series:
        out = pd.Series(np.nan, index=df.index)
        if not getattr(self, "ok", False):
            return out
        has = df.GR.notna()
        if has.any():
            out[has] = self.z(df[has]).to_numpy() @ self.m.coef_[0]  # weights only: the intercept is the base rate, owned by the combiner
        return out

    def params(self) -> dict:
        if not getattr(self, "ok", False):
            return {"trained": False}
        lo, hi = np.percentile(self.boot, [5, 95], axis=0) if len(self.boot) else (np.zeros(len(FEATURES)),) * 2
        return {"trained": True, "n_train": self.n_train, "C": self.C, "n_boot": len(self.boot),
                "weights": {c: {"w": round(float(self.coef[c]), 3), "p05": round(float(lo[i]), 3), "p95": round(float(hi[i]), 3),
                                "stable_sign": round(float((np.sign(self.boot[:, i]) == np.sign(self.coef[c])).mean()), 2) if len(self.boot) else None}
                            for i, c in enumerate(FEATURES)}}

    def why(self, row: pd.Series) -> str:
        if not getattr(self, "ok", False) or pd.isna(row.get("GR")):
            return "no logs for this unit"
        z = self.z(pd.DataFrame([row])).iloc[0]
        parts = sorted(((c, float(z[c]), float(z[c] * self.coef[c])) for c in FEATURES), key=lambda x: -abs(x[2]))[:3]
        return "; ".join(f"{c} {zz:+.1f} sd vs formation (effect {e:+.2f})" for c, zz, e in parts)
