"""Stratigraphy layer: share of described rows naming a green mineral, per formation, against the overall share.

Rate target (LOG L015): a unit has `coverage` described rows, `n_green` of them name a green mineral. Pooled per formation and smoothed toward the
overall rate with `a` pseudo-rows. Assumption: rows are trials with one rate per formation (rows of one rock are correlated: calibrate, bootstrap by well).
"""
import pandas as pd

from .base import logit


class Strat:
    name, title, needs = "strat", "Formation", ("name", "n_green", "coverage")
    doc = "Share of trials that succeed in this group (formation, area) vs overall."
    words = {"rows": "described rows", "hit": "name a green mineral", "short": "green"}

    def __init__(self, a: float = 30.0):
        self.a = a

    def fit(self, tr: pd.DataFrame):
        t = tr[tr.label >= 0]
        self.p0 = float(t.n_green.sum() / t.coverage.sum())
        g = t.groupby("name")[["n_green", "coverage"]].sum()
        self.table = {k: ((r.n_green + self.a * self.p0) / (r.coverage + self.a), int(r.coverage), int(r.n_green)) for k, r in g.iterrows()}
        return self

    def llr(self, df: pd.DataFrame) -> pd.Series:
        b = logit(self.p0)
        return df.name.map(lambda f: logit(self.table[f][0]) - b if f in self.table else 0.0).astype(float)

    def params(self) -> dict:
        top = sorted(self.table.items(), key=lambda kv: -kv[1][1])[:40]
        return {"a_rows": self.a, "base_rate": round(self.p0, 4), "formations": {k: {"rate": round(v[0], 3), "rows": v[1], "green_rows": v[2]} for k, v in top}}

    def why(self, row: pd.Series) -> str:
        v = self.table.get(row["name"])
        return f"{row['name']}: {v[2]} of {v[1]} {self.words['rows']} {self.words['hit']} ({v[0]:.1%} smoothed) vs {self.p0:.1%} overall" if v else f"{row['name']}: not in training, no effect"
