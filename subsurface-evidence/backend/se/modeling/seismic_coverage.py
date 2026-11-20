"""Screen wells for seismic tie work, without treating surface overlap as a tie."""

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import Delaunay, cKDTree

from se.config import DATA, OUT
from se.ingest.names import norm
from se.modeling.artifacts import sha256, write_json

RELATIVE_OUT = Path("velocity/seismic_coverage.json")


def _registry(path: Path) -> tuple[pd.DataFrame, set[str], dict]:
    fields = ("wlbNpdidWellbore npdid, wlbWellboreName wellbore, wlbGeodeticDatum datum, "
              "wlbUtmZone zone, wlbEwUtm east_m, wlbNsUtm north_m")
    with duckdb.connect(str(path), read_only=True) as db:
        raw = db.execute(f"""
            select {fields} from wellbore_exploration
            union all
            select {fields} from wellbore_development order by npdid
        """).df()
    if raw.npdid.isna().any() or raw.npdid.duplicated().any():
        raise ValueError("FactPages site screen requires unique non-null NPDIDs")
    raw["name_key"] = raw.wellbore.map(norm)
    valid_xy = raw.east_m.between(0, 1_000_000) & raw.north_m.between(0, 10_000_000)
    known = raw.datum.eq("ED50") & raw.zone.between(28, 38).fillna(False) & valid_xy.fillna(False)
    unambiguous = set(raw.loc[raw.wellbore.notna() & ~raw.name_key.duplicated(keep=False), "name_key"])
    counts = {"registry_wells": len(raw), "screened": int(known.sum()), "excluded_unresolved_coordinates": int((~known).sum())}
    return raw[known].copy(), unambiguous, counts


def sites_in_trace_hull(traces: np.ndarray, sites_xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if traces.ndim != 2 or traces.shape[1] != 2 or not np.isfinite(traces).all():
        raise ValueError("unexpected indexed XY trace geometry")
    inside = Delaunay(traces).find_simplex(sites_xy) >= 0
    return inside, cKDTree(traces).query(sites_xy[inside])[0]


def _project(sites: pd.DataFrame, epsg: int) -> np.ndarray:
    groups = sites.groupby("zone").indices
    xy = np.empty((len(sites), 2), dtype=float)
    for zone, ix in groups.items():
        x, y = Transformer.from_crs(23000 + int(zone), epsg, always_xy=True).transform(
            sites.east_m.iloc[ix].to_numpy(), sites.north_m.iloc[ix].to_numpy(),
        )
        xy[ix, :] = np.column_stack((x, y))
    return xy


def build(data_root: Path, out_root: Path) -> dict:
    paths = {
        "register": data_root / "ncs.duckdb",
        "core": data_root / "official/realpore/realpore.parquet",
        "wireline_training": data_root / "force2020/train.csv",
        "report_units": out_root / "units.parquet",
    }
    sites, unambiguous, counts = _registry(paths["register"])
    core = pd.read_parquet(paths["core"], columns=["npdid", "wellbore", "md"])
    core["name_key"] = core.wellbore.map(norm)
    matched = core[np.isfinite(core.md) & core.md.ge(0)].merge(sites[["npdid", "name_key"]], on=["npdid", "name_key"], how="inner")
    core_counts = matched.groupby("npdid").size().to_dict()
    logs = set(pd.read_csv(paths["wireline_training"], sep=";", usecols=["WELL"]).WELL.dropna().map(norm))
    report_units = pd.read_parquet(paths["report_units"], columns=["wellbore", "label", "coverage"])
    report_units["name_key"] = report_units.wellbore.map(norm)
    labelled = report_units[report_units.label.ge(0)].groupby("name_key").agg(units=("label", "size"), trials=("coverage", "sum"))
    surveys, seen = [], set()
    for meta_path in sorted((out_root / "seismic").glob("*/meta.json")):
        meta = json.loads(meta_path.read_text())
        if meta["dataset"] not in {"smeaheia", "sleipner"}:
            continue
        epsg = meta["epsg"]
        if epsg != 23031:
            raise ValueError(f"{meta['id']}: verify survey CRS before site screening")
        trace_path = meta_path.with_name("xy.npy")
        traces = np.load(trace_path, allow_pickle=False)
        inside, distances = sites_in_trace_hull(traces, _project(sites, epsg))
        wells = []
        for r, d in zip(sites[inside].itertuples(), distances, strict=True):
            units, trials = labelled.loc[r.name_key] if r.name_key in unambiguous and r.name_key in labelled.index else (0, 0)
            wells.append({
                "wellbore": r.wellbore, "npdid": int(r.npdid), "nearest_indexed_trace_m": round(float(d), 2),
                "force_train_logs": r.name_key in unambiguous and r.name_key in logs,
                "core_rows_with_matching_id_and_name": int(core_counts.get(r.npdid, 0)),
                "labelled_report_intervals": int(units), "eligible_report_trials": int(trials),
                "time_depth_tie": "not established by this screen",
            })
        seen.update(r["npdid"] for r in wells)
        surveys.append({
            "id": meta["id"], "dataset": meta["dataset"], "name": meta["name"], "epsg": epsg,
            "indexed_traces": len(traces), "geometry_sha256": sha256(trace_path), "meta_sha256": sha256(meta_path),
            "well_count": len(wells), "wells": wells,
        })
    if not surveys:
        raise ValueError("no locally indexed Smeaheia/Sleipner surveys to screen")
    return {
        "schema_version": 1, "status": "coverage_audit", "registry": counts, "distinct_wells_in_footprints": len(seen),
        "scope": "Convex hull of the decimated indexed trace positions and registry wellhead XY; not well trajectories, seismic illumination, or a time-depth tie.",
        "sources": {name: {"path": str(path.relative_to(data_root)) if path.is_relative_to(data_root) else str(path),
                           "sha256": sha256(path)} for name, path in paths.items()},
        "implementation_sha256": sha256(Path(__file__)),
        "limitations": [
            "A convex hull can include holes; nearest retained trace distance is reported, not used as an acceptance threshold.",
            "Only explicit ED50 UTM-well coordinates are screened. Nonstandard/unspecified datums remain unresolved.",
            "Core joins check both NPDID and normalized wellbore; FORCE training and report intervals use unambiguous well names only. These are counts, not depth alignment.",
            "An overlap across Sleipner processing variants or vintages is not an independent training well. No FORCE hidden test rows were read.",
        ], "surveys": surveys,
    }


def main() -> None:
    result = build(DATA, OUT)
    path = OUT / RELATIVE_OUT
    write_json(path, result)
    print(json.dumps({"artifact": str(path), "distinct_wells": result["distinct_wells_in_footprints"],
                      "surveys": {s["id"]: s["well_count"] for s in result["surveys"]}}, indent=2))


if __name__ == "__main__":
    main()
