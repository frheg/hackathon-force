"""Compare log-to-core estimates with the Sleipner interpreted PHIF curve."""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from se.config import DATA, OUT
from se.ingest.names import norm
from se.modeling import core_alignment
from se.modeling.artifacts import sha256, write_json

ROOT = Path("seismic/sleipner-benchmark-2019/extracted/well_data/data/Wells_released_2011")
WELLS = {
    "15/9-13": ROOT / "Well 159_13/159-13 Logs.las",
    "15/9-A-16": ROOT / "Well 159_A16/159-A-16.las",
}
CURVES = core_alignment.CURVES
UNITS = {"DEPTH": "M", "GR": "API", "RHOB": "G/CM3", "NPHI": "V/V_DECIMAL", "PHIF": "V/V_DECIMAL"}


def las(path: Path, well: str) -> pd.DataFrame:
    lines = path.read_text().splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("~A ")), None)
    if start is None:
        raise ValueError(f"{path.name}: expected a named LAS data section")
    names = lines[start].split()[1:]
    units, values = {}, {}
    section = ""
    for line in lines[:start]:
        if line.startswith("~"):
            section = line[1].upper()
        if section not in {"V", "W", "C"}:
            continue
        match = re.match(r"^\s*([\w-]+)\s*\.([^\s:]*)\s*([^:]*):", line)
        if match:
            key, unit, value = match.groups()
            if section == "C":
                units[key.upper()] = unit.upper()
            else:
                values[key.upper()] = value.strip()
    if norm(values.get("WELL")) != well or values.get("WRAP") != "NO":
        raise ValueError(f"{path.name}: unexpected well identity or wrapped LAS")
    if len(set(names)) != len(names) or not set(UNITS).issubset(names) or any(units.get(k) != u for k, u in UNITS.items()):
        raise ValueError(f"{path.name}: missing/duplicate column or unexpected curve unit")
    if "NULL" not in values:
        raise ValueError(f"{path.name}: missing LAS null marker")
    d = pd.DataFrame(np.loadtxt(lines[start + 1:], ndmin=2), columns=names)
    d = d.replace(float(values["NULL"]), np.nan)
    if not np.isfinite(d.DEPTH).all() or not (np.diff(d.DEPTH.to_numpy()) > 0).all():
        raise ValueError(f"{path.name}: expected strictly increasing measured depth")
    return d.rename(columns={"DEPTH": "DEPTH_MD"}).assign(las_line=np.arange(len(d)) + start + 2)


def held_out_ids(wells: pd.DataFrame) -> set[int]:
    names = wells.wellbore.map(norm)
    test = names.isin(WELLS)
    if test.sum() != len(WELLS) or set(names[test]) != set(WELLS):
        raise ValueError("could not resolve both Sleipner well identities uniquely")
    # Whole 15/9 block and named Sleipner fields, not just the two LAS aliases.
    by_field = wells.field.str.strip().str.upper().str.startswith("SLEIPNER ", na=False)
    return set(wells.loc[by_field | names.str.startswith("15/9-") | test, "npdid"].astype(int))


def score(y: np.ndarray, p: np.ndarray) -> dict | None:
    if not len(y):
        return None
    r = p - y
    return {"n": len(y), "rmse_pp": float(np.sqrt(np.mean(r**2))), "mae_pp": float(np.mean(abs(r))),
            "bias_pp": float(np.mean(r))}


def run(data_root: Path = DATA, out: Path = OUT / "sleipner_transfer_v2") -> dict:
    wells = core_alignment.registry(data_root / "ncs.duckdb")
    excluded = held_out_ids(wells)
    links, audit, sources = core_alignment.read_training(data_root, wells, excluded)
    fit = links.loc[np.isfinite(links[list(CURVES)]).all(axis=1)].copy()
    if fit.empty or fit.npdid.isin(excluded).any():
        raise ValueError("empty or contaminated transfer training set")
    fit["weight"] = 1 / fit.groupby("log_row").log_row.transform("size")
    x = fit[list(CURVES)]
    limits = pd.DataFrame({"min": x.min(), "max": x.max()})
    model = HistGradientBoostingRegressor(max_iter=180, learning_rate=0.06, max_depth=4,
                                         l2_regularization=1.0, early_stopping=False, random_state=7)
    model.fit(x, fit.porosity, sample_weight=fit.weight)
    med = float(fit.porosity.median())
    report, predictions = {}, []
    for name, relative in WELLS.items():
        path = data_root / relative
        d = las(path, name)
        valid = d.PHIF.between(0, 1)
        features = d[list(CURVES)]
        present = np.isfinite(features).all(axis=1)
        use = valid & present
        in_range = features.ge(limits["min"]).all(axis=1) & features.le(limits["max"]).all(axis=1)
        pred = np.full(len(d), np.nan)
        if use.any():
            pred[use] = model.predict(features.loc[use])
        y = (d.PHIF.where(valid) * 100).to_numpy()
        baselines = {"train_median": np.full(len(d), med), "tree": pred, "nphi": d.NPHI.to_numpy() * 100,
                     "sand_brine_density": ((2.65 - d.RHOB.to_numpy()) / (2.65 - 1.03)) * 100}
        report[name] = {
            "npdid": int(wells.loc[wells.wellbore.map(norm).eq(name), "npdid"].iloc[0]),
            "samples": len(d), "valid_phif": int(valid.sum()), "complete_features_and_phif": int(use.sum()),
            "status": "scored" if use.any() else "no_valid_phif_and_logs",
            "md_range_m": [float(d.DEPTH_MD.min()), float(d.DEPTH_MD.max())],
            "scored_md_range_m": [float(d.loc[use, "DEPTH_MD"].min()), float(d.loc[use, "DEPTH_MD"].max())] if use.any() else None,
            "metrics_same_rows": {k: score(y[use], v[use]) for k, v in baselines.items()},
            "metrics_marginal_train_ranges_only": {k: score(y[use & in_range], v[use & in_range]) for k, v in baselines.items()},
            "outside_at_least_one_training_curve_range": int((use & ~in_range).sum()),
            "source": {"path": str(relative), "sha256": sha256(path)},
        }
        predictions.append(pd.DataFrame({"wellbore": name, "las_line": d.las_line, "depth_md_m": d.DEPTH_MD,
                                         "phif_percent": y, "scored": use, "within_marginal_train_ranges": in_range,
                                         **{f"{k}_percent": v for k, v in baselines.items()}}))
    result = {
        "schema_version": 2, "status": "research_only",
        "dataset": "Sleipner 2019 Benchmark Model, DOI 10.11582/2020.00004",
        "realpore_attribution": "Data are © GeoProvider https://geoprovider.no/ and licensed CC-BY 4.0",
        "model": "FORCE/RealPore HistGradientBoosting; GR, RHOB, NPHI complete cases",
        "fit_scope": "Exclude block 15/9 and named Sleipner fields by FactPages NPDID; FORCE train only.",
        "target": "LAS PHIF (v/v converted to percent): interpreted porosity, not an independent core assay",
        "train": {**audit, "complete_curve_rows": len(fit), "complete_curve_wells": int(fit.npdid.nunique()),
                  "training_npdids": sorted(map(int, fit.npdid.unique())), "excluded_npdids": sorted(excluded),
                  "curve_ranges": limits.to_dict(orient="index"), "median_porosity_percent": med},
        "wells": report,
        "limitations": [
            "PHIF may be derived from the same input curves. A score measures agreement, not true porosity accuracy.",
            "Depth samples in a well are correlated. No confidence interval, field-wide estimate or formation attribution.",
            "Training uses the compiled RealPore best-available porosity, not one standardized assay. MD offsets are not a run-by-run datum correction.",
            "Range agreement is a marginal check only. No absolute MD or RT transferred; no permeability, volumetric, or seismic inference.",
        ],
        "sources": {k: {"path": str(p.relative_to(data_root)), "sha256": sha256(p)} for k, p in sources.items()},
        "implementation_sha256": {p.name: sha256(p) for p in (Path(__file__), Path(core_alignment.__file__))},
    }
    out.mkdir(parents=True, exist_ok=True)
    fit.to_parquet(out / "training_links.parquet", index=False)
    pd.concat(predictions, ignore_index=True).to_parquet(out / "predictions.parquet", index=False)
    write_json(out / "metrics.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(run()["wells"], indent=2, allow_nan=False))
