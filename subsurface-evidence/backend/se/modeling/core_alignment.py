"""Auditable porosity links from registry-backed core plugs to FORCE training logs."""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from se.ingest.names import norm

CURVES = ("GR", "RHOB", "NPHI")
MAX_OFFSET_M = 0.5


def registry(path: Path) -> pd.DataFrame:
    with duckdb.connect(str(path), read_only=True) as db:
        return db.execute("""
            select wlbNpdidWellbore npdid, wlbWellboreName wellbore, wlbField field from wellbore_exploration
            union all
            select wlbNpdidWellbore npdid, wlbWellboreName wellbore, wlbField field from wellbore_development
        """).df()


def align(core: pd.DataFrame, logs: pd.DataFrame, wells: pd.DataFrame, excluded_ids: set[int]) -> tuple[pd.DataFrame, dict]:
    # Save the file-relative row positions before filtering or sorting for the receipt.
    core = core.assign(core_row=np.arange(len(core)), wellbore=core.wellbore.map(norm))
    logs = logs.assign(log_row=np.arange(len(logs)), wellbore=logs.WELL.map(norm))
    wells = wells.dropna(subset=["wellbore", "npdid"]).copy()
    wells["wellbore"] = wells.wellbore.map(norm)
    wells = wells[~wells.wellbore.duplicated(keep=False) & ~wells.npdid.duplicated(keep=False)]
    available = core[core.wellbore.isin(logs.wellbore)]
    linked = available.merge(wells[["npdid", "wellbore"]], on=["npdid", "wellbore"], validate="many_to_one")
    excluded = linked.npdid.isin(excluded_ids)
    plugs = linked[~excluded & linked.md.between(0, np.inf, inclusive="left") & linked.porosity.between(0, 100)]
    logs = logs[logs.wellbore.isin(plugs.wellbore) & logs.DEPTH_MD.between(0, np.inf, inclusive="left")].copy()
    # Do not silently select one row from a contradictory duplicate log depth.
    logs["duplicate_depth"] = logs.duplicated(["wellbore", "DEPTH_MD"], keep=False)
    by_well = dict(tuple(logs.groupby("wellbore", sort=False)))
    output = []
    for well, p in plugs.groupby("wellbore", sort=True):
        if well not in by_well:
            continue
        q = by_well[well].sort_values("DEPTH_MD", kind="stable")
        z, md = q.DEPTH_MD.to_numpy(), p.md.to_numpy()
        j = np.searchsorted(z, md)
        left, right = np.clip(j - 1, 0, len(z) - 1), np.clip(j, 0, len(z) - 1)
        pick = np.where(abs(z[right] - md) < abs(z[left] - md), right, left)
        delta = z[pick] - md
        keep = (md >= z[0]) & (md <= z[-1]) & (abs(delta) <= MAX_OFFSET_M) & ~q.duplicate_depth.to_numpy()[pick]
        if keep.any():
            obs = p.iloc[keep][["npdid", "wellbore", "core_row", "md", "porosity"]].reset_index(drop=True)
            samples = q.iloc[pick[keep]][["log_row", "DEPTH_MD", *CURVES]].reset_index(drop=True)
            output.append(pd.concat([obs, samples], axis=1).assign(log_minus_core_md_m=delta[keep]))
    if not output:
        raise ValueError("no aligned log/porosity rows with verified well identity")
    matched = pd.concat(output, ignore_index=True)
    return matched, {
        "cores_in_named_log_wells": len(available), "unresolved_identity_rows": len(available) - len(linked),
        "held_out_core_rows": int(excluded.sum()), "eligible_core_rows": len(plugs),
        "joined_rows": len(matched), "joined_wells": int(matched.npdid.nunique()),
        "reused_log_sample_links": int(matched.log_row.duplicated().sum()),
        "max_offset_m": MAX_OFFSET_M,
    }


def read_training(data_root: Path, wells: pd.DataFrame, excluded_ids: set[int]) -> tuple[pd.DataFrame, dict, dict[str, Path]]:
    sources = {
        "core": data_root / "official/realpore/realpore.parquet",
        "logs": data_root / "force2020/train.csv",
        "well_registry": data_root / "ncs.duckdb",
    }
    core = pd.read_parquet(sources["core"], columns=["npdid", "wellbore", "md", "porosity"])
    logs = pd.read_csv(sources["logs"], sep=";", usecols=["WELL", "DEPTH_MD", *CURVES])
    matched, audit = align(core, logs, wells, excluded_ids)
    return matched, audit, sources
