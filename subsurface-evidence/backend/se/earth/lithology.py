"""Lithology per formation and column (PLAN P3.1, LOG L063).

Truth: FORCE 2020 expert lithofacies on the training wells (the hidden test file is never read). Per well and formation: the share of each
of the 12 FORCE classes. Estimate at a point: the formation's share, updated by nearby wells of the same formation with Gaussian weights
(length ell) and sample counts, shrunk to the formation mean with strength K (empirical Bayes in the simplest form):
    p = (K * p_formation + sum_i w_i n_i p_i) / (K + sum_i w_i n_i)
Report-text lithology (clay / sand / carbonate words in completion reports) can add pseudo-counts (weight TEXT_W per described row);
kept only if it helps held-out wells. Test: held-out 40 km blocks, per-sample accuracy and the FORCE penalty-matrix score against
the majority class and the formation mean.
"""
import json

import numpy as np
import pandas as pd

from se.config import DATA, EARTH
from se.earth import manifest
from se.earth.frame import FORCE_TRAIN, UTM31_TO_3035
from se.ingest.names import norm

CODES = [30000, 65030, 65000, 80000, 74000, 70000, 70032, 88000, 86000, 99000, 90000, 93000]
NAMES = ["sandstone", "sandstone/shale", "shale", "marl", "dolomite", "limestone", "chalk", "halite", "anhydrite", "tuff", "coal", "basement"]
GROUPED = {"sand": [0], "shale": [2], "heterolithic": [1], "carbonate": [3, 4, 5, 6], "other": [7, 8, 9, 10, 11]}
TEXT_MAP = {"sand": 0, "clay": 2, "carbonate": 5}
PENALTY = FORCE_TRAIN.parent / "penalty_matrix.npy"


def translit(s: str) -> str:
    return s.replace("Å", "AA").replace("Ø", "OE").replace("Æ", "AE")


def unit_name(s: str) -> str:
    """FORCE writes Sodir names in ASCII (ROEDBY FM.); map back to the Sodir spelling (RØDBY FM) so units join with the tops."""
    if not isinstance(s, str):
        return None
    u = s.upper().replace(" FM.", " FM").replace(" GP.", " GP").replace(" SST.", " SS").strip()
    u = SODIR.get(u, u)
    return u if u in SODIR.values() or not u.endswith(" MB.") else SODIR.get(u.replace(" MB.", " FM"), u)  # FORCE member = Sodir formation


SODIR = {translit(n): n for n in set(pd.read_parquet(EARTH / "tops.parquet").name.dropna())}


def samples() -> pd.DataFrame:
    f = pd.read_csv(FORCE_TRAIN, sep=";", usecols=["WELL", "DEPTH_MD", "X_LOC", "Y_LOC", "GROUP", "FORMATION", "FORCE_2020_LITHOFACIES_LITHOLOGY"])
    f = f.dropna(subset=["FORCE_2020_LITHOFACIES_LITHOLOGY", "X_LOC", "Y_LOC"])
    f["wellbore"] = f.WELL.map(norm)
    w = pd.read_parquet(EARTH / "wells.parquet"); pw = set(w[w.pilot].wellbore)
    f = f[f.wellbore.isin(pw)]
    f["k"] = f.FORCE_2020_LITHOFACIES_LITHOLOGY.astype(int).map({c: i for i, c in enumerate(CODES)})
    f["unit"] = f.FORMATION.map(unit_name).fillna(f.GROUP.map(unit_name))
    x, y = UTM31_TO_3035.transform(f.X_LOC.to_numpy(), f.Y_LOC.to_numpy())
    f["x"], f["y"] = x / 1000, y / 1000
    return f.dropna(subset=["unit", "k"])


def text_counts() -> pd.DataFrame:
    """Report-text lithology words per well and unit, by MD within the Sodir tops of that well."""
    from se.earth.pressure import _interval, unit_at

    d = pd.read_parquet(DATA / "atlas" / "reporttext" / "descriptions.parquet")
    d = d[d.lith.isin(TEXT_MAP) & d.depth_from.notna()]
    d["wellbore"] = d.wellbore.map(norm)
    w = pd.read_parquet(EARTH / "wells.parquet"); w = w[w.pilot].set_index("wellbore")
    d = d[d.wellbore.isin(w.index)]
    iv = _interval(pd.read_parquet(EARTH / "tops.parquet"))
    d["unit"] = [unit_at(iv, a, b)[0] for a, b in zip(d.wellbore, d.depth_from)]
    d = d.dropna(subset=["unit"])
    g = d.groupby(["wellbore", "unit", "lith"]).size().unstack(fill_value=0).reset_index()
    g["x"], g["y"] = g.wellbore.map(w.x), g.wellbore.map(w.y)
    return g


def well_table(s: pd.DataFrame) -> pd.DataFrame:
    """Counts per (well, unit, class) and the well position."""
    c = s.groupby(["wellbore", "unit", "k"]).size().unstack(fill_value=0)
    c = c.reindex(columns=range(len(CODES)), fill_value=0)
    pos = s.groupby("wellbore")[["x", "y"]].median()
    c = c.reset_index(); c["x"], c["y"] = c.wellbore.map(pos.x), c.wellbore.map(pos.y)
    return c


def estimate(train: pd.DataFrame, X, unit, ell, K, text=None, text_w=0.0, prior=None):
    """Class shares (n, 12) at points X for one unit, from training counts of that unit (and optional text pseudo-counts)."""
    cols = list(range(len(CODES)))
    t = train[train.unit == unit]
    base = prior if prior is not None else np.full(len(CODES), 1.0 / len(CODES))
    if len(t):
        tot = t[cols].to_numpy().sum(0); base = (tot + 1.0 * base) / (tot.sum() + 1.0)
    num = np.tile(K * base, (len(X), 1)); den = np.full(len(X), K)
    if len(t):
        C = t[cols].to_numpy().astype(float); n = C.sum(1); P = C / np.maximum(n, 1)[:, None]
        d2 = ((X[:, None, :] - t[["x", "y"]].to_numpy()[None]) ** 2).sum(-1); wgt = np.exp(-0.5 * d2 / ell ** 2) * np.minimum(n, 500)[None]
        num += wgt @ P; den += wgt.sum(1)
    if text is not None and text_w > 0:
        tt = text[text.unit == unit]
        if len(tt):
            P = np.zeros((len(tt), len(CODES))); n = np.zeros(len(tt))
            for lith, k in TEXT_MAP.items():
                if lith in tt:
                    P[:, k] += tt[lith].to_numpy(); n += tt[lith].to_numpy()
            P = P / np.maximum(n, 1)[:, None]
            d2 = ((X[:, None, :] - tt[["x", "y"]].to_numpy()[None]) ** 2).sum(-1); wgt = np.exp(-0.5 * d2 / ell ** 2) * (text_w * np.minimum(n, 50))[None]
            num += wgt @ P; den += wgt.sum(1)
    return num / den[:, None]


def cv(s, wt, text, ell, K, text_w, folds=5):
    from sklearn.model_selection import GroupKFold

    from se.earth.surfaces import blocks

    pos = s.groupby("wellbore")[["x", "y"]].median()
    bl = blocks(pos.x.to_numpy(), pos.y.to_numpy()); wells = pos.index.to_numpy()
    P = np.load(PENALTY)
    hit = {"model": 0, "formation": 0, "majority": 0}; pen = {"model": 0.0, "formation": 0.0, "majority": 0.0}; n = 0; brier = {"model": 0.0, "formation": 0.0}
    prior = np.bincount(s.k, minlength=len(CODES)) / len(s)
    for tr, te in GroupKFold(min(folds, len(np.unique(bl)))).split(wells, groups=bl):
        trw, tew = set(wells[tr]), set(wells[te])
        a = wt[wt.wellbore.isin(trw)]
        maj = int(np.argmax(np.bincount(s[s.wellbore.isin(trw)].k, minlength=len(CODES))))
        tx = text[~text.wellbore.isin(tew)] if text is not None else None
        for (wb, u), g in s[s.wellbore.isin(tew)].groupby(["wellbore", "unit"]):
            X = np.array([[g.x.median(), g.y.median()]])
            pm = estimate(a, X, u, ell, K, tx, text_w, prior)[0]; pf = estimate(a, X, u, 1e-6, 1.0, None, 0.0, prior)[0]
            truth = g.k.to_numpy().astype(int); m = len(truth); n += m
            for key, p in (("model", pm), ("formation", pf)):
                k = int(np.argmax(p)); hit[key] += int((truth == k).sum()); pen[key] += float(P[truth, k].sum())
                obs = np.bincount(truth, minlength=len(CODES)) / m; brier[key] += float(((p - obs) ** 2).sum()) * m
            hit["majority"] += int((truth == maj).sum()); pen["majority"] += float(P[truth, maj].sum())
    return {"samples": n, **{f"accuracy_{k}": round(v / n, 4) for k, v in hit.items()}, **{f"penalty_score_{k}": round(-v / n, 4) for k, v in pen.items()},
            **{f"brier_{k}": round(v / n, 4) for k, v in brier.items()}}


def from_text(text: pd.DataFrame) -> pd.DataFrame:
    """Where no FORCE well exists (Norwegian Sea, Barents: P8), report-text rock words are the only lithology: clay -> shale, sand -> sandstone,
    carbonate -> limestone, as counts per well and unit in the FORCE class columns. Weaker evidence (L063: it did not help where FORCE exists)."""
    wt = pd.DataFrame({"wellbore": text.wellbore, "unit": text.unit, "x": text.x, "y": text.y})
    for k in range(len(CODES)):
        wt[k] = 0
    for lith, k in TEXT_MAP.items():
        if lith in text:
            wt[k] = text[lith].to_numpy()
    return wt[wt[list(range(len(CODES)))].sum(1) > 0]


def build() -> dict:
    s = samples(); text = text_counts()
    if not len(s):
        wt = from_text(text); wt.to_parquet(EARTH / "lithology_wells.parquet"); text.to_parquet(EARTH / "lithology_text.parquet")
        out = {"source": "report text only (no FORCE wells in this region)", "well_units": int(len(wt)), "wells": int(wt.wellbore.nunique()), "units": int(wt.unit.nunique()),
               "chosen": {"ell_km": 25.0, "K": 300.0, "text_w": 1.0}, "note": "not scored against FORCE labels: none here"}
        (EARTH / "lithology_report.json").write_text(json.dumps(out, indent=1)); return out
    wt = well_table(s)
    grid = []
    for ell in (10.0, 25.0, 60.0):
        for K in (50.0, 300.0, 2000.0):
            grid.append(({"ell_km": ell, "K": K, "text_w": 0.0}, cv(s, wt, None, ell, K, 0.0)))
    best = min(grid, key=lambda r: -r[1]["penalty_score_model"])
    with_text = [({**best[0], "text_w": tw}, cv(s, wt, text, best[0]["ell_km"], best[0]["K"], tw)) for tw in (0.2, 1.0)]
    chosen = max([best] + with_text, key=lambda r: r[1]["penalty_score_model"])
    out = {"force_pilot_wells": int(s.wellbore.nunique()), "samples": int(len(s)), "units": int(s.unit.nunique()), "text_rows_used": int(text[[c for c in TEXT_MAP if c in text]].to_numpy().sum()),
           "search": [{**p, **r} for p, r in grid], "text_ablation": [{**p, **r} for p, r in with_text], "chosen": {**chosen[0], **chosen[1]},
           "classes": NAMES, "grouped": GROUPED}
    wt.to_parquet(EARTH / "lithology_wells.parquet"); text.to_parquet(EARTH / "lithology_text.parquet")
    (EARTH / "lithology_report.json").write_text(json.dumps(out, indent=1))
    manifest.write(EARTH / "lithology_wells.parquet", [FORCE_TRAIN, EARTH / "tops.parquet", EARTH / "wells.parquet"], {"codes": CODES})
    return out


if __name__ == "__main__":
    o = build()
    print({k: v for k, v in o.items() if k not in ("search", "text_ablation")})
    for r in o["search"]:
        print(r)
    for r in o["text_ablation"]:
        print("text", r)
