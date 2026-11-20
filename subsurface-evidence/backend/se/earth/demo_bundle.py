"""Rebuild missing display products from a verified parent, never from mutable live data."""

import argparse
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import numpy as np
import pandas as pd

from se.config import EARTH
from se.earth import atomic, export, factors, snapshot, volumes
from se.modeling.artifacts import sha256


def complete(build: str, *, region: Path = EARTH) -> dict:
    if not snapshot.BUILD_RE.fullmatch(build):
        raise ValueError("use an explicit frozen parent build ID")
    source = snapshot.resolve(region, build)
    receipt = json.loads((source / snapshot.RECEIPT).read_text())
    with TemporaryDirectory(prefix="earth-demo-") as tmp:
        work = Path(tmp)
        for key, digest in receipt["files_sha256"].items():
            path = Path(key)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"invalid parent receipt file: {key}")
            out = work / path
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / path, out)
            if sha256(out) != digest:
                raise ValueError(f"parent hash mismatch: {key}")
        cells = pd.read_parquet(work / snapshot.CELL_INPUT)
        phi, sigma = volumes.write_porosity(cells, root=work)
        if not (np.isfinite(phi).all() and np.isfinite(sigma) and sigma >= 0):
            raise ValueError("nonfinite modelled porosity or invalid sigma")
        legacy = factors.legacy(cells, root=work)
        path = work / "targets/legacy_wells.npz"
        atomic.savez(path, value=legacy.astype(np.float32), sd=np.zeros(len(cells), np.float32))
        factors.record_legacy(path, work)
        export.build(root=work)
        with ZipFile(work / "export" / f"{region.name}_all.zip") as archive:
            grid = json.loads(archive.read("export.json"))["grid"]
            if archive.testzip() is not None or "PORO" not in grid["properties"]:
                raise ValueError("export is corrupt or missing porosity")
        return snapshot.publish(region, source=work, parent_build=build, map_source=work / "map")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build")
    receipt = complete(parser.parse_args().build)
    print(json.dumps({k: v for k, v in receipt.items() if k != "files_sha256"}, indent=2))
