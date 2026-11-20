"""Audit measured-depth support and unresolved ties in the local Smeaheia release."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from se.config import DATA, OUT
from se.ingest.names import norm
from se.modeling import core_alignment
from se.modeling.artifacts import sha256, write_json
from se.modeling.seismic_coverage import RELATIVE_OUT as HULL_RECEIPT
from se.modeling.seismic_coverage import _registry
from se.modeling.smeaheia_velocity import LOG_32_2_1, LOG_32_4_1, _las_curve, _member
from se.modeling.smeaheia_velocity import RELATIVE_OUT as VELOCITY_RECEIPT

RESULT = Path("velocity/smeaheia_support_v2.json")
REPORT = "Reports/data/Troll_kystnaer_subsurface_status_report final_Gassnova.pdf"
PETROGRAPHY = "Well_Reports/data/32_4-1_Sedimentology_and_petrography.pdf"
MAX_LOG_GAP_M = 5.0
CURVES = ("GR", "RHOB", "NPHI", "DTC", "DTS")


def md_spans(depth) -> list[dict]:
    md = np.asarray(depth, dtype=float)
    md = np.sort(md[np.isfinite(md) & (md >= 0)])
    if not len(md):
        return []
    return [{"from_md_m": round(float(chunk[0]), 3), "to_md_m": round(float(chunk[-1]), 3), "samples": len(chunk)}
            for chunk in np.split(md, np.flatnonzero(np.diff(md) > MAX_LOG_GAP_M) + 1)]


def well_sources(well: dict, logs: pd.DataFrame, core: pd.DataFrame, units: pd.DataFrame) -> dict:
    key = norm(well["wellbore"])
    sample = logs[logs.name_key.eq(key)] if well["force_train_logs"] else logs.iloc[:0]
    c = core[core.npdid.eq(well["npdid"]) & core.name_key.eq(key) & core.md.ge(0) & np.isfinite(core.md)]
    u = units[units.name_key.eq(key) & units.label.ge(0) & np.isfinite(units.top) & np.isfinite(units.bot) & units.bot.gt(units.top)]
    paired_spans = []
    if not sample.empty and not c.empty:
        identity = pd.DataFrame([{"wellbore": well["wellbore"], "npdid": well["npdid"]}])
        try:
            pairs, _ = core_alignment.align(c, sample, identity, set())
        except ValueError as exc:
            if str(exc) != "no aligned log/porosity rows with verified well identity":
                raise
        else:
            eligible = np.isfinite(pairs[list(core_alignment.CURVES)]).all(axis=1)
            paired_spans = md_spans(pairs.loc[eligible, "md"])
    return {
        "force": {name: md_spans(sample.loc[np.isfinite(sample[name]), "DEPTH_MD"]) for name in CURVES},
        "realpore": {"rows": len(c), "porosity_rows": int(c.porosity.between(0, 100).sum()),
                     "spans": md_spans(c.md), "source_rows": c.index.tolist()},
        "report_intervals": [{"source_row": int(r.Index), "name": r.name, "from_md_m": r.top, "to_md_m": r.bot,
                              "trials": int(r.coverage)} for r in u.itertuples()],
        "porosity_log_pairs": {"rows": sum(s["samples"] for s in paired_spans), "spans": paired_spans},
    }


def build(data_root: Path = DATA, derived: Path = OUT) -> dict:
    survey_root = data_root / "seismic/smeaheia"
    hull_path = derived / HULL_RECEIPT
    velocity_path = derived / VELOCITY_RECEIPT
    coverage = json.loads(hull_path.read_text())
    velocity = json.loads(velocity_path.read_text())
    paths = {k: data_root / v["path"] for k, v in coverage["sources"].items() if k != "report_units"}
    paths["report_units"] = derived / "units.parquet"
    for k, path in paths.items():
        if sha256(path) != coverage["sources"][k]["sha256"]:
            raise ValueError(f"{k} differs from the hull receipt; rebuild the screen first")
    _, report = _member(survey_root / "reports.zip", REPORT, data_root)
    _, petrography = _member(survey_root / "well_reports.zip", PETROGRAPHY, data_root)
    archive_members = {"31/3-1": [], "32/2-1": [], "32/4-1": []}
    for well, member, name in (("32/2-1", LOG_32_2_1, "DT"), ("32/4-1", LOG_32_4_1, "HAC")):
        content, ref = _member(survey_root / "well_logs.zip", member, data_root)
        if ref["sha256"] != velocity["sources"][f"las_{well}"]["sha256"]:
            raise ValueError(f"stale GN1101 LAS receipt: {well}")
        md, values = _las_curve(content, name, "us/ft")
        archive_members[well].append({"source": ref, "kind": "sonic", "curve": name, "units": "us/ft", "spans": md_spans(md[values > 0])})
    _, picks = _member(survey_root / "well_reports.zip", velocity["sources"]["picks"]["member"], data_root)
    if picks["sha256"] != velocity["sources"]["picks"]["sha256"]:
        raise ValueError("stale GN1101 workbook receipt")
    logs = pd.read_csv(paths["wireline_training"], sep=";", usecols=["WELL", "DEPTH_MD", *CURVES])
    logs["name_key"] = logs.WELL.map(norm)
    core = pd.read_parquet(paths["core"], columns=["npdid", "wellbore", "md", "porosity"]).reset_index(drop=True)
    core["name_key"] = core.wellbore.map(norm)
    units = pd.read_parquet(paths["report_units"], columns=["wellbore", "name", "top", "bot", "label", "coverage"]).reset_index(drop=True)
    units["name_key"] = units.wellbore.map(norm)
    registry, unambiguous, _ = _registry(paths["register"])
    surveys = []
    for survey_id in ("gn1101", "tne01"):
        survey = next(s for s in coverage["surveys"] if s["id"] == survey_id)
        meta = derived / "seismic" / survey_id / "meta.json"
        xy = meta.with_name("xy.npy")
        if sha256(meta) != survey["meta_sha256"] or sha256(xy) != survey["geometry_sha256"]:
            raise ValueError(f"{survey_id}: seismic index differs from the hull receipt")
        timing = {k: v for k, v in json.loads(meta.read_text()).items() if k in {"t0_ms", "dt_ms", "t_end_ms"}}
        sites = [{**w, "in_hull": True, "role": "footprint_candidate"} for w in survey["wells"]]
        if survey_id == "tne01" and not any(w["npdid"] == 20 for w in sites):
            ref = registry.loc[registry.npdid.eq(20), "wellbore"].item()
            key = norm(ref)
            sites.append({"wellbore": ref, "npdid": 20, "in_hull": False, "role": "published_tie_reference",
                          "force_train_logs": key in unambiguous and logs.name_key.eq(key).any().item()})
        for w in sites:
            name = w["wellbore"]
            w.update(well_sources(w, logs, core, units))
            w["local_sonic"] = archive_members.get(name, [])
            w["raw_independent_time_depth"] = False
            w["tie_status"] = "no local verified tie"
            w["published_picks"] = []
            if name == "32/4-1":
                w["petrography_reference"] = {"source": petrography, "pdf_page": 30, "table": "3.1",
                                            "note": "Published core petrography, SEM and XRD context. Not matched to T2 or scored against the template."}
            if survey_id == "gn1101":
                control = next((c for c in velocity["controls"] if c["factpages"]["npdid"] == w["npdid"]), None)
                if control:
                    w["published_picks"] = control["picks"]
                    w["datum_issue"] = ("LAS OWT × 2 is 58.05–58.51 ms later than the workbook TWT; no shift applied."
                                        if name == "32/2-1" else "T2 workbook RKB is 23 m; parent FactPages RKB is 24 m. Do not merge the two paths.")
                    w["tie_status"] = "publisher picks only" if name == "32/2-1" else "T2 site context only"
            elif w["npdid"] == 20:
                w["tie_status"] = "checkshot tie reported; raw stations unavailable"
                w["report_reference"] = {"source": report, "pdf_page": 31, "section": "4.2.1",
                                         "note": "The figure caption says inline 1338; the paragraph says inline 338. Confirm before binding a trace."}
        surveys.append({"id": survey_id, "name": survey["name"], "indexed_time_ms": timing, "wells": sites})
    return {
        "schema_version": 1, "status": "coverage_audit", "activate_overlay": False,
        "independent_ties_verified": 0, "surveys": surveys, "source_roles": {
            "force": "Measured wireline in FORCE training only; finite curves by source MD (no run-to-run alignment).",
            "realpore": "Point samples in MD, not continuous core coverage. Data © GeoProvider (CC BY 4.0).",
            "reports": "Intervals with eligible descriptions for the green-clay evidence target, not lab mineralogy.",
            "published_picks": "Workbook interpretations, not checkshot stations. Preserve exact borehole label.",
            "porosity_log_pairs": "Finite GR/RHOB/NPHI within 0.5 m of valid plug MD, with duplicate log depths excluded. Not a time tie.",
        }, "log_gap_m": MAX_LOG_GAP_M,
        "sources": {**coverage["sources"], "hull_receipt": {"path": HULL_RECEIPT.as_posix(), "sha256": sha256(hull_path)},
                    "velocity_receipt": {"path": VELOCITY_RECEIPT.as_posix(), "sha256": sha256(velocity_path)},
                    "picks": picks, "tie_report": report, "petrography": {**petrography, "pdf_page": 30, "table": "3.1"}},
        "acquire": ["GN1101: raw checkshot/VSP and directional survey for 32/2-1; resolve the exact 32/4-1 T2 borehole separately.",
                    "GN1101: final processing datum and workbook horizon version; no blanket 58 ms correction.",
                    "TNE01: raw 31/3-1 controls and the correct inline; assess 31/3-3 as a separate holdout candidate."],
        "limits": ["The local footprint screen does not locate downhole trajectories or prove absence from the original survey.",
                   "Depth ranges group samples across gaps of at most 5 m for inventory; do not interpolate or fuse them.",
                   "The audit inventories the registered local inputs. It does not establish that missing raw files are unreleased.",
                   "TWT zero and the first indexed sample are not the seabed. No new depth conversion was enabled."],
        "credit": "Smeaheia data: Equinor and Gassnova. RealPore: GeoProvider (CC BY 4.0).",
        "implementation_sha256": {p.name: sha256(p) for p in (Path(__file__), Path(core_alignment.__file__))},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT / RESULT)
    output = parser.parse_args().output
    if output.exists():
        raise FileExistsError(f"preserve the existing audit; choose a different --output: {output}")
    receipt = build()
    write_json(output, receipt)
    print(json.dumps({s["id"]: {w["wellbore"]: w["tie_status"] for w in s["wells"]} for s in receipt["surveys"]}, indent=2))
