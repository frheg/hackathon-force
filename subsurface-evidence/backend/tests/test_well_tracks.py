import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from se.api import tracks
from se.config import DATA, OUT
from se.modeling import well_tracks as wt


def test_same_borehole_depth_and_area_guards():
    w = {"npdid": 1, "name": "A", "datum": "ED50", "lat": 60.576425, "lon": 3.443367}
    centre = w.copy()
    assert wt.exact({1: w}, 1, "A") is w
    assert wt.exact({1: w}, 1, "A T2") is None
    assert wt.exact({1: w}, 2, "A") is None
    assert set(wt.groups(w, set(), centre)) == {"northern-lights", "pilot"}
    for bad in ({"lat": None}, {"datum": "61ED50"}):
        assert wt.groups(w | bad, {1}, centre) == []
    assert wt.valid_depth(90, 100, 100)
    assert wt.valid_depth(90, 90, 100, point=True)
    for a, b in [
        (100, 101),
        (90, 90),
        (95, 92),
        (0, 100),
        (None, 95),
        (90, float("nan")),
    ]:
        assert not wt.valid_depth(a, b, 100)


def test_pinned_search_and_well_pack_fail_closed(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(tracks.router)
    client = TestClient(app)
    monkeypatch.setattr(tracks, "OUT", tmp_path)
    folder = tmp_path / wt.STORE
    assert client.get("/api/tracks").status_code == 404
    w = {"npdid": 1, "name": "A", "status": "P&A", "scopes": ["pilot"]}
    pack = wt.put(folder, {"1": w})
    manifest = {
        "schema": 1,
        "index": [list(w.values()), [2, "A T2", "SUSPENDED", []]],
        "columns": list(w),
        "pack_size": 128,
        "packs": {"0": pack},
        "scopes": {"all": "All", "pilot": "Pilot"},
        "rules": {"reports": {}},
        "focus_version": wt.SCREEN,
        "inputs": {},
    }
    pin = wt.put(folder, manifest)
    params = {"version": pin}
    assert client.get(
        "/api/tracks/search", params=params | {"pa": True, "scope": "pilot"}
    ).json()["rows"] == [list(w.values())]
    assert (
        client.get("/api/tracks/search", params=params | {"q": "2"}).json()["total"]
        == 1
    )
    assert (
        client.get(
            "/api/tracks/search", params=params | {"scope": "missing"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/tracks/search", params=params | {"limit": 1, "offset": 1}
        ).json()["rows"][0][1]
        == "A T2"
    )
    assert client.get("/api/tracks/wells/1", params=params).json()["well"] == w
    assert (
        client.get("/api/tracks/wells/2", params=params).status_code == 503
    )  # indexed, missing from pack
    assert (
        client.get("/api/tracks/wells/3", params=params).status_code == 404
    )  # not indexed
    assert client.get("/api/tracks", params={"version": pack}).status_code == 422
    assert client.get("/api/tracks", params={"version": "latest"}).status_code == 422
    (folder / f"{pack}.json").write_text("{}")
    assert client.get("/api/tracks/wells/1", params=params).status_code == 503
    (folder / f"{pin}.json").write_text("{}")
    assert client.get("/api/tracks", params=params).status_code == 503


@pytest.mark.skipif(
    not (DATA / wt.CATALOG).is_file()
    or not (OUT / "screen/smeaheia" / f"{wt.SCREEN}.json").is_file(),
    reason="local report collection and focused receipt required",
)
def test_source_replay_preserves_well_evidence_and_scopes(tmp_path):
    pin = wt.build(DATA, tmp_path, focus_dir=OUT / "screen/smeaheia")
    assert pin == tracks.RELEASE
    folder = tmp_path / wt.STORE
    receipt = wt.read(folder, pin)
    wells = {
        w["npdid"]: w
        for h in receipt["packs"].values()
        for w in wt.read(folder, h).values()
    }
    assert sorted(wells) == [r[0] for r in receipt["index"]]
    assert receipt["coverage"]["all"]["wells"] == len(wells) == 8496
    assert receipt["coverage"]["all"]["positioned"] == sum(
        any(e["top"] is not None for e in w["events"]) for w in wells.values()
    )
    assert receipt["coverage"]["all"]["placements"] == 6
    assert {i for i, w in wells.items() if w["scenario"] is not None} == {
        w["npdid"] for w in wt.read(OUT / "screen/smeaheia", wt.SCREEN)["wells"]
    }
    assert "smeaheia" not in wells[20]["scopes"]
    assert (
        not wells[10166]["events"]
        and wells[10166]["scenario"]["state"] == "insufficient evidence"
    )
    overlaps = [(o["formation"], o["m"]) for o in wells[5839]["overlaps"]]
    assert sorted(overlaps) == [
        ("DRAUPNE FM", 23),
        ("DRAUPNE FM", 33),
        ("SOGNEFJORD FM", 110),
    ]
    tests = [e for e in wells[45]["events"] if e["kind"] == "equipment test"]
    assert len(tests) == 2 and all(
        e["top"] is None and e["base"] is None and e["page"] == 123 for e in tests
    )
    assert {"negative", "OK"} == {
        word for e in tests for word in ("negative", "OK") if word in e["label"]
    }
    (dst,) = [e for e in wells[8951]["events"] if e["kind"] == "reservoir test"]
    assert dst["top"] == 2698 and "2697.5" in dst["evidence"]
    assert not wells[8951]["overlaps"] and wells[8951]["scenario"] is None
