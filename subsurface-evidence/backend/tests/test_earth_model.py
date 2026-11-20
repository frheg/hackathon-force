"""Tests for the earth-model modules of P2.3-P7 (PLAN P7.3). Unit tests use small synthetic data; the artefact tests skip when the pilot
artefacts are not built on this machine."""
import numpy as np
import pandas as pd
import pytest
import yaml

from se.config import EARTH


def test_seismic_velocity_is_monotone_and_fits_a_synthetic_tie():
    from se.earth.seismic import Velocity

    rng = np.random.default_rng(0)
    tsb = rng.uniform(400, 500, 40); t = tsb + rng.uniform(200, 1500, 40); wd = 1500 * tsb / 2000
    dt = (t - tsb) / 2000; z = 1500 * tsb / 2000 + dt * (1800 + 900 * dt) + rng.normal(0, 5, 40)
    v = Velocity().fit(tsb, wd, t, z, rng.uniform(0, 50, (40, 2)), np.full(40, 25.0))
    assert abs(v.vw - 1500) < 1 and abs(v.ab[0] - 1800) < 60
    zz = v.depth(np.full(50, 450.0), np.linspace(460, 2000, 50))
    assert np.all(np.diff(zz) > 0)


def test_neighbour_features_leave_the_own_well_out():
    from se.earth.targets import nb_features

    tr = pd.DataFrame({"wellbore": ["a", "b", "c"], "unit": "U", "x": [0.0, 1.0, 2.0], "y": 0.0, "ev": [1.0, 0.0, 0.0], "w": 1.0})
    with_self = nb_features(tr, tr, self_out=False); without = nb_features(tr, tr, self_out=True)
    assert with_self.nb.iloc[0] > without.nb.iloc[0]  # well a's own HC no longer lifts its own neighbour rate
    assert without.prior.iloc[0] < with_self.prior.iloc[0]
    assert np.isfinite(without.d_km.iloc[0]) and without.d_km.iloc[0] == pytest.approx(1.0)


def test_report_facts_must_be_grounded_in_the_page():
    from se.earth.reports import grounded

    page = "Core porosity averages 23.5 % in the Sognefjord Formation. Weak oil show at 1550 m."
    assert grounded({"type": "porosity", "value": 23.5, "quote": "Core porosity averages 23.5 %"}, page)
    assert not grounded({"type": "porosity", "value": 25.0, "quote": "Core porosity averages 23.5 %"}, page)  # number not in quote
    assert not grounded({"type": "porosity", "value": 23.5, "quote": "porosity of 23.5 % measured"}, page)  # quote not on the page
    assert grounded({"type": "show", "value": None, "quote": "Weak oil show at 1550 m"}, page)


def test_rules_file_is_complete():
    from se.earth.rules import RULES

    kb = yaml.safe_load(RULES.read_text())
    ids = [r["id"] for r in kb["rules"]]
    assert len(ids) == len(set(ids)) >= 9
    for r in kb["rules"]:
        assert r["status"] in ("sourced", "sourced_unverified", "inferred") and r["sources"] and r["check"]["type"] and r["guard"]


def test_pressure_qc_flags_impossible_dst_values():
    from se.earth.pressure import qc

    o = pd.DataFrame({"kind": ["pore", "pore", "pore", "mud"], "emw_ss": [0.3, 1.1, 3.5, 1.4], "wellbore": "w", "src": "DST", "md": 1.0, "P": 1.0})
    q, s = qc(o)
    assert list(q.qc) == ["below hydrostatic: likely wellhead pressure", "ok", "above overburden: likely unit or entry error", "ok"]
    assert s["excluded_low"] == 1 and s["excluded_high"] == 1


need = pytest.mark.skipif(not (EARTH / "targets" / "cells.parquet").exists(), reason="pilot artefacts not built here")


@need
def test_grid_has_no_gaps_and_surfaces_keep_order():
    g = np.load(EARTH / "grid.npz"); dz = np.diff(g["zb"].astype(np.float64), axis=0)
    assert (dz[:, g["inside"]] >= -1e-3).all()
    s = np.load(EARTH / "surfaces.npz"); lev = list(s["level"]); M = s["mean"]
    gi = [i for i, l in enumerate(lev) if l in ("SEABED", "GROUP")]
    assert all(((M[b] >= M[a] - 1e-6) | ~s["inside"]).all() for a, b in zip(gi, gi[1:]))


@need
def test_targets_have_probability_range_and_support():
    import json

    rep = json.loads((EARTH / "targets" / "report.json").read_text())
    for t in ("hydrocarbons", "reservoir", "overpressure", "green_clay", "calcareous_clay", "sandy_delta", "co2_storage"):
        d = np.load(EARTH / "targets" / f"{t}.npz")
        assert len(d["p"]) == len(d["support"]) > 1000
        # p is the mean over the realisations (total probability); with a skewed spread it can lie outside the 5-95 percent range
        assert (d["p05"] <= d["p95"] + 1e-6).all() and ((d["p"] >= 0) & (d["p"] <= 1)).all() and (d["support"] >= 0).all() and (d["support"] <= 1).all()
        assert t == "co2_storage" or rep[t]["published"] in ("model", "unit prior", "base rate")


@need
def test_earth_api_cell_evidence():
    from se.api import earth

    c = earth.cell("hydrocarbons", 1000)
    assert {"unit", "p", "p05", "p95", "support", "nearest_observations", "rules"} <= set(c)
    t = earth.target("reservoir", pmin=0.8, limit=50)
    assert t["shown"] <= 50 and all(p >= 0.8 for p in t["p"])


# ---------------------------------------------------------------- P9 (LOG L075)
def test_closure_finds_a_dome_and_nothing_on_a_plane():
    from se.earth.factors import closure

    y, x = np.mgrid[0:41, 0:41].astype(float)
    dome = 2000 - 60 * np.exp(-((x - 20) ** 2 + (y - 20) ** 2) / 40) + 2 * x  # a dome on a gentle dip (depth, positive down)
    c = closure(dome)
    assert c[20, 20] > 30 and c[0].max() == 0 and c[:, 0].max() == 0
    assert closure(2000 + 2 * x).max() == 0
    gap = dome.copy(); gap[18:23, 18:23] = np.nan  # an absent unit is not a closure
    assert np.all(closure(gap)[18:23, 18:23] == 0)


def test_burial_map_shrinks_to_zero_far_from_wells():
    from se.earth.poroperm import burial_map

    tr = pd.DataFrame({"wellbore": ["a", "a", "b"], "x": [0.0, 0.0, 5.0], "y": 0.0, "E_own": [1500.0, 1700.0, 1600.0]})
    near, far = burial_map(tr, [1.0, 2000.0], [0.0, 0.0])
    assert 500 < near < 1700 and abs(far) < 1  # K_E pseudo-wells at 0: two wells give about 45 percent of their value
    assert burial_map(tr, [0.0], [0.0], exclude=["a"])[0] < near  # own well left out


@pytest.mark.skipif(not (__import__("se.config", fromlist=["DATA"]).DATA / "woa23" / "t00an01.csv.gz").exists(), reason="WOA23 not downloaded")
def test_seabed_temperature_is_cold_in_the_deep_norwegian_sea():
    from se.earth.seabed import bottom_temperature
    from se.evidence.spatial import project

    p = project([3.0, 4.0], [60.0, 66.5])
    t = bottom_temperature(p[:, 0], p[:, 1], [120.0, 1500.0])
    assert 5 < t[0] < 10 and t[1] < 1


def test_features_never_read_discovery_or_field_outlines():
    """P9.11: discoveries and fields are partly the same facts as our labels; no feature module may read them."""
    import re
    from pathlib import Path

    from se.earth import targets

    bad = re.compile(r"\b(from|join)\s+(discovery|field)\w*|discovery\w*\.(csv|parquet|geojson)|field\w*\.(csv|parquet|geojson)|dscName|fldName|wlbDiscovery|wlbField", re.I)
    for m in ("factors", "targets", "poroperm", "temperature", "seabed", "lithology", "gamma"):
        src = (Path(targets.__file__).parent / f"{m}.py").read_text()
        assert not bad.search(src), f"{m}.py reads discovery or field data"
    feats = {f for v in targets.FEATS.values() for f in v} | {f for v in targets.CAND.values() for f in v}
    assert not any(k in f for f in feats for k in ("disc", "field", "fld"))


# ---------------------------------------------------------------- P10 (LOG L076)
def test_fill_and_spill_sends_kitchen_oil_into_the_dome():
    from se.earth.factors import migrate

    y, x = np.mgrid[0:41, 0:41].astype(float)
    top = 2000 - 60 * np.exp(-((x - 20) ** 2 + (y - 20) ** 2) / 40) + 2 * x  # dome on a gentle dip down to the east (deeper = larger x)
    kitchen = ((x > 34) & (abs(y - 20) < 4)).astype(float)  # a mature source in the deep east, in line with the dome
    clos, chg, pc = migrate(top, kitchen, 4.0)
    assert clos[20, 20] > 20 and chg[20, 20] > 0 and pc[20, 20] > 0.99  # oil from the east reaches the crest
    assert chg[2, 20] == 0 and pc[2, 20] < 0.01  # off the flow path (far north of the dome and the kitchen): nothing arrives
    assert np.all(chg[clos > 1] == chg[20, 20])  # a closure holds what passes its spill point, everywhere inside it


def test_monte_carlo_keeps_rare_rates_rare():
    """P10.1 bug: normal noise on the logit pulled rare targets towards 0.5; beta draws keep the mean near the rate."""
    from se.earth.targets import Model, monte_carlo

    rng = np.random.default_rng(0); n = 400
    F = pd.DataFrame({"prior": np.full(n, 0.01), "nb": np.full(n, 0.01), "n_unit": np.full(n, 2.0), "n_nb": np.full(n, 1.0), "zb_km": rng.uniform(1, 3, n)})
    F["lp"], F["lnb"] = np.log(0.01 / 0.99), np.log(0.01 / 0.99)
    y = (rng.random(n) < 0.01).astype(float); y[:4] = 1
    m = Model(["lp", "lnb", "zb_km"]).fit(F.assign(lp=F.lp + rng.normal(0, 1, n)), y, np.ones(n))
    mean, lo, hi = monte_carlo(m, F, None, n=60)
    assert mean.mean() < 0.1 and (lo <= mean + 1e-9).all() and (mean <= hi + 1e-9).all()


def test_sidetracks_get_their_parents_depth():
    """Owner question (25/1-14 G, MD 10,444 m): a sidetrack without TVD takes its parent's TVD, not its measured length."""
    from se.earth.frame import estimate_tvd

    w = pd.DataFrame({"wellbore": ["9/1-1", "9/1-1 A", "9/2-1", "9/2-1 B", "8/1-1"], "kind": "exploration", "td": [2250.0, 10400.0, 3000.0, 3200.0, 2600.0],
                      "tvd_td": [2250.0, np.nan, 2990.0, 2900.0, np.nan]})
    e, cal = estimate_tvd(w)
    e = e.set_index("wellbore")
    assert e.loc["9/1-1 A", "tvd_how"] == "parent" and abs(e.loc["9/1-1 A", "tvd_est"] - 2250) < 500
    assert e.loc["8/1-1", "tvd_how"] in ("class", "none") and e.loc["9/1-1", "tvd_how"] == "factpages"


def test_export_formats_have_the_right_sizes():
    from se.earth.export import _kw, irap, zmap

    z = np.arange(12.0).reshape(3, 4); z[0, 0] = np.nan; x, y = np.arange(4) * 1000.0, np.arange(3) * 1000.0
    ir = irap(z, x, y).split("\n"); assert ir[0] == "-996 3 1000.000000 1000.000000" and sum(len(l.split()) for l in ir[4:]) == 12 and "9999900.0000" in ir[4]
    zm = zmap(z, x, y, "t"); body = zm.split("@\n")[-1]; assert len(body.split()) == 12 and "1.0E+30" in body
    k = _kw("ACTNUM", np.ones(10, int), "{:d}"); assert k.startswith("ACTNUM\n") and k.strip().endswith("/") and len(k.split()) == 12
