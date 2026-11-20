import numpy as np
import pandas as pd
import pytest

from se.config import DATA
from se.modeling.core_alignment import CURVES, align
from se.modeling.sleipner_transfer import WELLS, run


def test_core_link_checks_npdid_and_retains_original_rows():
    core = pd.DataFrame({
        "wellbore": ["A", "A", "A", "A", "B", "A", "A"],
        "npdid": [1, 2, 1, 1, 2, 1, 1],
        "md": [101.4, 101, 100.05, 99.9, 100, 103, 101],
        "porosity": [20, 20, 20, 20, 20, 20, np.inf],
    })
    logs = pd.DataFrame({
        "WELL": ["NO A", "B", "A", "A", "A", "A"], "DEPTH_MD": [104, 100, 100, 101, 100, 103],
        **{curve: list(range(6)) for curve in CURVES},
    })
    registry = pd.DataFrame({"wellbore": ["A", "B"], "npdid": [1, 2]})
    aligned, audit = align(core, logs, registry, {2})
    assert aligned[["core_row", "log_row"]].to_numpy().tolist() == [[0, 3], [5, 5]]
    assert aligned.log_minus_core_md_m.tolist() == pytest.approx([-0.4, 0])
    assert audit["held_out_core_rows"] == 1
    assert audit["unresolved_identity_rows"] == 1


def test_external_transfer_excludes_field_and_handles_absent_phif(tmp_path):
    if not all((DATA / p).is_file() for p in WELLS.values()):
        pytest.skip("Sleipner benchmark LAS package missing")
    result = run(DATA, tmp_path)
    training = pd.read_parquet(tmp_path / "training_links.parquet")
    assert not set(training.npdid) & set(result["train"]["excluded_npdids"])
    assert {45, 2763}.issubset(result["train"]["excluded_npdids"])
    assert training.core_row.is_unique
    assert result["wells"]["15/9-13"]["metrics_same_rows"]["tree"] is None
    measured = result["wells"]["15/9-A-16"]["metrics_same_rows"]
    assert {entry["n"] for entry in measured.values()} == {12818}
    assert measured["sand_brine_density"]["rmse_pp"] < measured["tree"]["rmse_pp"]
