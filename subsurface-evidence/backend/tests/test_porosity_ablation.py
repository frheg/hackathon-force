import numpy as np
import pandas as pd
import pytest

from se.modeling.porosity_ablation import (
    COMPARISONS,
    _weights,
    folds,
    formation_prior,
    metrics,
)
from se.modeling.rock_porosity import metrics as rock_metrics
from se.modeling.rock_porosity import physics


def test_formation_prior_falls_back_to_train_group_then_global():
    train = pd.DataFrame({"formation": ["X", "Y", "X"], "group": ["A", "A", "B"], "porosity": [10, 20, 40]})
    test = pd.DataFrame({"formation": ["X", "NEW", "NEW"], "group": ["B", "A", "C"], "porosity": [100, 100, 100]})
    assert formation_prior(train, test, pd.Series([1., 1., 2.])).tolist() == [40, 15, 27.5]


def test_whole_wells_and_nearby_training_wells_are_purged():
    sites = pd.DataFrame({"x_km": [39., 41., 140., 240., 340.], "y_km": 0., "npdid": np.arange(5)})
    sites["block"] = sites.x_km // 40
    d = pd.concat([sites, sites], ignore_index=True)
    seen = np.zeros(len(d), dtype=int)
    for train, test, n in folds(d):
        seen += test
        assert not set(d.npdid[train]) & set(d.npdid[test])
        assert set(d.block[train]).isdisjoint(d.block[test])
        if set(d.npdid[test]) & {0, 1}:
            assert n == 1 and not set(d.npdid[train]) & {0, 1}
    assert (seen == 1).all()


def test_bootstrap_contrasts_the_correct_paired_models():
    d = pd.DataFrame({"npdid": [1, 1, 2], "log_row": [0, 0, 1], "block": ["a", "a", "b"], "porosity": 10.})
    d[list(COMPARISONS)] = [[20., 14., 15., 11., 12.]] * len(d)
    assert _weights(d).tolist() == [0.5, 0.5, 1.0]
    result = metrics(d)
    assert result["gain_block_bootstrap_90_pp"] == pytest.approx([3., 3.])
    assert result["gain_vs_formation_prior_block_bootstrap_90_pp"] == pytest.approx([2., 2.])


def test_rock_physics_uses_measured_units_and_no_core_label():
    d = pd.DataFrame({"DTC": [101.6], "DTS": [152.4], "RHOB": [2.328], "porosity": [94.]})
    a = physics(d).iloc[0]
    assert a.density_phi_pct == pytest.approx(20.)
    assert a.vpvs == pytest.approx(1.5)
    assert a.shear_gpa == pytest.approx(2.328 * 4)
    assert a.bulk_gpa == pytest.approx(2.328 * (9 - 16 / 3))


def test_rock_comparison_uses_paired_whole_block_errors():
    d = pd.DataFrame({"npdid": [1, 1, 2], "log_row": [0, 0, 1], "block": ["a", "a", "b"], "porosity": 10.,
                      "fixed_density": 20., "raw_logs": 15., "raw_plus_physics": 12.})
    scores = rock_metrics(d)
    assert scores["gain_block_bootstrap_90_pp"] == pytest.approx([3., 3.])
    assert scores["gain_well_bootstrap_90_pp"] == pytest.approx([3., 3.])
