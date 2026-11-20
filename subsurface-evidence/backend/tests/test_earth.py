"""Earth-model tests (PLAN.md P0-P7)."""
import json

import numpy as np

from se.config import PILOT, in_pilot


def test_pilot_box():
    assert in_pilot(60.5, 3.0) and not in_pilot(58.4, 1.9) and not in_pilot(61.6, 3.0)
    assert in_pilot(np.array([59.5, 61.5]), np.array([1.5, 4.5])).all() and PILOT["lat"] == (59.5, 61.5)


def test_manifest(tmp_path):
    from se.earth import manifest
    a = tmp_path / "in.txt"; a.write_text("x"); out = tmp_path / "art.parquet"
    m = manifest.write(out, [a], {"k": 1})
    j = json.loads((tmp_path / "art.parquet.manifest.json").read_text())
    assert j["inputs"][0]["sha256"] == manifest.sha256(a) and j["params"] == {"k": 1} and m["code"]


def test_approx_tvd_models():
    from se.earth.frame import approx_tvd
    md = np.array([0.0, 1000.0, 2000.0])
    tv, h = approx_tvd(md, 2000.0, 1500.0, np.nan, "ratio")
    assert np.allclose(tv, [0, 750, 1500]) and np.allclose(h[-1], np.sqrt(2000 ** 2 - 1500 ** 2))
    tv, h = approx_tvd(md, 2000.0, 1500.0, 1000.0, "kop")  # vertical to 1000 m, then 1000 m of hole for 500 m of depth
    assert np.allclose(tv, [0, 1000, 1500]) and h[1] == 0 and np.isclose(h[2], np.sqrt(1000 ** 2 - 500 ** 2))
    tv, h = approx_tvd(md, np.nan, np.nan, np.nan, "ratio")
    assert np.allclose(tv, md) and (h == 0).all()  # no TVD at TD: vertical, no offset


def test_frame_force_path_is_exact_and_sigma_covers():
    from se.earth.frame import Frame
    fr = Frame()
    wb = next(iter(fr.force)); g = fr.force[wb]
    a = fr.at(wb, g.md.to_numpy()[:50])
    assert a["source"] == "force" and np.allclose(a["tvdss"], g.tvdss.to_numpy()[:50]) and (a["sigma_z"] <= 1.0).all()


def test_datum_status():
    import pandas as pd
    from se.earth.tops import datum_checks

    class F:  # minimal stand-in for Frame.w
        w = pd.DataFrame({"kb": [25.0, 25.0, np.nan], "wd": [100.0, 100.0, 80.0], "pilot": [True, True, True]}, index=pd.Index(["a", "b", "c"], name="wellbore"))
    t = pd.DataFrame({"wellbore": ["a", "b", "c"], "top_md": [125.0, 160.0, 105.0]})
    d = datum_checks(F(), t).set_index("wellbore").status
    assert d["a"] == "consistent" and d["b"] == "inconsistent" and d["c"] == "no KB"


def test_gp_recovers_surface_and_calibrated_samples():
    from se.earth.gp import GP
    rng = np.random.default_rng(1)
    X = rng.uniform(0, 100, (150, 2)); f = lambda P: 1000 + 3 * P[:, 0] + 50 * np.sin(P[:, 1] / 15)
    y = f(X) + rng.normal(0, 5, 150)
    gp = GP().fit(X, y, obs_var=np.full(150, 25.0))
    Xs = rng.uniform(10, 90, (200, 2)); mu, var = gp.predict(Xs, latent=True)
    z = (mu - f(Xs)) / np.sqrt(var + 1e-9)
    assert np.sqrt(np.mean((mu - f(Xs)) ** 2)) < 15 and 0.75 < np.mean(np.abs(z) < 1.645) <= 1.0  # recovers the surface; intervals cover
    S = gp.sample(Xs[:40], 400, seed=2)
    assert np.abs(S.mean(1) - mu[:40]).max() < 2 and 0.8 < np.median(S.var(1) / var[:40]) < 1.2  # samples match the posterior (random-feature error is absolute, ~sill / features)
