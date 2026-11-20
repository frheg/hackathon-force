"""Compare raw measured logs and rock-physics transforms on the same core plugs."""

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from se.config import DATA, OUT
from se.earth import rpt
from se.modeling.artifacts import sha256, write_json
from se.modeling.porosity_ablation import (
    BLOCK_KM,
    BUFFER_KM,
    OUTPUT,
    SEED,
    _weights,
    folds,
)

RESULT = Path("rock_porosity_v2")
RAW = ["GR", "RHOB", "NPHI", "DTC", "DTS", "depth_below_seabed_m"]
ELASTIC = ["density_phi_pct", "ai", "vpvs", "shear_gpa", "bulk_gpa"]
RPT = ["density_phi_mixed_pct", "cement_index"]


def physics(d: pd.DataFrame) -> pd.DataFrame:
    vp, vs = rpt.US_FT / d.DTC.to_numpy(), rpt.US_FT / d.DTS.to_numpy()
    rho = d.RHOB.to_numpy()
    _, _, quartz = rpt.QZ
    _, brine = rpt.FLUIDS["brine"]
    density_phi = 100 * (quartz - rho) / (quartz - brine)
    return d.assign(density_phi_pct=density_phi, ai=vp * rho / 1000, vpvs=vp / vs,
                    shear_gpa=rho * (vs / 1000) ** 2, bulk_gpa=rho * (vp**2 - 4 / 3 * vs**2) / 1e6)


def sand_domain(d: pd.DataFrame) -> pd.DataFrame:
    k, g, mineral_density = rpt.vrh(d.gr_index.to_numpy())
    phi = (mineral_density - d.RHOB.to_numpy()) / (mineral_density - rpt.FLUIDS["brine"][1])
    d = d.assign(density_phi_mixed_pct=100 * phi)
    use = (
        d["FORCE_2020_LITHOFACIES_LITHOLOGY"].isin(rpt.SAND)
        & d.gr_index.lt(rpt.VALID["clay_max"])
        & pd.Series(phi, index=d.index).between(*rpt.VALID["phi"])
    )
    index = np.flatnonzero(use)
    p = (2.3 - 1.03) * 9.81 * d.depth_below_seabed_m.to_numpy()[index] / 1000
    _, gf = rpt.friable(phi[index], k[index], g[index], p)
    _, gc = rpt.contact_cement(phi[index], k[index], g[index])
    s = d.iloc[index].copy()
    return s.assign(cement_index=np.clip((s.shear_gpa - gf) / np.maximum(gc - gf, 1e-6), -0.5, 1.5))


def compare(d: pd.DataFrame, raw: list[str], extra: list[str]) -> tuple[pd.DataFrame, dict]:
    result = d.reset_index(drop=True).copy()
    result["fixed_density"] = result.density_phi_pct.clip(0, 100)
    scores = {"raw_logs": raw, "raw_plus_physics": raw + extra}
    for name in scores:
        result[name] = np.nan
    result["fold"] = -1
    splits = []
    for fold, (train, test, purged) in enumerate(folds(result)):
        a, b = result.loc[train], result.loc[test]
        if a.empty or b.empty:
            raise ValueError(f"fold {fold} is empty after purging neighbours")
        weights = _weights(a)
        for key, features in scores.items():
            model = HistGradientBoostingRegressor(max_iter=180, learning_rate=0.06, max_depth=4,
                                                 l2_regularization=1.0, early_stopping=False, random_state=SEED)
            model.fit(a[features], a.porosity, sample_weight=weights / weights.mean())
            result.loc[test, key] = model.predict(b[features])
        result.loc[test, "fold"] = fold
        splits.append({"fold": fold, "train_npdids": sorted(map(int, a.npdid.unique())),
                       "held_out_npdids": sorted(map(int, b.npdid.unique())), "purged_wells": purged})
    if result.fold.lt(0).any() or result[list(scores)].isna().any().any():
        raise ValueError("not all eligible rows received scores")
    return result, {"rows": len(result), "wells": int(result.npdid.nunique()), "blocks": int(result.block.nunique()),
                    "split": splits, "features": scores, **metrics(result)}


def metrics(d: pd.DataFrame) -> dict:
    names = ["fixed_density", "raw_logs", "raw_plus_physics"]
    weights = _weights(d)
    delta = d[names].sub(d.porosity, axis=0)
    squared = delta.pow(2).mul(weights, axis=0)
    wells = squared.groupby(d.npdid).sum()
    blocks = squared.groupby(d.block).sum()
    n = d.groupby("block").npdid.nunique().to_numpy()

    def interval(totals, denom):
        indexes = np.random.default_rng(SEED).integers(0, len(totals), (2000, len(totals)))
        rmse = np.sqrt(totals[indexes].sum(axis=1) / denom[indexes].sum(axis=1)[:, None])
        return np.percentile(rmse[:, 1] - rmse[:, 2], [5, 95]).tolist()

    rmse = np.sqrt(squared.sum() / weights.sum())
    return {"rmse_pp": rmse.to_dict(), "mae_pp": (delta.abs().mul(weights, axis=0).sum() / weights.sum()).to_dict(),
            "per_well_rmse_pp": np.sqrt(wells).round(4).to_dict(orient="index"),
            "gain_pp": float(rmse["raw_logs"] - rmse["raw_plus_physics"]),
            "gain_block_bootstrap_90_pp": interval(blocks.to_numpy(), n),
            "gain_well_bootstrap_90_pp": interval(wells.to_numpy(), np.ones(len(wells)))}


def run(data_root: Path = DATA, derived: Path = OUT, output: Path = OUT / RESULT) -> dict:
    if output.exists():
        raise FileExistsError(f"preserve the existing result; use a different --output: {output}")
    base = derived / OUTPUT
    base_receipt = json.loads((base / "metrics.json").read_text())
    paths = {key: data_root / info["path"] for key, info in base_receipt["sources"].items()}
    for key, path in paths.items():
        if sha256(path) != base_receipt["sources"][key]["sha256"]:
            raise ValueError(f"stale base join: {key}")
    cols = ["npdid", "wellbore", "core_row", "md", "porosity", "log_row", "DEPTH_MD", "log_minus_core_md_m",
            "GR", "RHOB", "NPHI", "x_km", "y_km", "block"]
    cohort = pd.read_parquet(base / "oof.parquet", columns=cols)
    logs = pd.read_csv(paths["logs"], sep=";", usecols=["WELL", "GR", "DTC", "DTS", "Z_LOC", "FORCE_2020_LITHOFACIES_LITHOLOGY"])
    g = logs.groupby("WELL").GR
    lo, hi = g.transform("quantile", q=0.05), g.transform("quantile", q=0.95)
    logs["gr_index"] = ((logs.GR - lo) / (hi - lo).clip(lower=1)).clip(0, 1)
    d = cohort.join(logs.drop(columns=["GR", "WELL"]), on="log_row", validate="many_to_one")
    with duckdb.connect(str(paths["well_registry"]), read_only=True) as db:
        water = db.execute("""
            select wlbNpdidWellbore npdid, wlbWaterDepth water_depth_m from wellbore_exploration
            union all select wlbNpdidWellbore, wlbWaterDepth from wellbore_development
        """).df()
    d = d.merge(water, on="npdid", how="left", validate="many_to_one")
    d["depth_below_seabed_m"] = -d.Z_LOC - d.water_depth_m
    eligible = d.DTC.between(40, 200) & d.DTS.between(60, 600) & d.RHOB.between(1.6, 3) & d.depth_below_seabed_m.gt(100)
    d = physics(d.loc[eligible & np.isfinite(d.depth_below_seabed_m)])
    d = d[d.bulk_gpa.gt(0)]
    scored, main = compare(d, RAW, ELASTIC)
    sand = sand_domain(d)
    enough = sand.npdid.nunique() >= 10 and sand.block.nunique() >= 5
    sand_scored, secondary = compare(sand, [*RAW, "gr_index"], [*ELASTIC, *RPT]) if enough else (None, {
        "status": "insufficient_support", "rows": len(sand), "wells": int(sand.npdid.nunique()), "blocks": int(sand.block.nunique()),
        "minimum_wells": 10, "minimum_blocks": 5,
    })
    sources = {**base_receipt["sources"], "base_receipt": {"path": str(base / "metrics.json"), "sha256": sha256(base / "metrics.json")},
               "base_core_log_join": {"path": str(base / "oof.parquet"), "sha256": sha256(base / "oof.parquet")}}
    receipt = {"status": "research_only", "target": "RealPore measured plug porosity (%)",
               "attribution": "Data are © GeoProvider https://geoprovider.no/ and licensed CC-BY 4.0",
               "base_rows": len(cohort), "block_km": BLOCK_KM, "buffer_km": BUFFER_KM, "crs": "EPSG:3035",
               "main": main, "template_sand": secondary, "sources": sources,
               "implementation_sha256": {p.name: sha256(p) for p in (Path(__file__), Path(rpt.__file__), Path(folds.__code__.co_filename))},
               "density_baseline": "2.65 g/cm³ quartz and 1.04 g/cm³ brine; clipped to [0,100]%",
               "limits": ["Complete measured sonic and density only; no predicted shear, test-set labels, or seismic inputs.",
                          "Template sand cohort uses the existing sand labels and a full-well GR index, not independent mineralogy.",
                          "Intervals resample paired held-out residuals, not deployment prediction uncertainty. Plugs represent sampled wells, not undrilled cells."]}
    output.mkdir(parents=True)
    scored.to_parquet(output / "measured_sonic_oof.parquet", index=False)
    if sand_scored is not None:
        sand_scored.to_parquet(output / "template_sand_oof.parquet", index=False)
    write_json(output / "metrics.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT / RESULT)
    result = run(output=parser.parse_args().output)
    print(json.dumps({tag: {k: v for k, v in result[tag].items() if k != "split" and k != "per_well_rmse_pp"}
                      for tag in ("main", "template_sand")}, indent=2))
