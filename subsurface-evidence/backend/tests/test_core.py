"""Core tests: layer maths, calibration, knowledge-base rules, CPU/GPU map agreement, API shape. Run: uv run pytest (needs the built data)."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from se.evidence.strat import Strat
from se.infer.combine import Platt
from se.jobs import map_job
from se.knowledge import kb


def units(n=40):
    r = np.random.default_rng(0)
    return pd.DataFrame({"unit": [f"w{i} | F" for i in range(n)], "wellbore": [f"w{i}" for i in range(n)], "name": "F", "level": "FORMATION",
                         "lat": 60 + r.random(n), "lon": 2 + r.random(n), "coverage": 10, "n_green": r.integers(0, 4, n), "label": 1})


def test_strat_shrinks_to_base_with_no_rows():
    u = units(); s = Strat(a=30.0).fit(u)
    assert 0 < s.p0 < 1 and s.table["F"][0] == pytest.approx((u.n_green.sum() + 30 * s.p0) / (u.coverage.sum() + 30))


def test_platt_slope_below_one_for_overconfident_input():
    r = np.random.default_rng(1); x = r.normal(size=4000) * 2; p = 1 / (1 + np.exp(-(0.4 * x - 2)))
    n = np.full(4000, 10); g = r.binomial(10, p)
    f = Platt().fit(x, g, n)
    assert 0.3 < f.params()["slope"] < 0.5


def test_map_far_cells_are_flagged():
    u = units(); s = Strat().fit(u)
    m = map_job.run(s, u, "F", res_deg=0.2, dev="cpu", pad_deg=3.0)
    assert np.nanmax(m["nearest_km"]) > m["reach_km"], "padding far from every unit must be beyond reach"


def test_every_rule_has_a_source_and_status():
    for r in kb.load()["rules"]:
        assert r["sources"] and r["status"] in ("sourced", "sourced_unverified", "inferred")


def test_rule_without_source_is_rejected(tmp_path, monkeypatch):
    p = tmp_path / "r.yaml"; p.write_text("rules:\n  - {id: X, statement: s, status: sourced, sources: [], check: {type: not_testable}}\n")
    monkeypatch.setattr(kb, "RULES", p)
    with pytest.raises(ValueError):
        kb.load()


def test_cpu_and_cuda_maps_agree():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("no cuda")
    u = units(); s = Strat().fit(u)
    a, b = map_job.run(s, u, "F", 0.05, dev="cpu"), map_job.run(s, u, "F", 0.05, dev="cuda")
    assert np.abs(np.array(a["logit"]) - np.array(b["logit"])).max() < 1e-3


def test_api_shape():
    from se.api.main import app
    with TestClient(app) as c:
        m = c.get("/api/meta").json()
        assert m["status"]["logs"] in ("helps", "no_evidence", "hurts") and "logs" not in m["layers_default_on"] or m["status"]["logs"] != "hurts"
        u = c.get("/api/units", params={"limit": 1}).json()[0]
        e = c.get("/api/unit", params={"id": u["unit"]}).json()["estimate"]
        assert 0 < e["rate"] < 1 and e["parts"][0]["layer"] == "base"
        assert len(c.get("/api/kb").json()) >= 7


def test_builder_filters():
    from se.targets.builder import apply
    d = pd.DataFrame({"a": ["OIL", "GAS", "DRY", None], "n": [0, 5, 1, 7]})
    assert apply(d, ["a|in|OIL,GAS"]).tolist() == [True, True, False, False]
    assert apply(d, ["a|has|ga", "n|gt|1"]).tolist() == [False, True, False, False]
    assert apply(d, ["a|notnull"]).tolist() == [True, True, True, False]
    with pytest.raises(ValueError):
        apply(d, ["nope|eq|x"])


def test_spec_id_is_stable_and_recipe_specific():
    from se.targets.builder import spec_id
    a = {"mode": "well", "table": "t", "population": [], "success": ["x|eq|1"], "group": "g", "title": "one"}
    assert spec_id(a) == spec_id({**a, "title": "other title"})  # same recipe, same id: title is not part of it
    assert spec_id(a) != spec_id({**a, "success": ["x|eq|2"]})


def test_too_little_data_is_refused():
    from se.targets import store
    with pytest.raises(ValueError, match="too little data"):
        store.evaluate({"title": "none", "mode": "well", "table": "wellbore_exploration", "population": [], "success": ["wlbContent|eq|NOPE"], "group": "wlbMainArea"})


def test_targets_api_and_target_param():
    from se.api.main import app
    with TestClient(app) as c:
        t = c.get("/api/targets").json()
        assert t["builtin"]["id"] == "green_clay" and len(t["presets"]) >= 3
        o = c.get("/api/targets/options").json()
        assert {x["table"] for x in o["well"]} == {"wellbore_exploration", "wellbore_development"}
        for s in t["saved"][:1]:  # a saved target answers the same endpoints with its own words
            m = c.get("/api/meta", params={"target": s["id"]}).json()
            assert m["words"]["hit"] and m["title"] == s["title"]
        assert c.post("/api/targets/build", json={"mode": "well", "table": "nope", "success": ["a|eq|1"]}).status_code == 400
