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
