import io
import json
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from se.api import earth
from se.earth import atomic, demo_bundle, export, snapshot
from se.modeling.artifacts import sha256


def scratch(root, unit, probability):
    targets = root / "targets"
    targets.mkdir(parents=True, exist_ok=True)
    x, y = np.array([4000.0, 4002.0]), np.array([3400.0])
    inside = np.ones((1, 2), dtype=bool)
    np.savez(root / "surfaces.npz", x=x, y=y, inside=inside, names=["SEABED"], level=["SEABED"])
    np.savez(root / "grid.npz", x=x, y=y, inside=inside)
    cells = pd.DataFrame({"i": [0, 1], "j": [0, 0], "label": [0, 0], "x": x, "y": y[0], "unit": unit, "group": "G",
                          "top": 1000.0, "base": 1100.0, "thick": 100.0, "zb": 800.0})
    cells.to_parquet(targets / "cells.parquet")
    (root / "column.json").write_text(json.dumps({"groups": []}))
    (targets / "report.json").write_text(json.dumps({"hydrocarbons": {"published": "model"}}))
    for product, dependency in (("grid.npz", "surfaces.npz"), ("targets/cells.parquet", "grid.npz")):
        (root / f"{product}.manifest.json").write_text(json.dumps({
            "inputs": [{"path": dependency, "sha256": sha256(root / dependency)}],
        }))
    p = np.array([probability, 0.1])
    np.savez(targets / "hydrocarbons.npz", i=cells.i, j=cells.j, label=cells.label, p=p, p05=p, p95=p, support=[0.6, 0])


def test_snapshot_api_retains_old_cell_after_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(earth, "OUT", tmp_path)
    pilot = tmp_path / "earth" / "pilot"
    scratch(pilot, "old", 0.7)
    a = snapshot.publish(pilot, activate=True)["build"]

    app = FastAPI()
    app.include_router(earth.router)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/api/earth/meta").json()["build"] == a
    drawn = client.get("/api/earth/target", params={"t": "hydrocarbons", "build": a}).json()
    assert drawn["unit"] == ["old"] and drawn["p"] == [0.7]
    scratch(pilot, "new", 0.8)
    b = snapshot.publish(pilot, activate=True)["build"]
    assert client.get("/api/earth/meta").json()["build"] == b
    assert client.get("/api/earth/target", params={"t": "hydrocarbons"}).json()["unit"] == ["new"]
    params = {"t": "hydrocarbons", "cell": drawn["cell"][0]}
    assert client.get("/api/earth/cell", params=params).status_code == 409
    assert client.get("/api/earth/cell", params={**params, "build": "0" * 12}).status_code == 404
    old = client.get("/api/earth/cell", params={**params, "build": a}).json()
    assert (old["build"], old["unit"], old["p"]) == (a, "old", 0.7)
    assert client.get("/api/earth/meta", params={"build": "legacy"}).json()["build"] is None


def test_bad_row_order_does_not_replace_active_build(tmp_path):
    pilot = tmp_path / "pilot"
    scratch(pilot, "A", 0.7)
    (pilot / "export").mkdir()
    (pilot / "export/pilot_all.zip").write_bytes(b"unverified")
    original = snapshot.publish(pilot, activate=True)
    assert original["omitted_without_input_receipt"] == ["export/pilot_all.zip"]
    path = pilot / "targets/hydrocarbons.npz"
    with np.load(path) as arrays:
        reordered = {k: arrays[k][::-1] for k in arrays.files}
    np.savez(path, **reordered)
    with pytest.raises(ValueError, match="cell order"):
        snapshot.publish(pilot, activate=True)
    assert snapshot.resolve(pilot).name == original["build"]
    assert (pilot / "export/pilot_all.zip").read_bytes() == b"unverified"


def test_staging_recovers_from_failed_rename(tmp_path, monkeypatch):
    target = tmp_path / "targets"
    target.mkdir()
    (target / "original.txt").write_text("previous")
    replace = atomic.os.replace

    def fail(source, dest):
        if source.name == "targets.staging":
            raise OSError("injected rename failure")
        replace(source, dest)

    monkeypatch.setattr(atomic.os, "replace", fail)
    with pytest.raises(OSError, match="injected"), atomic.staged(target) as stage:
        (stage / "replacement.txt").write_text("next")
    assert (target / "original.txt").read_text() == "previous"


def test_demo_bundle_rejects_modified_parent(tmp_path):
    root = tmp_path / "pilot"
    scratch(root, "A", 0.7)
    parent = snapshot.publish(root, activate=True)["build"]
    (snapshot.resolve(root, parent) / "column.json").write_text("{}")
    with pytest.raises(ValueError, match="parent hash mismatch: column.json"):
        demo_bundle.complete(parent, region=root)
    assert snapshot.resolve(root).name == parent


def test_export_surfaces_respect_offshore_mask(tmp_path):
    x, y = np.array([4000., 4002.]), np.array([3400., 3402.])
    np.savez(tmp_path / "surfaces.npz", x=x, y=y, inside=np.ones((2, 2), bool), names=["SEABED"],
             mean=np.full((1, 2, 2), 300.), sd=np.full((1, 2, 2), 10.))
    np.savez(tmp_path / "grid.npz", inside=[[True, False], [True, True]])
    data = export.build("surfaces", root=tmp_path)
    with ZipFile(io.BytesIO(data)) as archive:
        depth = archive.read("surfaces/SEABED_depth.irap").decode().splitlines()[4:]
        assert [float(x) for x in " ".join(depth).split()] == [300, export.UNDEF_IRAP, 300, 300]
    archive_path = next((tmp_path / "export").glob("*.zip"))
    receipt = json.loads(archive_path.with_name(archive_path.name + ".manifest.json").read_text())
    assert {item["sha256"] for item in receipt["inputs"]} == {sha256(tmp_path / n) for n in ("grid.npz", "surfaces.npz")}


def test_export_distinguishes_missing_unit_rows_from_modelled_zero(tmp_path):
    np.savez(tmp_path / "grid.npz", x=[4000., 4002.], y=[3400., 3402.], zone=[0], zones=["G"],
             zb=np.stack([np.full((2, 2), 300.), np.full((2, 2), 301.)]),
             inside=[[True, True], [True, False]])
    targets = tmp_path / "targets"
    targets.mkdir()
    pd.DataFrame({"group": ["G", "G"], "i": [0, 0], "j": [0, 1], "thick": [1., 1.]}).to_parquet(targets / "cells.parquet")
    np.savez(targets / "porosity.npz", value=[25., 0.])
    grid, meta = export.grdecl(root=tmp_path)
    assert grid.split("ACTNUM\n")[1].split("/")[0].split() == ["1", "0", "1", "0"]
    assert grid.split("PORO\n")[1].split("/")[0].split() == ["0.2500", "0.0000", "0.0000", "0.0000"]
    assert meta["geometry_cells_without_unit_rows"] == 1
