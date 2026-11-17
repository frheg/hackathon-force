"""Trains Log Lens's lithology model on the FORCE 2020 training wells and predicts the 10 held-out wells.

    uv run python -m sketches.train_logs

A gradient-boosted tree model (scikit-learn) on the log curves, depth, position and stratigraphic group, much like
the competition's top entries. Takes a few minutes on the CPU. Writes data/force2020/{wells.parquet,metrics.json}.
"""

import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from common import DATA_DIR

D = DATA_DIR / "force2020"
# the competition's lithology codes, in the order of its penalty matrix
LITHOLOGY = {
    30000: "Sandstone",
    65030: "Sandstone/Shale",
    65000: "Shale",
    80000: "Marl",
    74000: "Dolomite",
    70000: "Limestone",
    70032: "Chalk",
    88000: "Halite",
    86000: "Anhydrite",
    99000: "Tuff",
    90000: "Coal",
    93000: "Basement",
}
CODE = {c: i for i, c in enumerate(LITHOLOGY)}
CURVES = ["CALI", "RSHA", "RMED", "RDEP", "RHOB", "GR", "SGR", "NPHI", "PEF", "DTC", "SP", "BS", "ROP", "DTS", "DCAL", "DRHO"]
RESISTIVITY = ["RSHA", "RMED", "RDEP"]
KEEP = ["WELL", "DEPTH_MD", "GROUP", "FORMATION", "GR", "RHOB", "NPHI", "DTC", "RDEP", "RMED", "PEF", "CALI"]


def features(df: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    x = df[CURVES + ["DEPTH_MD", "X_LOC", "Y_LOC", "Z_LOC"]].copy()
    for c in RESISTIVITY:
        x[c] = np.log10(x[c].clip(lower=1e-3))
    x["GROUP"] = pd.Categorical(df["GROUP"], categories=groups).codes  # -1 when missing
    return x


def main() -> None:
    t0 = time.time()
    train = pd.read_csv(D / "train.csv", sep=";")
    test = pd.read_csv(D / "hidden_test.csv", sep=";")
    groups = sorted(set(train["GROUP"].dropna()) | set(test["GROUP"].dropna()))
    # every 2nd sample: neighbours 15 cm apart add little, and it halves the time
    train = train.iloc[::2]
    y = train["FORCE_2020_LITHOFACIES_LITHOLOGY"].map(CODE)
    print(f"{len(train)} training samples from {train['WELL'].nunique()} wells, {len(test)} test samples")

    model = HistGradientBoostingClassifier(
        max_iter=250, learning_rate=0.08, max_leaf_nodes=63, l2_regularization=1.0, early_stopping=False,
        categorical_features=["GROUP"], random_state=0,
    )
    model.fit(features(train, groups), y)
    print(f"trained in {time.time() - t0:.0f} s, {model.n_iter_} iterations")

    proba = model.predict_proba(features(test, groups))
    pred = model.classes_[proba.argmax(1)]
    true = test["FORCE_2020_LITHOFACIES_LITHOLOGY"].map(CODE).to_numpy()
    penalty = np.load(D / "penalty_matrix.npy")
    out = test[KEEP].copy()
    out["TRUE"] = true
    out["PRED"] = pred
    out["CONFIDENCE"] = proba.max(1).round(3)
    out.to_parquet(D / "wells.parquet", index=False)

    per_well = {
        w: {"accuracy": round(float((g["TRUE"] == g["PRED"]).mean()), 3), "samples": len(g)}
        for w, g in out.groupby("WELL")
    }
    metrics = {
        "accuracy": round(float((true == pred).mean()), 3),
        # the competition's score: minus the mean penalty, 0 is perfect; the winner scored about -0.47 on these wells
        "score": round(float(-penalty[true, pred].mean()), 3),
        "wells": per_well,
        "lithology": list(LITHOLOGY.values()),
        "train_wells": int(train["WELL"].nunique()),
    }
    (D / "metrics.json").write_text(json.dumps(metrics, indent=1))
    print(f"accuracy {metrics['accuracy']}, score {metrics['score']}, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
