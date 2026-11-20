import numpy as np
import pandas as pd
import yaml

from se.modeling.interval_screen import assess
from se.modeling.smeaheia_screen import INTERVAL_RULE


def fixture():
    # 80 m of pressure support. TVD from rig is 0.8 * MD; TVDSS is another 20 m shallower.
    m = np.arange(221)
    well = {"wellbore": "A", "npdid": 1, "rkb_m": 20, "water_m": 20,
            "markers": [{"unit_id": 151, "picks": [{"top_md_m": 200}], "excluded_rows": 0}]}
    path = pd.DataFrame({"md": m, "tvdss": 0.8*m-20})
    logs = pd.DataFrame({"WELL": "A", "DEPTH_MD": m+0.5, "GR": 50., "RDEP": 1., "DTC": 140.})
    tops = pd.DataFrame([("A", 1, "HORDALAND GP", 67, "GROUP", 100, 125),
                         ("A", 1, "ROGALAND GP", 131, "GROUP", 145, 180)],
                        columns=["wellbore", "npdid", "unit", "unit_id", "level", "top_md", "base_md"])
    mud = pd.DataFrame({"wellbore": "A", "npdid": 1, "md": [190, 210], "density": [1.1, 1.2]})
    tests = pd.DataFrame({"wellbore": "A", "npdid": 1, "md": [100, 180], "density": 2.2, "kind": "LOT"})
    return well, path, tops, mud, tests, logs, yaml.safe_load(INTERVAL_RULE.read_text())


def test_joint_not_additive_and_group_not_a_continuous_run():
    well, path, tops, mud, tests, logs, rule = fixture()
    logs.loc[(logs.DEPTH_MD >= 125) & (logs.DEPTH_MD < 151), "RDEP"] = 1.3
    r = assess(well, path, tops, mud, tests, logs, rule)
    s = r["strict"]
    assert (s["assessable_bins"], s["joint_bins"], s["longest_joint_m"]) == (80, 54, 29)
    assert s["state"] == "not seen on supported metres" and not s["intervals_md_m"]
    assert r["group_screen"]["in_window_m"] == 60 and r["group_screen"]["meets_total"]
    e = r["example_in_longest"]
    assert np.isclose(e["required_emw"], 0.2 + (1.1 - 0.2) * 160 / (e["md"]*0.8))
    assert e["available_emw"] == 2.2
    logs.loc[150, "RDEP"] = 1.
    s = assess(well, path, tops, mud, tests, logs, rule)["strict"]
    assert s["intervals_md_m"] == [[150, 180]] and s["state"] == "candidate interval"


def test_missing_sonic_gap_and_rows_are_not_spliced():
    well, path, tops, mud, tests, logs, rule = fixture()
    logs.loc[100:179, "DTC"] = np.nan
    # Additional same-bin samples with sonic but no RDEP must not patch the chosen row.
    other = logs.iloc[100:180].assign(DEPTH_MD=lambda d: d.DEPTH_MD+0.1, DTC=150., RDEP=np.nan)
    logs = pd.concat([logs, other, logs.iloc[[135]]], ignore_index=True)
    logs.loc[159, "DTC"] = 135.  # measured borderline, not missing
    r = assess(well, path, tops, mud, tests, logs, rule)
    assert r["strict"]["state"] == "insufficient evidence"
    assert r["optional_sonic"]["intervals_md_m"] == [[100, 135]]
    assert r["optional_sonic"]["joint_bins"] == 78  # ambiguous duplicate and borderline sonic break runs
    assert r["group_screen"]["in_window_m"] == 60


def test_no_extrapolation_no_fit_or_sidetrack_substitution():
    well, path, tops, mud, tests, logs, rule = fixture()
    tests = pd.concat([tests.iloc[:1], tests.iloc[1:].assign(kind="FIT"),
                       tests.iloc[1:].assign(wellbore="A T2"), tests.iloc[1:].assign(npdid=2)])
    r = assess(well, path, tops, mud, tests, logs, rule)
    assert r["unused_other_tests_above"] == 1 and len(r["lot_shoes_above"]) == 1
    assert r["strict"]["longest_joint_m"] is None and r["group_screen"]["in_window_m"] is None
    assert r["rock_signature_bins"] > 30  # rock alone cannot qualify
    _, _, _, _, two, _, _ = fixture()
    for bad_mud in (mud.iloc[:1], pd.concat([mud, mud.iloc[[1]].assign(density=1.5)])):
        r = assess(well, path, tops, bad_mud, two, logs, rule)
        assert r["assumed_pp_g_cm3"] is None and not r["strict"]["assessable_bins"]
    path = path[~path.md.between(178, 181)]
    r = assess(well, path, tops, mud, two, logs, rule)
    assert r["lot_shoes_above"][-1]["tvd_rkb_m"] is None and not r["strict"]["assessable_bins"]


def test_gates_must_coincide_at_same_depth():
    well, path, tops, mud, tests, logs, rule = fixture()
    tests["density"] = 1.4
    logs.loc[logs.DEPTH_MD >= 140, "GR"] = 40.
    r = assess(well, path, tops, mud, tests, logs, rule)
    assert min(r["rock_signature_bins"], r["pressure_window_log_bins"]) >= 30
    assert r["strict"]["longest_joint_m"] == 0 and not r["strict"]["intervals_md_m"]
