"""Knowledge base: sourced rules, each tested against the data. A rule is never trusted and never hidden: the verdict is shown next to it.

Verdicts: agrees (interval entirely on the predicted side) / disagrees (entirely on the other side) / inconclusive / not_testable.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from se.config import OUT

RULES = Path(__file__).parent / "rules" / "green_clay.yaml"


def load() -> dict:
    kb = yaml.safe_load(RULES.read_text())
    for r in kb["rules"]:  # provenance is mandatory: a rule without a source is rejected, not defaulted
        if not r.get("sources") or r.get("status") not in ("sourced", "sourced_unverified", "inferred"):
            raise ValueError(f"rule {r.get('id')}: needs sources and a status")
    return kb


def _side(lo: float, hi: float, centre: float, want: str) -> str:
    if lo > centre:
        return "agrees" if want == "+" else "disagrees"
    if hi < centre:
        return "agrees" if want == "-" else "disagrees"
    return "inconclusive"


def _boot_rate(u: pd.DataFrame, name: str, n: int = 300, seed: int = 0):
    """Green share of clay rows in one formation, with a well-resampled 90 % interval."""
    rng, by = np.random.default_rng(seed), {w: g for w, g in u[u.name == name].groupby("wellbore")}
    if len(by) < 5:
        return None
    wells, v = list(by), []
    for _ in range(n):
        s = pd.concat([by[w] for w in rng.choice(wells, len(wells))])
        v.append(s.n_green.sum() / s.coverage.sum())
    g = u[u.name == name]
    return float(g.n_green.sum() / g.coverage.sum()), float(np.percentile(v, 5)), float(np.percentile(v, 95)), len(by)


def check(units: pd.DataFrame | None = None) -> list:
    """Every rule with its verdict and the numbers behind it."""
    kb = load()
    u = units if units is not None else pd.read_parquet(OUT / "units.parquet")
    u = u[u.label >= 0]
    rows = {}
    for lith in ("clay", "sand"):
        p = OUT / f"row_logs_{lith}.json"
        if p.exists():
            rows[lith] = json.loads(p.read_text())
    out = []
    for r in kb["rules"]:
        c = r["check"]
        v = {"verdict": "not_testable", "numbers": c.get("why", "")}
        if c["type"] == "row_auc":
            parts, verdicts = [], []
            for lith, j in rows.items():
                a = j["univariate_auc"].get(c["feature"])
                if a:
                    verdicts.append(_side(a["p05"], a["p95"], 0.5, c["direction"]))
                    parts.append(f"{lith} rows: AUC {a['auc']:.2f} [{a['p05']:.2f}, {a['p95']:.2f}] ({j['green_rows']} green rows, {j['wells']} wells)")
            v = {"verdict": ("agrees" if "agrees" in verdicts and "disagrees" not in verdicts else "disagrees" if "disagrees" in verdicts and "agrees" not in verdicts
                             else "inconclusive") if verdicts else "not_testable", "numbers": "; ".join(parts) or "no row-level result yet: run scripts/exp_row_logs.py"}
        elif c["type"] == "rate_order":
            a, b = _boot_rate(u, c["higher"]), _boot_rate(u, c["lower"])
            if a and b:
                v = {"verdict": "agrees" if a[1] > b[2] else "disagrees" if a[2] < b[1] else "inconclusive",
                     "numbers": f"{c['higher']} {a[0]:.1%} [{a[1]:.1%}, {a[2]:.1%}] ({a[3]} wells) vs {c['lower']} {b[0]:.1%} [{b[1]:.1%}, {b[2]:.1%}] ({b[3]} wells)"}
        elif c["type"] == "rate_vs_overall":
            a = _boot_rate(u, c["formation"])
            base = float(u.n_green.sum() / u.coverage.sum())
            if a:
                v = {"verdict": _side(a[1], a[2], base, c["direction"]), "numbers": f"{c['formation']} {a[0]:.1%} [{a[1]:.1%}, {a[2]:.1%}] ({a[3]} wells) vs overall {base:.1%}"}
        out.append({"id": r["id"], "statement": r["statement"], "status": r["status"], "caveat": r.get("caveat", ""), "sources": r["sources"], **v})
    return out
