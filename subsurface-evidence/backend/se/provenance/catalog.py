"""Canonical, inspectable inventory of every dataset root used by the project.

Sizes and file counts are observed from disk. Counts, licences, and limitations are
explicit metadata: they describe evidence quality, not ground truth.
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path

from se.config import DATA, OUT, PROJECT

DATASETS = [
    {"id": "factpages", "name": "Sodir FactPages", "path": "ncs.duckdb", "origin": "earlier", "license": "NLOD 2.0", "source": "Sodir FactPages CSV exports", "kind": "primary-structured", "modality": ["well", "formation", "test", "production", "reserve", "licence"], "grain": "tables keyed by wellbore, field, discovery, licence and NPDID", "rows": "22 tables; exact table counts in /api/catalog", "used_by": ["studio", "subsurface-evidence"], "truth": "official register; can disagree with reports and may be revised", "limitations": ["not raw measurements", "formation/group tops overlap", "coordinates and depth references require checks"]},
    {"id": "sodir_csv", "name": "Sodir FactPages source CSV", "path": "sodir", "origin": "earlier", "license": "NLOD 2.0", "source": "Sodir public CSV export", "kind": "source-copy", "modality": ["structured"], "grain": "one CSV per FactPages table", "rows": "source for ncs.duckdb", "used_by": ["fetch_data.py"], "truth": "source export", "limitations": ["duplicated by ncs.duckdb", "refresh-dependent"]},
    {"id": "completion", "name": "NCS completion reports", "path": "official/completion_reports", "origin": "mail", "license": "CC BY 4.0 (organiser distribution; individual source metadata retained)", "source": "FORCE/Sodir Zenodo completion-report package", "kind": "primary-documents", "modality": ["pdf", "json", "ocr-markdown", "tables", "figures"], "grain": "page/document/wellbore", "rows": "about 4,441 wells, 5,327 JSON, 5,453 PDFs; exact disk count below", "used_by": ["green-clay extraction", "atlas", "report-text targets"], "truth": "reported observations; AI summaries/tags are model-derived", "limitations": ["OCR/layout uncertainty", "duplicate report variants", "historical terminology", "reporting effort bias"]},
    {"id": "official_text", "name": "Cross-basin report text", "path": "official/text", "origin": "mail", "license": "CC BY 4.0 per Zenodo corpus", "source": "FORCE 2023 OCR corpus", "kind": "primary-text", "modality": ["text", "ocr", "language-quality"], "grain": "page", "rows": "2.75M Norway Diskos pages plus UK, Netherlands and relinquishment reports", "used_by": ["retrieval candidate corpus", "atlas profiles"], "truth": "OCR representation, not authoritative source", "limitations": ["only 29% Norway Diskos pages classified as natural language", "overlaps completion reports", "duplicates and OCR gibberish"]},
    {"id": "force2020_las", "name": "FORCE 2020 LAS", "path": "official/force2020", "origin": "mail", "license": "CC BY 4.0", "source": "FORCE 2020 Zenodo record 4351156", "kind": "primary-logs", "modality": ["wireline", "lithology labels", "headers"], "grain": "depth sample / well", "rows": "118 wells in organiser copy", "used_by": ["log exploration", "data doctor"], "truth": "expert/competition lithology labels", "limitations": ["not mineralogical truth", "sample and curve missingness", "class imbalance"]},
    {"id": "force2020_csv", "name": "FORCE 2020 CSV + benchmark", "path": "force2020", "origin": "earlier", "license": "CC BY 4.0", "source": "FORCE 2020 competition", "kind": "derived-training", "modality": ["wireline features", "lithology labels"], "grain": "15 cm log sample / well", "rows": "98 train wells + 10 labelled hidden-test wells; 1,292,908 samples", "used_by": ["Log Lens", "evidence log layer", "atlas"], "truth": "competition labels; hidden labels are evaluation-only", "limitations": ["hidden_test.csv must never train or tune", "depth samples in one well are correlated", "15 cm sampling creates heavy adjacent-sample leakage if split by row"]},
    {"id": "realpore", "name": "RealPore", "path": "official/realpore", "origin": "mail", "license": "Data are © GeoProvider https://geoprovider.no/ and licensed CC-BY 4.0", "source": "GeoProvider/organiser distribution", "kind": "primary-core", "modality": ["core plug", "porosity", "permeability", "saturation", "rock description"], "grain": "core plug with depth and NPDID", "rows": "372,930 plugs in 1,238 wells", "used_by": ["atlas profiles", "research-only log-to-core fit"], "truth": "compiled lab measurements, not standardized assays", "limitations": ["mixed units and permeability variants", "known invalid/outlier values", "sampled cores are non-random", "join by depth + well must carry tolerance"]},
    {"id": "diskosqa", "name": "DISKOS-QA", "path": "diskosqa", "origin": "earlier", "license": "NLOD 2.0", "source": "FORCE consortium DISKOS-QA", "kind": "benchmark", "modality": ["question", "answer", "passage", "entities", "gold chunks"], "grain": "question", "rows": "1,027 questions; 1,690 unique gold passages", "used_by": ["Diskos Detective", "retrieval scorecard"], "truth": "mainly generated/programmatic benchmark, not manually authoritative", "limitations": ["gold passages in a small haystack overstate retrieval", "model-family/judge leakage risk", "closed-book answers possible"]},
    {"id": "volve", "name": "Volve drilling reports", "path": "volve", "origin": "earlier", "license": "CC BY 4.0 (Hugging Face copy; original terms apply)", "source": "Volve public dataset/WITSML", "kind": "primary-operations", "modality": ["daily operation", "state", "time", "depth", "comments"], "grain": "activity/report/wellbore", "rows": "1,759 reports", "used_by": ["Lost Time Hunter"], "truth": "coded operation plus free-text report", "limitations": ["26-well field-specific sample", "codes and comments can disagree", "time ordering matters"]},
    {"id": "f3", "name": "F3 seismic", "path": "seismic/f3", "origin": "earlier", "license": "CC BY 4.0", "source": "F3 Netherlands benchmark", "kind": "labelled-seismic", "modality": ["amplitude", "facies labels"], "grain": "voxel/patch", "rows": "train + two held blocks", "used_by": ["Seismic Lookalike", "atlas seismic explorer"], "truth": "facies labels; Netherlands stand-in, not NCS truth", "limitations": ["domain/geographic shift", "not joined to our NCS wells"]},
    {"id": "adele", "name": "Adele seismic", "path": "official/adele", "origin": "mail", "license": "CC BY 4.0", "source": "Geoscience Australia", "kind": "unlabelled-seismic", "modality": ["amplitude", "headers"], "grain": "voxel/trace", "rows": "301 x 2,731 x 1,001", "used_by": ["atlas seismic explorer"], "truth": "measured seismic; no NCS labels or wells", "limitations": ["Australia domain", "demo/QC only for NCS modeling"]},
    {"id": "parihaka", "name": "Parihaka seismic", "path": "seismic/parihaka", "origin": "earlier", "license": "CC BY 4.0", "source": "public Parihaka benchmark", "kind": "labelled-seismic", "modality": ["amplitude", "facies labels"], "grain": "voxel", "rows": "New Zealand 3D with six labels", "used_by": [], "truth": "research labels, not NCS", "limitations": ["domain shift", "currently unused"]},
    {"id": "penobscot", "name": "Penobscot seismic", "path": "seismic/penobscot", "origin": "earlier", "license": "CC BY 4.0", "source": "public Penobscot dataset", "kind": "labelled-seismic", "modality": ["amplitude", "horizons"], "grain": "voxel/horizon", "rows": "601 x 1,501 x 481; seven horizons", "used_by": [], "truth": "horizon interpretation, not NCS", "limitations": ["domain shift", "currently unused"]},
    {"id": "faultseg3d", "name": "FaultSeg3D", "path": "seismic/faultseg3d", "origin": "earlier", "license": "CC BY-NC 4.0", "source": "FaultSeg3D benchmark", "kind": "synthetic-seismic", "modality": ["amplitude", "fault labels"], "grain": "voxel", "rows": "220 synthetic cubes", "used_by": [], "truth": "synthetic labels", "limitations": ["not commercial training data", "synthetic-to-real gap", "currently unused"]},
    {"id": "smeaheia", "name": "Smeaheia CO2 dataset", "path": "seismic/smeaheia", "origin": "earlier", "license": "Gassnova/Equinor CO2DataShare click-through; CC BY based terms, no reselling", "source": "CO2DataShare", "kind": "primary-ncs-seismic", "modality": ["3D seismic", "2D seismic", "horizons", "faults", "surfaces", "velocity", "well data", "simulation"], "grain": "survey/trace/horizon/well", "rows": "GN1101, TNE01 and supporting material", "used_by": ["seismic context", "future CCS/barrier model"], "truth": "NCS measurements and interpretations", "limitations": ["few scored well units", "time-depth relation incomplete", "licence click-through applies"]},
    {"id": "sleipner", "name": "Sleipner 4D seismic", "path": "seismic/sleipner", "origin": "earlier", "license": "Equinor CO2DataShare click-through terms", "source": "CO2DataShare", "kind": "primary-ncs-seismic-time-lapse", "modality": ["3D seismic vintages", "time-lapse"], "grain": "survey/trace", "rows": "ten vintages, 1994-2010", "used_by": ["seismic context", "future CCS/time-lapse model"], "truth": "measured NCS seismic; processing vintages matter", "limitations": ["few internal target labels", "processing differences confound time-lapse", "licence terms apply"]},
    {"id": "sleipner_benchmark_2019", "name": "Sleipner 2019 Benchmark Model", "path": "seismic/sleipner-benchmark-2019", "origin": "earlier", "license": "CO2DataShare terms; see archive licence and attribution", "source": "CO2DataShare Sleipner Benchmark Model 2019", "kind": "mixed-log-and-interpretation", "modality": ["LAS", "well picks", "grids", "velocity trends", "plume boundaries"], "grain": "well sample / interpreted horizon or cell", "rows": "two wells and associated benchmark products", "used_by": ["transfer research and seismic context"], "truth": "well curves and publisher interpretations, not a fully observed reservoir", "limitations": ["few wells", "derived products share controls; not independent validation"]},
    {"id": "ksat", "name": "KSAT SAR event data", "path": "official/ksat", "origin": "mail", "license": "organiser terms; not established in repo", "source": "hackathon organiser", "kind": "primary-sar", "modality": ["SAR"], "grain": "scene/pixel", "rows": "empty directory currently", "used_by": [], "truth": "not available on disk", "limitations": ["no files", "licence/task semantics unresolved"]},
    {"id": "atlas", "name": "Data Atlas derived profiles", "path": "atlas", "origin": "derived", "license": "inherits each source", "source": "app/sketches/atlas.py and related modules", "kind": "derived", "modality": ["profiles", "indexes", "charts", "extracted text"], "grain": "derived table/summary", "rows": "per-dataset profiles and extracted rows", "used_by": ["atlas", "subsurface-evidence"], "truth": "derived; provenance must point to build script/source", "limitations": ["stale until rebuilt", "not evidence source on its own"]},
    {"id": "subsurface_derived", "name": "Subsurface Evidence derived artifacts", "path": "subsurface-evidence", "origin": "derived", "license": "inherits source datasets/code", "source": "se.ingest, se.validate, se.seismic", "kind": "derived-model-artifacts", "modality": ["units", "log features", "OOF predictions", "seismic index", "targets"], "grain": "unit/prediction/artifact", "rows": "generated from current code", "used_by": ["subsurface-evidence"], "truth": "derived; must be rebuilt with code/data hashes", "limitations": ["must not be cited as source", "can become stale", "saved targets are mutable runtime state"]},
]


def _tree(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "bytes": 0, "files": 0}
    if path.is_file():
        return {"exists": True, "bytes": path.stat().st_size, "files": 1}
    size = files = 0
    for root, _, names in os.walk(path):
        files += len(names)
        for name in names:
            try:
                size += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return {"exists": True, "bytes": size, "files": files}


def _sha256(path: Path) -> str | None:
    if not path.is_file() or path.stat().st_size > 100 * 1024 * 1024:
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


@lru_cache(maxsize=1)
def catalog() -> dict:
    datasets = []
    for item in DATASETS:
        p = DATA / item["path"]
        datasets.append({**item, **_tree(p), "absolute_path": str(p)})
    return {"root": str(DATA), "bytes_total": sum(d["bytes"] for d in datasets if d["id"] != "sodir_csv" and d["id"] != "subsurface_derived"), "datasets": datasets}


@lru_cache(maxsize=8)
def model_lineage(target: str = "green_clay") -> dict:
    d = OUT if target == "green_clay" else OUT / "targets" / target
    artifacts = []
    for p in (d / "units.parquet", d / "results.json", d / "oof.parquet", d / "unit_diagnostics.json", OUT / "unit_diagnostics.json"):
        if p.exists() and p not in [Path(x["path"]) for x in artifacts]:
            artifacts.append({"path": str(p), "bytes": p.stat().st_size, "sha256": _sha256(p), "mtime": p.stat().st_mtime})
    scripts = [PROJECT / "backend/se/ingest/units.py", PROJECT / "backend/se/validate/cv.py", PROJECT.parent / "app/sketches/greenclay.py"]
    return {
        "target": target,
        "unit_policy": "formation-first, group fallback; no source row may count twice",
        "validation": {"split": "geographic blocked by 40 km LAEA groups", "calibration": "nested; held-out labels never fit outer-fold calibrator", "bootstrap": "whole wellbore"},
        "artifacts": artifacts,
        "code": [{"path": str(p), "sha256": _sha256(p)} for p in scripts if p.exists()],
        "rules": {"path": str(PROJECT / "backend/se/knowledge/rules/green_clay.yaml"), "sha256": _sha256(PROJECT / "backend/se/knowledge/rules/green_clay.yaml")},
        "warning": "Derived predictions are model estimates, not geological ground truth. Every score must link to source pages and manifest limitations.",
    }
