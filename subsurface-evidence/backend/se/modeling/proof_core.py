"""Limited, honest GPU proof: predict RealPore properties from FORCE 2020 logs.

This is not a general NCS foundation model. It proves one cross-modal relation:
measured wireline curves -> direct core-plug porosity/permeability. All splits are
whole-well and spatially blocked; the labelled FORCE hidden-test file is never read.

Run from backend:
  LD_LIBRARY_PATH=/run/opengl-driver/lib ../../.venv-gpu/bin/python -m se.modeling.proof_core
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

from se.config import DATA, OUT
from se.ingest.names import norm

try:
    import torch
    from torch import nn
except ImportError as e:  # type: ignore[assignment]
    raise SystemExit("GPU proof needs the repository's .venv-gpu torch environment") from e

SEED = 7
CURVES = ("GR", "RHOB", "NPHI", "DTC", "RDEP", "RMED", "RSHA", "PEF", "CALI", "DRHO")
TARGETS = ("porosity", "log10_perm")
OUT_DIR = OUT / "proof_core"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def nearest_join() -> tuple[pd.DataFrame, dict]:
    """Match each core plug to its closest log sample, <=0.5 m, without hidden_test."""
    rp_path = DATA / "official" / "realpore" / "realpore.parquet"
    log_path = DATA / "force2020" / "train.csv"
    rp = pd.read_parquet(rp_path)
    logs = pd.read_csv(log_path, sep=";")
    rp["wellbore"] = rp.wellbore.map(norm)
    logs["wellbore"] = logs.WELL.map(norm)
    overlap = sorted(set(rp.wellbore) & set(logs.wellbore))
    out = []
    for well in overlap:
        p = rp[rp.wellbore == well].sort_values("md").copy()
        q = logs[logs.wellbore == well].sort_values("DEPTH_MD").copy()
        z = q.DEPTH_MD.to_numpy(float)
        if not len(z):
            continue
        j = np.searchsorted(z, p.md.to_numpy(float))
        left = np.clip(j - 1, 0, len(z) - 1)
        right = np.clip(j, 0, len(z) - 1)
        pick = np.where(abs(z[right] - p.md.to_numpy(float)) < abs(z[left] - p.md.to_numpy(float)), right, left)
        distance = abs(z[pick] - p.md.to_numpy(float))
        keep = distance <= 0.5
        if not keep.any():
            continue
        joined = q.iloc[pick[keep]].reset_index(drop=True)[[*CURVES, "DEPTH_MD", "X_LOC", "Y_LOC", "GROUP", "FORMATION"]].copy()
        p = p.iloc[np.flatnonzero(keep)].reset_index(drop=True)
        joined.insert(0, "wellbore", well)
        joined["core_index"] = p.index.to_numpy()
        joined["depth_distance_m"] = distance[keep]
        joined["porosity"] = pd.to_numeric(p.porosity, errors="coerce")
        joined["perm"] = pd.to_numeric(p.perm, errors="coerce")
        joined["rock"] = p.rock.astype("string")
        joined["npdid"] = p.npdid
        out.append(joined)
    data = pd.concat(out, ignore_index=True)
    data = data[(data.porosity.between(0, 55) | data.perm.ge(0))].copy()
    data["log10_perm"] = np.log10(data.perm.where(data.perm > 0))
    data = data[(data.porosity.notna() | data.log10_perm.notna())].copy()
    diagnostics = {
        "excluded_hidden_test": True,
        "training_file": str(log_path),
        "overlap_wells": len(overlap),
        "matched_rows": len(data),
        "porosity_rows": int(data.porosity.notna().sum()),
        "permeability_rows": int(data.log10_perm.notna().sum()),
        "max_depth_distance_m": float(data.depth_distance_m.max()),
        "mean_depth_distance_m": float(data.depth_distance_m.mean()),
        "sources": [str(log_path), str(rp_path)],
        "sha256": {str(log_path): sha256(log_path), str(rp_path): sha256(rp_path)},
    }
    return data, diagnostics


def spatial_blocks(data: pd.DataFrame) -> np.ndarray:
    w = data.groupby("wellbore").agg(x=("X_LOC", "median"), y=("Y_LOC", "median"))
    return ((np.floor(w.x.to_numpy(float) / 40_000) * 10_000_000) + np.floor(w.y.to_numpy(float) / 40_000)).astype("int64")


def metrics(y: np.ndarray, p: np.ndarray, mask: np.ndarray) -> dict:
    a, b = y[mask], p[mask]
    rmse = float(np.sqrt(np.mean((b - a) ** 2)))
    mae = float(np.mean(abs(b - a)))
    var = float(np.sum((a - np.mean(a)) ** 2))
    r2 = float(1 - np.sum((b - a) ** 2) / var) if var > 0 else math.nan
    return {"n": len(a), "rmse": rmse, "mae": mae, "r2": r2}


class MLP(nn.Module):
    def __init__(self, width: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(width, 128),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(128, 64),
            nn.GELU(),
            nn.Dropout(0.05),
            nn.Linear(64, 2),
        )

    def forward(self, x):
        return self.net(x)


def prepare(x: pd.DataFrame, train: np.ndarray) -> tuple[np.ndarray, dict]:
    v = x[list(CURVES) + ["DEPTH_MD"]].copy()
    for c in v.columns:
        v[c] = pd.to_numeric(v[c], errors="coerce")
    median = v.iloc[train].median().fillna(0.0)
    scale = v.iloc[train].sub(median).abs().median().replace(0, 1.0).fillna(1.0) * 1.4826
    values = v.fillna(median).sub(median).div(scale).clip(-10, 10)
    missing = v.isna().astype(float).add_suffix("_missing")
    return np.c_[values.to_numpy(float), missing.to_numpy(float)], {"median": median.to_dict(), "scale": scale.to_dict()}


def train_mlp(x: np.ndarray, y: np.ndarray, mask: np.ndarray, train: np.ndarray, device: str, epochs: int = 100) -> tuple[np.ndarray, float]:
    torch.manual_seed(SEED)
    centre = np.nanmedian(y[train], axis=0)
    spread = np.nanstd(y[train], axis=0)
    spread = np.where(np.isfinite(spread) & (spread > 0), spread, 1.0)
    y_scaled = np.where(np.isfinite(y), (y - centre) / spread, 0.0)
    tr = torch.as_tensor(x[train], dtype=torch.float32, device=device)
    ty = torch.as_tensor(y_scaled[train], dtype=torch.float32, device=device)
    tm = torch.as_tensor(mask[train], dtype=torch.float32, device=device)
    model = MLP(x.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    started = time.time()
    best = math.inf
    best_state = None
    for _ in range(epochs):
        model.train()
        order = torch.randperm(len(tr), device=device)
        for lo in range(0, len(tr), 1024):
            idx = order[lo : lo + 1024]
            pred = model(tr[idx])
            loss = (((pred - ty[idx]) ** 2) * tm[idx]).sum() / tm[idx].sum().clamp_min(1)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            loss = float((((model(tr) - ty) ** 2 * tm).sum() / tm.sum().clamp_min(1)).cpu())
        if loss < best:
            best, best_state = loss, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pred = model(torch.as_tensor(x, dtype=torch.float32, device=device)).cpu().numpy()
    return (pred * spread + centre).astype(float), time.time() - started


def run(device: str | None = None) -> dict:
    random.seed(SEED)
    np.random.seed(SEED)
    data, diagnostics = nearest_join()
    wells = pd.Series(data.wellbore.unique()).sort_values().to_numpy()
    blocks = dict(zip(wells, spatial_blocks(data)))
    groups = np.array([blocks[w] for w in data.wellbore])
    y = data[[*TARGETS]].to_numpy(float)
    mask = np.isfinite(y)
    raw = prepare(data, np.arange(len(data)))[0]
    folds = list(GroupKFold(n_splits=5).split(raw, groups=groups))
    predictions = {"median": np.empty_like(y), "histgb": np.empty_like(y), "mlp": np.empty_like(y)}
    predictions["median"].fill(np.nan)
    predictions["histgb"].fill(np.nan)
    predictions["mlp"].fill(np.nan)
    fold_diag, timings = [], 0.0
    chosen_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    for fold, (tr_all, te) in enumerate(folds):
        x, scaler = prepare(data, tr_all)
        fold_diag.append({"fold": fold, "test_blocks": int(np.unique(groups[te]).size), "test_wells": int(data.iloc[te].wellbore.nunique()), "train_wells": int(data.iloc[tr_all].wellbore.nunique()), "scaler": scaler})
        for target_i, target in enumerate(TARGETS):
            tr = tr_all[mask[tr_all, target_i]]
            ok = mask[te, target_i]
            mean = float(np.nanmedian(y[tr, target_i]))
            predictions["median"][te, target_i] = mean
            est = HistGradientBoostingRegressor(max_iter=150, learning_rate=0.06, max_depth=4, l2_regularization=1.0, random_state=SEED)
            est.fit(x[tr], y[tr, target_i])
            predictions["histgb"][te, target_i] = est.predict(x[te])
            assert ok.sum() >= 0
        p, elapsed = train_mlp(x, np.nan_to_num(y), mask, tr_all, chosen_device)
        timings += elapsed
        predictions["mlp"][te] = p[te]
    report = {
        "model": "masked-MLP-v1",
        "purpose": "Limited proof of FORCE log -> RealPore core relation; not an NCS foundation-model claim.",
        "device": chosen_device,
        "split": {"name": "GroupKFold whole-well by 40 km spatial blocks", "folds": 5, "hidden_test_used": False, "seed": SEED},
        "data": diagnostics,
        "folds": fold_diag,
        "training_seconds": round(timings, 2),
        "metrics": {},
        "limitations": ["only 69 overlapping wells", "whole-well/generalization test, not a blind geographic region", "core plugs are sampled non-randomly", "no independent validation of reported mineralogy", "porosity/permeability measurements have heterogeneous tools and units", "does not yet use text or seismic"],
    }
    for target_i, target in enumerate(TARGETS):
        report["metrics"][target] = {}
        for model, pred in predictions.items():
            report["metrics"][target][model] = metrics(y[:, target_i], pred[:, target_i], mask[:, target_i])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    pd.DataFrame({
        "wellbore": data.wellbore,
        **{f"y_{t}": y[:, i] for i, t in enumerate(TARGETS)},
        **{f"{m}_{t}": predictions[m][:, i] for m in predictions for i, t in enumerate(TARGETS)},
        "source_train_csv": "data/force2020/train.csv",
        "source_realpore": "data/official/realpore/realpore.parquet",
    }).to_parquet(OUT_DIR / "oof_predictions.parquet", index=False)
    print(json.dumps(report, indent=2, allow_nan=False))
    return report


if __name__ == "__main__":
    run(os.environ.get("MODEL_DEVICE"))
