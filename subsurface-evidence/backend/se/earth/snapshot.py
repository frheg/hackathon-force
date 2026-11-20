"""Publish verified regional artifacts without replacing the live directory."""

import argparse
import json
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import numpy as np
import pandas as pd

from se.earth import atomic
from se.modeling.artifacts import sha256

BUILD_ID = r"[a-f0-9]{12}"
BUILD_RE = re.compile(BUILD_ID)
STORE = ".snapshots"
RECEIPT = "snapshot.json"
SCHEMA = 2
LEGACY = "legacy"
CELL_INPUT = "targets/cells.parquet"
DERIVED = ("porosity", "legacy_wells", "gamma_ray", "co2_capacity")
MAP_FILES = ("faults_and_boundaries.geojson", "structural_elements.geojson")


def resolve(region: Path, build: str | None = None) -> Path:
    if build == LEGACY:  # an explicitly legacy scene must not follow a newly active pointer
        return region
    if build is None:
        pointer = region / STORE / "active"
        try:
            build = pointer.read_text().strip()
        except FileNotFoundError:
            return region
    if not BUILD_RE.fullmatch(build):
        raise ValueError("invalid earth snapshot ID")
    path = region / STORE / build
    try:
        receipt = json.loads((path / RECEIPT).read_text())
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"earth snapshot {build} is missing") from exc
    if receipt.get("schema") != SCHEMA or receipt.get("build") != build or receipt.get("region") != region.name:
        raise ValueError(f"earth snapshot {build} has an invalid or obsolete receipt")
    return path


def _check_input(root: Path, hashes: dict, output: str, dependency: str) -> None:
    receipt = json.loads((root / (output + ".manifest.json")).read_text())
    matches = [item for item in receipt["inputs"] if Path(item["path"]).name == Path(dependency).name]
    if len(matches) != 1 or matches[0]["sha256"] != hashes.get(dependency):
        raise ValueError(f"{output}: receipt does not match copied {dependency}")


def validate(root: Path, hashes: dict) -> int:
    prefix = "targets/"
    for product, dependency in (("grid.npz", "surfaces.npz"), (prefix + "cells.parquet", "grid.npz"),
                                ("factors.npz", "grid.npz"), *((f"{prefix}{n}.npz", CELL_INPUT) for n in DERIVED),
                                (prefix + "porosity.npz", "poroperm_wells.parquet"), (prefix + "porosity.npz", "poroperm_report.json"),
                                (prefix + "legacy_wells.npz", "wells.parquet")):
        if product in hashes or product in {"grid.npz", prefix + "cells.parquet"}:
            _check_input(root, hashes, product, dependency)
    with np.load(root / "grid.npz") as grid, np.load(root / "surfaces.npz") as surfaces:
        for axis in ("x", "y"):
            if not np.array_equal(grid[axis], surfaces[axis]):
                raise ValueError(f"surface/grid mismatch: {axis}")
        cells = pd.read_parquet(root / prefix / "cells.parquet", columns=["i", "j", "label", "x", "y"])
        x, y = grid["x"], grid["y"]
        i, j = cells.i.to_numpy(), cells.j.to_numpy()
        if (cells.empty or not cells.i.between(0, len(x) - 1).all() or not cells.j.between(0, len(y) - 1).all()
                or not grid["inside"][j, i].all() or not np.array_equal(x[i], cells.x) or not np.array_equal(y[j], cells.y)
                or cells.duplicated(["i", "j", "label"]).any()):
            raise ValueError("cells do not uniquely match the regional lattice")
    report = json.loads((root / prefix / "report.json").read_text())
    required = {key for key, row in report.items() if not key.startswith("_") and isinstance(row, dict)}
    if not required or not all((root / prefix / f"{key}.npz").is_file() for key in required):
        raise ValueError("reported target arrays are missing")
    for path in (root / prefix).glob("*.npz"):
        with np.load(path) as a:
            if "p" in a:
                if any(not np.array_equal(a[field], cells[field]) for field in ("i", "j", "label")):
                    raise ValueError(f"{path.name}: cell order or identity mismatch")
                if any(a[field].shape != (len(cells),) for field in ("p", "p05", "p95", "support")):
                    raise ValueError(f"{path.name}: invalid probability array shape")
            elif any(a[field].shape != (len(cells),) for field in ("value", "sd")):
                raise ValueError(f"{path.name}: invalid property array shape")
        if path.stem in ("porosity", "legacy_wells"):
            key = path.relative_to(root).as_posix()
            receipt = json.loads((root / (key + ".manifest.json")).read_text())
            if receipt.get("output_sha256") != hashes[key]:
                raise ValueError(f"{key}: receipt does not match the property")
    if "seismic_surfaces.npz" in hashes:
        _check_input(root, hashes, "seismic_surfaces.npz", "tops.parquet")
        _check_input(root, hashes, "seismic_surfaces.npz", "wells.parquet")
        with np.load(root / "seismic_surfaces.npz") as tied:
            shape = (len(tied["names"]), len(y), len(x))
            if any(tied[k].shape != shape for k in ("mean", "sd", "weight")):
                raise ValueError("tied seismic horizon geometry differs from the lattice")
    for path in (root / "export").glob("*.zip"):
        export = path.relative_to(root).as_posix()
        from se.earth.export import inputs

        receipt = json.loads((root / (export + ".manifest.json")).read_text())
        kind = receipt.get("params", {}).get("kind")
        if kind not in {"all", "grid", "surfaces"} or not path.stem.endswith("_" + kind):
            raise ValueError(f"{export}: invalid export kind")
        for dependency in inputs(root, kind):
            _check_input(root, hashes, export, dependency.relative_to(root).as_posix())
        if receipt.get("output_sha256") != hashes[export]:
            raise ValueError(f"{export}: receipt does not match the archive")
    return len(cells)


def publish(region: Path, *, source: Path | None = None, activate: bool = False, map_source: Path | None = None,
            parent_build: str | None = None) -> dict:
    """Freeze a completed, idle build. Never consume a source while it is being rebuilt."""
    source = region if source is None else source
    store = region / STORE
    store.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="draft-", dir=store) as tmp:
        draft = Path(tmp)
        paths = {p.relative_to(source): p for p in source.iterdir() if p.is_file() and p.name != RECEIPT}
        for folder in ("targets", "export"):
            paths.update({p.relative_to(source): p for p in (source / folder).glob("*") if p.is_file()})
        if map_source is not None:
            paths.update({Path("map") / f: map_source / f for f in MAP_FILES})
        optional = {Path(f"targets/{name}.npz") for name in DERIVED} | {k for k in paths if k.parts[0] == "export" and k.suffix == ".zip"}
        omitted = sorted(k for k in paths.keys() & optional if Path(f"{k}.manifest.json") not in paths)
        for k in omitted:
            del paths[k]
        hashes = {}
        for key, path in sorted(paths.items()):
            target = draft / key
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            hashes[key.as_posix()] = sha256(target)
        count = validate(draft, hashes)
        if any(sha256(path) != hashes[key.as_posix()] for key, path in paths.items()):
            raise ValueError("source changed while copying; stop the builder before publishing")
        build = uuid4().hex[:12]
        receipt = {"schema": SCHEMA, "build": build, "region": region.name, "cells": count, "parent_build": parent_build,
                   "omitted_without_input_receipt": [k.as_posix() for k in omitted],
                   "files_sha256": hashes, "scope": "Frozen files and consistency checks, not scientific validation."}
        atomic.write_json(draft / RECEIPT, receipt)
        draft.rename(store / build)
    if activate:
        atomic.write_text(store / "active", build + "\n")
    return receipt


if __name__ == "__main__":
    from se.config import DATA, EARTH

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="copy from a completed, idle regional build directory")
    parser.add_argument("--activate", action="store_true", help="switch the active snapshot after verification")
    args = parser.parse_args()
    result = publish(EARTH, source=args.source, activate=args.activate, map_source=DATA / "sodir" / "factmaps")
    print(json.dumps({k: v for k, v in result.items() if k != "files_sha256"}, indent=2))
