from dataclasses import replace

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from se.api import provenance
from se.config import DATA, OUT
from se.modeling.seismic_coverage import build as build_coverage
from se.modeling.seismic_coverage import sites_in_trace_hull
from se.modeling.smeaheia_velocity import build
from se.modeling.velocity import HorizonTie, WellTie, evaluate


def test_velocity_whole_site_split_uses_only_test_times_and_seabed():
    a = WellTie("A", 400, 300, (HorizonTie("upper", 600, 500), HorizonTie("lower", 800, 800)))
    b = WellTie("B", 600, 450, (HorizonTie("upper", 800, 650), HorizonTie("lower", 1000, 950)))
    out = evaluate([a, b])
    assert out["pooled_scores"]["layer_cake"]["rmse_m"] == 0
    fold = next(f for f in out["folds"] if f["held_out_site"] == "B")
    assert fold["training_sites"] == ["A"]
    assert fold["interval_velocities_mps"] == {"upper": 2000, "lower": 3000}
    changed = evaluate([a, replace(b, horizons=tuple(replace(h, depth_m=h.depth_m + 10) for h in b.horizons))])
    assert [r["prediction_m"] for r in changed["folds"][1]["rows"]] == [r["prediction_m"] for r in fold["rows"]]
    with pytest.raises(ValueError, match="time and depth must increase"):
        evaluate([a, replace(b, horizons=(b.horizons[0], replace(b.horizons[1], twt_ms=799)))])
    with pytest.raises(ValueError, match="horizon sequence"):
        evaluate([a, replace(b, horizons=(b.horizons[0], replace(b.horizons[1], horizon="unmatched")))])


def test_real_smeaheia_sources_use_factpages_not_derived_bathymetry():
    out = build(DATA)
    heldout = out["evaluation"]
    assert heldout["pooled_scores"]["ui_constant"]["rmse_m"] == pytest.approx(73.2182, abs=1e-4)
    assert heldout["pooled_scores"]["layer_cake"]["rmse_m"] == pytest.approx(15.8457, abs=1e-4)
    for c in out["controls"]:
        assert c["factpages"]["water_depth_m"] != c["seabed_depth_derived_diagnostic"]["positive_down_value"]
        assert all(p["distance_to_factpages_site_m"] < 10 for p in c["picks"])
    assert out["controls"][0]["wireline_diagnostics"]["las_two_way_minus_workbook_twt_ms"] == pytest.approx([58.36, 58.30, 58.05, 58.51], abs=0.01)
    assert not out["activate_overlay"] and heldout["prediction_interval"] is None


def test_velocity_api_absence_and_relation_coverage(tmp_path, monkeypatch):
    api = FastAPI()
    api.include_router(provenance.router)
    monkeypatch.setattr(provenance, "OUT", tmp_path)
    client = TestClient(api)
    assert client.get("/api/provenance/velocity").status_code == 404
    result = build(DATA)
    path = tmp_path / provenance.RELATIVE_OUT
    path.parent.mkdir()
    path.write_text(provenance.json.dumps(result))
    data = client.get("/api/provenance/velocity").json()
    assert data["evaluation"]["sites"] == 2 and not data["activate_overlay"]

    plan = client.get("/api/provenance/relations").json()
    catalog = client.get("/api/provenance/datasets").json()["datasets"]
    assert {s for r in plan["relations"] for s in r["inputs"]} == {d["id"] for d in catalog}
    assert next(r for r in plan["relations"] if r["id"] == "gn1101-time-depth")["state"] == "research_only"


def test_hull_screen_is_not_a_bounding_box():
    traces = np.array([[0, 0], [100, 0], [0, 100]])
    inside, distances = sites_in_trace_hull(traces, np.array([[3, 4], [85, 85], [100, 0]]))
    assert inside.tolist() == [True, False, True]
    assert distances.tolist() == pytest.approx([5, 0])


def test_local_coverage_counts_unique_wellheads_across_processing_variants(tmp_path, monkeypatch):
    if not (OUT / "seismic" / "gn1101" / "xy.npy").exists() or not (OUT / "units.parquet").exists():
        pytest.skip("local seismic index or report interval build missing")
    api = FastAPI()
    api.include_router(provenance.router)
    monkeypatch.setattr(provenance, "OUT", tmp_path)
    client = TestClient(api)
    assert client.get("/api/provenance/seismic-coverage").status_code == 404
    coverage = build_coverage(DATA, OUT)
    path = tmp_path / provenance.COVERAGE_OUT
    path.parent.mkdir()
    path.write_text(provenance.json.dumps(coverage))
    data = client.get("/api/provenance/seismic-coverage").json()
    gn = next(s for s in data["surveys"] if s["id"] == "gn1101")
    control = next(w for w in gn["wells"] if w["npdid"] == 5839)
    assert control["force_train_logs"] and "not established" in control["time_depth_tie"]
    assert data["distinct_wells_in_footprints"] < sum(s["well_count"] for s in data["surveys"])
