"""Log features per unit from the FORCE 2020 wells (the only open logs we hold: 98 train + 10 hidden-test wells).

Run: uv run python -m se.ingest.logs   (needs units.parquet)
Features are medians over the samples inside the unit, plus the density-neutron separation. Units with fewer than MIN_SAMPLES are left empty.
"""
import numpy as np
import pandas as pd

from se.config import DATA, OUT
from se.ingest.names import norm

CURVES = ("GR", "RHOB", "NPHI", "PEF", "DTC", "RDEP")
MIN_SAMPLES = 20  # 0.15 m spacing: 3 m of rock
RHO_MATRIX, RHO_FLUID = 2.65, 1.0  # sandstone matrix, fresh water: for the density-neutron separation (an assumption, LOG L012)


def read() -> pd.DataFrame:
    parts = []
    for f in ("train.csv", "hidden_test.csv"):
        p = DATA / "force2020" / f
        if p.exists():
            parts.append(pd.read_csv(p, sep=";", usecols=["WELL", "DEPTH_MD", *CURVES]))
    d = pd.concat(parts, ignore_index=True)
    d["wellbore"] = d.WELL.map(norm)
    d["RDEP"] = np.log10(d.RDEP.where(d.RDEP > 0))
    return d.drop(columns="WELL").sort_values(["wellbore", "DEPTH_MD"])


def features(units: pd.DataFrame) -> pd.DataFrame:
    logs = read()
    out = []
    for w, g in logs.groupby("wellbore"):
        u = units[units.wellbore == w]
        if u.empty:
            continue
        z = g.DEPTH_MD.to_numpy()
        for uid, top, bot in zip(u.index, u.top, u.bot):
            a, b = np.searchsorted(z, [top, bot])
            if b - a < MIN_SAMPLES:
                continue
            s = g.iloc[a:b]
            row = {"uid": uid, "n_log": b - a}
            for c in CURVES:
                row[c] = s[c].median()
            dphi = ((RHO_MATRIX - s.RHOB) / (RHO_MATRIX - RHO_FLUID)).clip(-0.2, 0.8)
            row["DNSEP"] = (s.NPHI - dphi).median()
            out.append(row)
    f = pd.DataFrame(out).set_index("uid")
    f.to_parquet(OUT / "log_features.parquet")
    return f


if __name__ == "__main__":
    u = pd.read_parquet(OUT / "units.parquet")
    f = features(u)
    j = u.join(f, how="inner")
    lab = j[j.label >= 0]
    print(f"log features for {len(f)} units in {j.wellbore.nunique()} wellbores; labelled {len(lab)} ({lab.label.mean():.1%} positive) in {lab.wellbore.nunique()} wellbores")
    print("share of the 12,976 labelled units that have logs:", f"{len(lab) / (u.label >= 0).sum():.1%}")
    print(lab[list(CURVES) + ["DNSEP"]].notna().mean().round(2).to_dict())
    print(lab.groupby("label")[list(CURVES) + ["DNSEP"]].median().round(2).to_string())
