import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from se.api import screen
from se.config import DATA, OUT
from se.modeling import screen_validation as validation
from se.modeling import smeaheia_screen as review


def test_missing_brackets_do_not_grow_paths_or_transfer_sidetracks():
    path = pd.DataFrame({"md": [100, 101, 110, 111], "x": [1]*4, "y": [2]*4, "tvdss": [75, 76, 85, 86]})
    assert validation.bracket(path, 100.5)["tvdss"] == 75.5
    assert all(validation.bracket(path, m) is None for m in (99, 102, 115))
    assert [len(s) for s in review.path_segments(path)] == [2, 2]
    rules = [{"name": "SOGNEFJORD FM", "unit_id": 151}]
    r = SimpleNamespace(wellbore="A", npdid=1, td=120)
    rows = pd.DataFrame([
        ("A", 1, 151, "FORMATION", 106, 109), ("A T2", 1, 151, "FORMATION", 100, 110),
        ("A", 2, 151, "FORMATION", 100, 110), ("A", 1, 151, "GROUP", 100, 110),
        ("A", 1, 4, "FORMATION", 100, 110), ("A", 1, 151, "FORMATION", 110, 130),
    ], columns=["wellbore", "npdid", "unit_id", "level", "top_md", "base_md"]).assign(unit="SOGNEFJORD FM")
    m = review.markers(rows, r, rules, path)[0]
    assert m["picks"] == [{"top_md_m": 106., "base_md_m": 109., "top_position": None}]
    assert m["excluded_rows"] == 1
    assert review.markers(rows.iloc[1:], r, rules, path)[0]["state"] == "unknown"


def test_fixed_depth_comparison_excludes_neighbors_and_families():
    rows = [{"npdid": i, "head_x": x, "head_y": 0, "family": f, "tvdss": z} for i, x, f, z in
            [(1, 39, "A", 400), (2, 41, "B", 800), (3, 83, "A", 900), (4, 125, "D", 1200), (5, 130, "E", 1400)]]
    result = validation.evaluate(rows)
    fold = next(f for f in result["folds"] if 1 in f["test_ids"])
    assert fold["train_ids"] == [4, 5]
    pred = next(r for r in result["rows"] if r["npdid"] == 1)
    assert (pred["median_m"], pred["nearest_m"]) == (1300, 1200)
    rows[0]["tvdss"] = 4000
    changed = next(r for r in validation.evaluate(rows)["rows"] if r["npdid"] == 1)
    assert (changed["median_m"], changed["nearest_m"]) == (1300, 1200)
    with pytest.raises(ValueError, match="one identified top"):
        validation.evaluate(rows + rows[:1])


def test_receipt_api_fails_closed(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(screen.router)
    client = TestClient(app)
    monkeypatch.setattr(screen, "OUT", tmp_path)
    base = "/api/screen/smeaheia"
    assert client.get(base).status_code == 404
    assert client.get(base, params={"version": "legacy"}).status_code == 422
    d = {"schema": 1, "earth_build": review.BUILD, "region": "pilot", "wells": []}
    version = review.publish(d, tmp_path)
    assert review.publish(d, tmp_path) == version
    assert client.get(base, params={"version": version}).json() == {"version": version, **d}
    (tmp_path / review.STORE / (version + ".json")).write_text("{}")
    assert client.get(base, params={"version": version}).status_code == 503
    with pytest.raises(ValueError, match="digest mismatch"):
        review.publish(d, tmp_path)


@pytest.mark.skipif(not (OUT / review.SUPPORT).is_file() or not (DATA / "ncs.duckdb").is_file()
                    or not (OUT / "earth/pilot/.snapshots" / review.BUILD).is_dir(), reason="licensed local release unavailable")
def test_source_replay_matches_shipped_release(tmp_path):
    d = review.build()
    assert review.publish(d, tmp_path) == screen.RELEASE
    local = [w for w in d["wells"] if any(s["in_hull"] for s in w["surveys"])]
    assert len(local) == 6 and all(w["registry_status"] == "P&A" for w in local)
    assert sum(all(m["picks"] for m in w["markers"]) for w in local) == 5
    wells = {w["npdid"]: w for w in d["wells"]}
    assert wells[10166]["markers"][0]["state"] == "unknown" and not wells[10166]["path_segments"]
    assert wells[2918]["markers"][0]["picks"][0]["top_position"] is None and not wells[2918]["report_claim"]
    assert wells[5839]["report_claim"]["pdf_page"] == 57 and not wells[20]["surveys"][0]["in_hull"]
    v = d["validation"]
    assert len(v["rows"]) == v["scored"] == 20
    assert not v["published"] and v["median_mae_m"] < v["nearest_mae_m"]
    assert d["schema"] == 2 and all(w["barrier_integrity"] == "unknown" for w in d["wells"])
    assert sum(w["interval_screen"]["strict"]["state"] == "insufficient evidence" for w in local) == 5
    case = wells[447]["interval_screen"]
    assert case["strict"]["longest_joint_m"] == 13 and case["strict"]["state"] == "not seen on supported metres"
    assert case["zero_overbalance"]["longest_joint_m"] == 0 and case["group_screen"]["in_window_m"] == 41
    assert wells[20]["interval_screen"]["strict"]["longest_bounds_md_m"] == [1039, 1109]
    assert wells[5839]["interval_screen"]["lot_shoes_above"][0]["md"] == 835
    assert wells[5839]["interval_screen"]["strict"]["longest_joint_m"] is None
    assert np.isclose(v["gain_m"], v["median_mae_m"] - v["nearest_mae_m"])
    assert json.dumps(d, allow_nan=False)
