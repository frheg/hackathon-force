"""Does wireline add skill beyond a formation label for measured plug porosity?"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import OneHotEncoder

from se.config import DATA, OUT
from se.modeling import core_alignment
from se.modeling.artifacts import sha256, write_json
from se.modeling.seismic_coverage import _project, _registry

OUTPUT = Path("porosity_ablation_v3")
BLOCK_KM = 40
BUFFER_KM = 10
SEED = 7
STRATA = ["formation", "group"]
COMPARISONS = ("global_mean", "formation_prior", "formation_group", "logs", "formation_group_logs")


def folds(d: pd.DataFrame):
    sites = d[["npdid", "x_km", "y_km", "block"]].drop_duplicates()
    for train, test in GroupKFold(5).split(sites, groups=sites.block):
        a, b = sites.iloc[train], sites.iloc[test]
        distance = cKDTree(b[["x_km", "y_km"]]).query(a[["x_km", "y_km"]])[0]
        keep = a[distance >= BUFFER_KM]
        yield d.npdid.isin(keep.npdid).to_numpy(), d.npdid.isin(b.npdid).to_numpy(), len(a) - len(keep)


def _weights(d: pd.DataFrame) -> pd.Series:
    # Equal weight per well and, within each well, per unique log sample.
    by_log = 1 / d.groupby("log_row").log_row.transform("size")
    return by_log / by_log.groupby(d.npdid).transform("sum")


def formation_prior(train: pd.DataFrame, test: pd.DataFrame, weights: pd.Series) -> np.ndarray:
    average = np.average(train.porosity, weights=weights)
    stats = train.assign(weighted_y=train.porosity * weights, weight=weights)
    g = stats[stats.group != "UNKNOWN"].groupby("group")[["weighted_y", "weight"]].sum()
    f = stats[stats.formation != "UNKNOWN"].groupby(STRATA)[["weighted_y", "weight"]].sum()
    group = test.group.map(g.weighted_y / g.weight).fillna(average).to_numpy()
    formation = (f.weighted_y / f.weight).reindex(pd.MultiIndex.from_frame(test[STRATA])).to_numpy()
    return np.where(np.isfinite(formation), formation, group)


def fit_oof(d: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    result = d.copy()
    specs = {"formation_group": (True, False), "logs": (False, True), "formation_group_logs": (True, True)}
    for k in COMPARISONS:
        result[k] = np.nan
    result["fold"] = -1
    receipts = []
    for fold, (train, test, n_purged) in enumerate(folds(d)):
        a, b = d.iloc[train], d.iloc[test]
        if a.empty or b.empty:
            raise ValueError(f"fold {fold} has no remaining train or test rows")
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        ca, cb = encoder.fit_transform(a[STRATA]), encoder.transform(b[STRATA])
        wa = _weights(a)
        result.loc[test, "fold"] = fold
        result.loc[test, "global_mean"] = np.average(a.porosity, weights=wa)
        result.loc[test, "formation_prior"] = formation_prior(a, b, wa)
        la, lb = a[list(core_alignment.CURVES)].to_numpy(), b[list(core_alignment.CURVES)].to_numpy()

        def features(categories, logs, use_strata, use_logs):
            return np.column_stack(([categories] if use_strata else []) + ([logs] if use_logs else []))

        for key, spec in specs.items():
            model = HistGradientBoostingRegressor(max_iter=180, learning_rate=0.06, max_depth=4,
                                                 l2_regularization=1.0, early_stopping=False, random_state=SEED)
            model.fit(features(ca, la, *spec), a.porosity, sample_weight=wa / wa.mean())
            result.loc[test, key] = model.predict(features(cb, lb, *spec))
        receipts.append({"fold": fold, "train_npdids": sorted(map(int, a.npdid.unique())),
                         "held_out_npdids": sorted(map(int, b.npdid.unique())), "held_out_blocks": sorted(b.block.unique()),
                         "buffered_train_wells_excluded": n_purged,
                         "test_rows": len(b), "test_rows_with_known_formation": int(b.formation.isin(a.formation.unique()).sum())})
    if (result.fold < 0).any() or result[list(COMPARISONS)].isna().any().any():
        raise ValueError("some eligible rows were never scored")
    return result, receipts


def metrics(oof: pd.DataFrame) -> dict:
    w = _weights(oof)
    by_well = oof[["npdid", "block"]].copy()
    scores, per_well = {}, {}
    for key in COMPARISONS:
        e = oof[key] - oof.porosity
        scores[key] = {"rmse_pp": float(np.sqrt(np.average(e**2, weights=w))), "mae_pp": float(np.average(abs(e), weights=w))}
        by_well[key] = w * e**2
        per_well[key] = np.sqrt(by_well[key].groupby(oof.npdid).sum())
    blocks = by_well.groupby("block")
    totals = blocks[["formation_group", "formation_prior", "formation_group_logs"]].sum().to_numpy()
    counts = blocks.npdid.nunique().to_numpy()
    ix = np.random.default_rng(SEED).integers(0, len(totals), (2000, len(totals)))
    rmses = np.sqrt(totals[ix].sum(axis=1) / counts[ix].sum(axis=1)[:, None])
    return {"well_weighted": scores, "per_well_rmse_pp": pd.DataFrame(per_well).round(4).to_dict(orient="index"),
            "gain_with_logs_rmse_pp": scores["formation_group"]["rmse_pp"] - scores["formation_group_logs"]["rmse_pp"],
            "gain_block_bootstrap_90_pp": np.percentile(rmses[:, 0] - rmses[:, 2], [5, 95]).tolist(),
            "gain_vs_formation_prior_rmse_pp": scores["formation_prior"]["rmse_pp"] - scores["formation_group_logs"]["rmse_pp"],
            "gain_vs_formation_prior_block_bootstrap_90_pp": np.percentile(rmses[:, 1] - rmses[:, 2], [5, 95]).tolist(),
            "bootstrap_unit": "40 km block, paired out-of-fold errors; not a prediction interval"}


def run(data_root: Path = DATA, out: Path = OUT / OUTPUT) -> dict:
    if out.exists():
        raise FileExistsError(f"preserve the existing benchmark; choose a different --output: {out}")
    db = data_root / "ncs.duckdb"
    wells = core_alignment.registry(db)
    linked, audit, sources = core_alignment.read_training(data_root, wells, set())
    logs = pd.read_csv(sources["logs"], sep=";", usecols=["FORMATION", "GROUP"])
    aligned_with_labels = linked.join(logs.rename(columns={"FORMATION": "formation", "GROUP": "group"}), on="log_row")
    known_wells, unambiguous, _ = _registry(db)
    known_wells = known_wells[known_wells.name_key.isin(unambiguous)]
    xy = _project(known_wells, 3035) / 1000
    known_wells = known_wells.assign(x_km=xy[:, 0], y_km=xy[:, 1])
    d = aligned_with_labels.merge(known_wells[["npdid", "x_km", "y_km"]], on="npdid", validate="many_to_one")
    matched_coords = len(d)
    d = d[np.isfinite(d[list(core_alignment.CURVES)]).all(axis=1)].reset_index(drop=True)
    for col in ("formation", "group"):
        d[col] = d[col].str.strip().str.upper().replace("", "UNKNOWN").fillna("UNKNOWN")
    d["block"] = (d.x_km // BLOCK_KM).astype(int).astype(str) + ":" + (d.y_km // BLOCK_KM).astype(int).astype(str)
    oof, split = fit_oof(d)
    result = {
        "status": "research_only", "target": "RealPore compiled lab plug porosity (%)",
        "attribution": "Data are © GeoProvider https://geoprovider.no/ and licensed CC-BY 4.0",
        "scope": "FORCE training wells only; no hidden-test data, seismic, or rock-physics-template scores.",
        "rows": len(oof), "wells": int(oof.npdid.nunique()), "blocks": int(oof.block.nunique()),
        "missing_verified_coordinate_rows": len(linked) - matched_coords, "incomplete_log_rows": matched_coords - len(d),
        "curves": list(core_alignment.CURVES), "join": audit,
        "estimator": {"family": "HistGradientBoostingRegressor", "max_iter": 180, "max_depth": 4,
                      "learning_rate": 0.06, "l2_regularization": 1.0, "seed": SEED, "selection": "fixed; no fold tuning"},
        "split": {"block_km": BLOCK_KM, "buffer_km": BUFFER_KM, "crs": "EPSG:3035", "folds": split},
        "scores": metrics(oof),
        "limits": ["Formation/group labels and complete logs must be available at prediction time.",
                   "Compiled assays and selective coring; not exhaustive or standardized ground truth.",
                   "Nearby reported depths may have run-specific datum offsets. No seismic coupling or regional map evaluated."],
        "sources": {name: {"path": str(path.relative_to(data_root)), "sha256": sha256(path)} for name, path in sources.items()},
        "implementation_sha256": {p.name: sha256(p) for p in (Path(__file__), Path(core_alignment.__file__))},
    }
    out.mkdir(parents=True)
    oof.to_parquet(out / "oof.parquet", index=False)
    write_json(out / "metrics.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT / OUTPUT)
    receipt = run(out=parser.parse_args().output)
    print(json.dumps({k: v for k, v in receipt["scores"].items() if k != "per_well_rmse_pp"}, indent=2))
