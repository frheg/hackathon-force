"""Tests that need the data (uv run python fetch_data.py) but no model: the model is replaced by a stub.

    uv run pytest -q
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

import app as studio
import common
from sketches import copilot, detective, doctor, reports, seismic, spud, tieback, wells

client = TestClient(studio.api)


# -- the pieces --


def test_norm_spellings():
    assert common.norm("NO 15/9-F-12") == "15/9-F-12"
    assert common.norm("15/9-F- 12") == "15/9-F-12"
    assert common.norm(" 9/2-1 ") == "9/2-1"


def test_km_is_sane():
    assert common.km(60, 3, 60, 3) == 0
    assert 110 < common.km(60, 3, 61, 3) < 112


def test_plain_trims_and_cleans():
    assert common.plain("LUNDE FM   ") == "LUNDE FM"
    assert common.plain(float("nan")) is None


def test_entities_find_wells_and_formations():
    e = reports.entities("What did the cores in 9/2-1 show about the Sandnes Formation?")
    assert "9/2-1" in e["wellbores"]
    assert "SANDNES FM" in e["formations"]


def test_sql_guard():
    assert copilot.extract_sql("```sql\nselect 1\n```") == "select 1"
    for bad in ("drop table field", "select 1; drop table field", "delete from field"):
        with pytest.raises(ValueError):
            copilot.extract_sql(bad)


def test_sql_cannot_read_files():
    with pytest.raises(Exception):
        copilot.run("select * from read_csv('/etc/passwd')")


def test_facts_hide_zone():
    text = wells.facts_text(wells.card("34/10-1"))
    assert "zone=" not in text and "npdid=" not in text
    assert "[F:tops]" in text


def test_margin_needs_tests_and_stays_in_range():
    env = [{"md": 500 + 100 * i, "max": 1.2 + 0.02 * i, "min": 1.1, "median": 1.15, "n": 3} for i in range(20)]
    assert spud.margin(env, [{"md": 1000, "lot": 1.5}]) is None
    lots = [{"md": 800, "lot": 1.45}, {"md": 1500, "lot": 1.6}, {"md": 2200, "lot": 1.75}]
    m = spud.margin(env, lots)
    assert m and all(800 - 125 <= r["md"] <= 2200 + 125 for r in m["rows"])
    assert [k[1] for k in m["fit"]["knots"]] == sorted(k[1] for k in m["fit"]["knots"])


def test_odds_are_probabilities():
    d = tieback.discoveries()[0]
    h = next(iter(tieback.hosts().values()))
    o = tieback.odds(d, h)
    if o:
        assert 0 <= o["p_fit"] <= 1 and 0 <= o["share"] <= 1 and o["share_p10"] <= o["share_p90"]


def test_seismic_features_shape():
    import numpy as np

    f = seismic.features(np.random.default_rng(0).normal(size=(120, 80)).astype("float32"))
    assert f.ndim == 3 and f.shape[-1] == 32


def test_unit_spelling():
    assert doctor.unit("Åsgard Fm.") == doctor.unit("AASGARD FM")


def test_sentences_keep_citations():
    assert detective.sentences("A is 3 m [S1]. B is 4 m [F:tops].") == ["A is 3 m [S1].", "B is 4 m [F:tops]."]


# -- the API without a model --

PAGES = ["/", "/status/", "/copilot/", "/logs/", "/decline/", "/detective/", "/tieback/", "/spud/", "/barrier/",
         "/losttime/", "/doctor/", "/seismic/", "/style.css", "/shell.js"]
APIS = ["/api/apps", "/logs/api/wells", "/decline/api/fields", "/detective/api/wellbores", "/detective/api/scorecard",
        "/tieback/api/board", "/spud/api/examples", "/barrier/api/sites", "/losttime/api/overview", "/doctor/api/audit",
        "/seismic/api/info", "/seismic/api/section/test1/10"]


@pytest.mark.parametrize("path", PAGES + APIS)
def test_get(path):
    assert client.get(path).status_code == 200


def test_ten_apps():
    assert len(client.get("/api/apps").json()["apps"]) == 10


def test_screen_and_similar():
    r = client.post("/barrier/api/screen", json={"site": "smeaheia"}).json()
    assert r["wells"] and {"status_age", "barrier_depth", "proximity"} <= set(r["wells"][0]["schemes"])
    for mode in ("texture", "learned"):
        s = client.post("/seismic/api/similar", json={"section": 50, "trace": 300, "sample": 120, "mode": mode}).json()
        assert len(s["matches"]) == 12


@pytest.mark.parametrize("path,body", [
    ("/copilot/api/ask", {"q": ""}),
    ("/detective/api/ask", {"q": "why", "mode": "telepathy"}),
    ("/spud/api/brief", {"wellbore": "35/4-3", "radius_km": 500}),
    ("/barrier/api/screen", {"site": "smeaheia", "radius_km": 0}),
    ("/seismic/api/similar", {"cube": "nowhere", "section": 1, "trace": 1, "sample": 1}),
    ("/losttime/api/lessons", {"q": "x" * 5000}),
])
def test_bad_input_is_rejected(path, body):
    assert client.post(path, json=body).status_code == 422


def test_unknown_wellbore_is_404():
    assert client.get("/detective/api/dossier/99/99-99").status_code == 404
    assert client.post("/spud/api/brief", json={"wellbore": "99/99-99"}).status_code == 404


# -- the model-driven endpoints, with the model stubbed --


@pytest.fixture
def stub(monkeypatch):
    async def fake_chat(messages, **kw):
        return "Stub answer [S1]."

    async def fake_json(messages, schema, **kw):
        props = schema.get("properties", {})
        return {k: ([] if v.get("type") == "array" else "none") for k, v in props.items()}

    for m in (tieback, spud, detective, doctor, seismic):
        if hasattr(m, "chat"):
            monkeypatch.setattr(m, "chat", fake_chat)
        if hasattr(m, "chat_json"):
            monkeypatch.setattr(m, "chat_json", fake_json)


def test_memo_with_stub(stub):
    d = tieback.matches()[0]
    r = client.post("/tieback/api/memo", json={"discovery": d["name"], "host": d["best"]["host"]})
    assert r.status_code == 200 and r.json()["text"].startswith("Stub")


def test_dossier_with_stub(stub):
    r = client.get("/detective/api/dossier/9/2-1")
    assert r.status_code == 200 and r.json()["card"]["header"]["name"] == "9/2-1"


def test_verify_with_stub(stub):
    r = client.post("/detective/api/verify", json={"answer": "A is 3 m [S1]. B is 4 m.", "sources": [{"ref": "S1", "text": "A is 3 m."}]})
    assert r.status_code == 200 and len(r.json()["claims"]) == 2


def test_model_busy_becomes_503(monkeypatch):
    async def busy(*a, **k):
        raise common.ModelBusy("reserved")

    monkeypatch.setattr(tieback, "chat", busy)
    d = tieback.matches()[0]
    r = client.post("/tieback/api/memo", json={"discovery": d["name"], "host": d["best"]["host"]})
    assert r.status_code == 503


def test_prefix_routes():
    c = TestClient(studio.app)
    import os

    if os.environ.get("ROOT_PATH"):
        assert c.get(os.environ["ROOT_PATH"] + "/api/apps").status_code == 200


def test_scorecard_sample_keeps_topic(monkeypatch):
    from sketches import scorecard

    async def fake_agent(q):
        return {"answer": "x", "sources": [], "seconds": 0.1}

    async def fake_judge(q, ref, ans):
        return {"correct": True, "why": ""}

    monkeypatch.setattr(scorecard.detective, "rag", lambda q, mode: fake_agent(q))
    monkeypatch.setattr(scorecard, "judge", fake_judge)
    import asyncio

    out = asyncio.run(scorecard.answers(8, ["closed"]))
    assert out["answers"]["closed"]["n"] >= 8 and out["answers"]["closed"]["by_topic"]


# -- the Data Atlas --


def test_atlas_safe_drops_nan():
    from sketches import atlas

    assert atlas.safe({"a": [1.0, float("nan")], "b": float("inf")}) == {"a": [1.0, None], "b": None}


def test_atlas_catalog_splits_origins():
    d = client.get("/atlas/api/catalog", params={"all": True}).json()["datasets"]
    assert {x["origin"] for x in d} == {"mail", "earlier"}
    assert next(x for x in d if x["id"] == "completion")["path"] == "official/completion_reports"


def test_atlas_well_joins_datasets():
    w = client.get("/atlas/api/well/15/9-13").json()
    assert w["name"] == "15/9-13"
    assert w["in"]["logs"] and w["in"]["realpore"]
    assert len(w["plugs"]["md"]) > 100 and len(w["tops"]) > 5
    assert client.get("/atlas/api/well/not-a-well").status_code == 404


def test_atlas_reserves_use_latest_estimate():
    k = client.get("/atlas/api/profile/factpages").json()["kpis"]
    assert 1000 < k["remaining_oe"] < 5000  # summing every yearly estimate gives about 67,000


def test_atlas_completion_report_pages():
    r = client.get("/atlas/api/reports/15/9-F-5").json()
    assert r["folder"] == "15_9-F-5" and r["reports"][0]["pages"]
    f = r["reports"][0]["file"]
    p = client.get("/atlas/api/page/15/9-F-5", params={"file": f, "n": 3}).json()
    assert p["markdown"] and p["ai"]["page_summary"]
    assert client.get("/atlas/api/pdf/..%2F..%2F/x.pdf").status_code == 404  # nothing outside the reports folder


def test_atlas_focus_is_seismic():
    d = client.get("/atlas/api/catalog").json()
    assert {x["id"] for x in d["datasets"]} == {"adele", "f3"} and d["focus"]


def test_atlas_seismic_slices():
    from sketches import atlas_seis

    r = client.get("/atlas/api/seis/slice/adele", params={"axis": "time", "i": 500})
    assert r.headers["x-shape"] == "301,2731" and len(r.content) == 301 * 2731
    r = client.get("/atlas/api/seis/slice/f3", params={"axis": "inline", "i": 10, "split": "test1"})
    assert r.headers["x-shape"] == "510,701" and r.headers["x-labels"] == "1"  # amplitudes, then labels
    assert client.get("/atlas/api/seis/slice/adele", params={"axis": "inline", "i": 301}).status_code == 404
    t = client.get("/atlas/api/seis/trace/adele", params={"il": 205, "xl": 401}).json()
    assert (t["il"], t["xl"]) == (4585, 6071) and t["peak"] > 300000  # the spike
    assert next(h for h in t["header"] if h["byte"] == 189)["value"] == 4585
    a = np.random.default_rng(0).normal(size=(5, 5, 40))
    assert atlas_seis.semblance(np.repeat(a[:1, :1], 5, 0).repeat(5, 1), (3, 3, 1), (1, 1, 9)).min() > 0.99  # identical traces
    assert atlas_seis.semblance(a, (3, 3, 1), (1, 1, 9)).mean() < 0.5  # noise


def test_atlas_resolution_is_measured():
    for cube, inline_m in (("adele", 37.5), ("f3", 25.0)):
        r = client.get(f"/atlas/api/seis/resolution/{cube}").json()
        assert r["inline"]["d"] == inline_m and len(r["windows"]) == 4
        for ax in ("crossline", "inline", "time"):
            assert r[ax]["nyquist"] > r[ax]["k95"] > 0  # both cubes are sampled finer than their content needs


def test_atlas_slice_step_is_a_light_preview():
    full = client.get("/atlas/api/seis/slice/adele", params={"axis": "inline", "i": 10})
    light = client.get("/atlas/api/seis/slice/adele", params={"axis": "inline", "i": 10, "step": 3})
    assert light.headers["x-shape"] == "334,911" and len(light.content) * 8 < len(full.content)
    assert client.get("/atlas/api/seis/slice/adele", params={"axis": "inline", "i": 10, "step": 0}).status_code == 422


def test_theme_script_is_served():
    r = client.get("/theme.js")
    assert r.status_code == 200 and "studio-theme" in r.text


def test_atlas_volume_is_a_coarse_copy():
    r = client.get("/atlas/api/seis/volume/adele")
    ni, nx, nt = map(int, r.headers["x-shape"].split(","))
    assert (ni, nx, nt) == (51, 69, 83) and len(r.content) == ni * nx * nt and r.headers["x-steps"] == "6,40,12"
    f = client.get("/atlas/api/seis/volume/f3", params={"split": "test2"})
    assert f.headers["x-shape"].split(",")[1] == "15"


def test_greenclay_extracts_depth_and_confidence():
    from sketches.greenclay import extract_page

    def one(text):
        got, _ = extract_page(text)
        return got[0]

    r = one("| 2630 | Claystone | 100 | dark olive grey, glauconitic |")  # a cuttings row: depth in the first cell
    assert (r["kind"], r["depth_from"], r["depth_to"], r["confidence"]) == ("glauconite", 2630.0, None, "high")
    r = one("From 2300 to 2350 m: sandstone with green clay laminae")
    assert (r["kind"], r["depth_from"], r["depth_to"], r["depth_unit"], r["confidence"]) == ("green clay", 2300.0, 2350.0, "m", "high")
    r = one("Siltstone, grading to sandy siltstone with 10-20% sand; glauconitic")  # 10-20 % is not a depth
    assert r["depth_from"] is None and r["confidence"] == "low"
    r = one("| 25 | 2382.6 | SILTSTONE, firm, glauconite blebs |")  # a sample number, then the depth
    assert (r["depth_from"], r["depth_to"]) == (2382.6, None)
    r = one("| TOP GREEN CLAY | 875.0 | 897.0 | +/- 25 | 870.0 |")  # a tops table: the top, not a 875-897 interval
    assert r["marker"] and (r["depth_from"], r["depth_to"]) == (875.0, None)
    assert one("Chlorite is listed in the 1995-2001 bibliography")["depth_from"] is None  # years are not depths


def test_greenclay_each_sentence_gets_its_own_interval():
    from sketches.greenclay import extract_page

    got, _ = extract_page("Balder Formation (2394 - 2459 m MD): bluish grey tuff. Sele Formation (2459 - 2527 m MD): olive green claystone, glauconitic.")
    assert {(g["depth_from"], g["depth_to"], g["formation"]) for g in got} == {(2459.0, 2527.0, "Sele Formation")}
