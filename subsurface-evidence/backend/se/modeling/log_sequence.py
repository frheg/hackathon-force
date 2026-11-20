"""Sequence model proof: wireline depth context -> measured RealPore properties.

Scientific choice: petrophysical measurements at one depth are interpreted using
beds, boundaries, washouts and vertical trends, so a point-vector MLP discards
nearby context. A small temporal convolution is used rather than a large
Transformer because only 69 wells overlap and the sample sequence is short;
parameter count must be commensurate with independent well count.

Evaluation is the same whole-well, 40 km GroupKFold used by proof_core. The
labelled FORCE hidden-test set is never read. Missing curves carry explicit
masks, and the model is rejected if it does not beat a gradient-boosted point
baseline.
"""
from __future__ import annotations

import json
import math
import os
import random
import time

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from se.config import DATA, OUT
from se.ingest.names import norm
from se.modeling.proof_core import (
    CURVES,
    TARGETS,
    metrics,
    nearest_join,
    spatial_blocks,
)

try:
    import torch
    from torch import nn
except ImportError as e:  # type: ignore[assignment]
    raise SystemExit("Sequence proof needs the repository's .venv-gpu torch environment") from e

SEED = 7
WINDOW = 31
OUT_DIR = OUT / "proof_log_sequence"


class SequenceCNN(nn.Module):
    """Small masked temporal CNN with global context; about 55k parameters."""

    def __init__(self, channels: int):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv1d(channels, 48, 5, padding=2),
            nn.GELU(),
            nn.Conv1d(48, 48, 3, padding=1),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Conv1d(48, 96, 3, padding=1),
            nn.GELU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(96 + channels, 64), nn.GELU(), nn.Linear(64, 2))

    def forward(self, x: torch.Tensor, point: torch.Tensor, depth: torch.Tensor):
        context = self.encoder(x).squeeze(-1)
        return self.head(torch.cat([context, point, depth], dim=1))


def sequence_data(radius: int = WINDOW // 2) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (sequence values, point values, mask) in model order.

    Windows are within one well and preserve MD order. Edge positions are padded
    by repeated edge samples but masked as missing, avoiding synthetic geologic
    continuation across a file boundary.
    """
    logs = pd.read_csv(DATA / "force2020" / "train.csv", sep=";")
    logs["wellbore"] = logs.WELL.map(norm)
    logs = logs.sort_values(["wellbore", "DEPTH_MD"]).reset_index(drop=True)
    curves = list(CURVES)
    point, seq = [], []
    by_well = {w: g for w, g in logs.groupby("wellbore", sort=False)}
    for w, g in by_well.items():
        g = g.reset_index(drop=True)
        vals = g[curves + ["DEPTH_MD"]].apply(pd.to_numeric, errors="coerce")
        by_well[w] = (vals.to_numpy(float), g.DEPTH_MD.to_numpy(float))
    joined, _ = nearest_join()
    for r in joined.itertuples():
        vals, depths = by_well[r.wellbore]
        if len(depths) == 0:
            continue
        centre = int(np.argmin(abs(depths - r.DEPTH_MD)))
        lo, hi = centre - radius, centre + radius + 1
        left = max(lo, 0)
        right = min(hi, len(vals))
        window = vals[left:right]
        pad_l, pad_r = max(0, -lo), max(0, hi - len(vals))
        window = np.pad(window, ((pad_l, pad_r), (0, 0)), mode="edge") if len(window) else np.zeros((WINDOW, vals.shape[1]))
        values = window
        point.append(values[radius])
        seq.append(values.T)
    return np.asarray(seq, float), np.asarray(point, float), np.isfinite(np.asarray(seq, float))


def scaled(sequence: np.ndarray, point: np.ndarray, train: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    """Train-fold median/MAD scaling with explicit missing masks."""
    x = np.concatenate([sequence.transpose(0, 2, 1), point[:, None, :]], axis=1)
    tr = x[train].reshape(-1, x.shape[-1])
    median = np.nanmedian(tr, axis=0)
    mad = np.nanmedian(abs(tr - median), axis=0) * 1.4826
    scale = np.where(np.isfinite(mad) & (mad > 1e-6), mad, 1.0)
    transform = lambda a: np.clip((np.nan_to_num(a, nan=median) - median) / scale, -10, 10)
    sv = transform(sequence.transpose(0, 2, 1)).transpose(0, 2, 1)
    pv = transform(point)
    sm = np.isfinite(sequence).astype(float)
    pm = np.isfinite(point).astype(float)
    return np.concatenate([sv, sm], axis=1), np.concatenate([pv, pm], axis=1), {"median": median.tolist(), "scale": scale.tolist()}


def train_fold(sequence: np.ndarray, point: np.ndarray, y: np.ndarray, mask: np.ndarray, train: np.ndarray, test: np.ndarray, device: str, epochs: int = 45) -> tuple[np.ndarray, float]:
    x, p, _ = scaled(sequence, point, train)
    centre = np.nanmedian(y[train], axis=0)
    spread = np.nanstd(y[train], axis=0)
    spread = np.where(np.isfinite(spread) & (spread > 0), spread, 1.0)
    ys = np.where(np.isfinite(y), (y - centre) / spread, 0.0)
    tx = torch.as_tensor(x[train], dtype=torch.float32, device=device)
    tp = torch.as_tensor(p[train], dtype=torch.float32, device=device)
    ty = torch.as_tensor(ys[train], dtype=torch.float32, device=device)
    tm = torch.as_tensor(mask[train], dtype=torch.float32, device=device)
    model = SequenceCNN(x.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=3e-4)
    best, best_state = math.inf, None
    started = time.time()
    for _ in range(epochs):
        model.train()
        order = torch.randperm(len(train), device=device)
        for lo in range(0, len(order), 512):
            i = order[lo : lo + 512]
            pred = model(tx[i], tp[i, :-1], tp[i, -1:])
            loss = (((pred - ty[i]) ** 2) * tm[i]).sum() / tm[i].sum().clamp_min(1)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            pred = model(tx, tp[:, :-1], tp[:, -1:])
            val = float((((pred - ty) ** 2 * tm).sum() / tm.sum().clamp_min(1)).cpu())
        if val < best:
            best = val
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        allp = model(torch.as_tensor(x[test], dtype=torch.float32, device=device), torch.as_tensor(p[test, :-1], dtype=torch.float32, device=device), torch.as_tensor(p[test, -1:], dtype=torch.float32, device=device)).cpu().numpy()
    return allp * spread + centre, time.time() - started


def run(device: str | None = None) -> dict:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    joined, diagnostics = nearest_join()
    sequence, point, _ = sequence_data()
    if len(sequence) != len(joined):
        raise RuntimeError(f"sequence rows {len(sequence)} != joined rows {len(joined)}")
    y = joined[[*TARGETS]].to_numpy(float)
    target_mask = np.isfinite(y)
    wells = np.array(sorted(joined.wellbore.unique()))
    blocks = dict(zip(wells, spatial_blocks(joined)))
    groups = np.array([blocks[w] for w in joined.wellbore])
    folds = list(GroupKFold(5).split(sequence, groups=groups))
    pred = np.full_like(y, np.nan)
    chosen = device or ("cuda" if torch.cuda.is_available() else "cpu")
    elapsed = 0.0
    fold_info = []
    for fold, (train, test) in enumerate(folds):
        p, seconds = train_fold(sequence, point, y, target_mask, train, test, chosen)
        pred[test] = p
        elapsed += seconds
        fold_info.append({"fold": fold, "train_wells": int(joined.iloc[train].wellbore.nunique()), "test_wells": int(joined.iloc[test].wellbore.nunique()), "test_blocks": int(np.unique(groups[test]).size)})
    proof = json.loads((OUT / "proof_core" / "metrics.json").read_text())
    report = {
        "model": "temporal-CNN-v1",
        "window_samples": WINDOW,
        "purpose": "Test whether vertical wireline context improves held-out RealPore prediction over point baselines.",
        "scientific_rationale": "Wireline interpretation depends on bed boundaries, vertical trends and bad-hole context; a 31-sample window (~4.65 m at 15 cm spacing) captures local continuity without cross-well mixing. A small CNN is chosen over a Transformer because only 69 independent wells are available.",
        "device": chosen,
        "seed": SEED,
        "data": diagnostics,
        "folds": fold_info,
        "training_seconds": round(elapsed, 2),
        "baseline_model": "HistGradientBoosting on point curves from proof_core",
        "metrics": {target: {"sequence": metrics(y[:, i], pred[:, i], target_mask[:, i]), "point_histgb": proof["metrics"][target]["histgb"], "point_mlp": proof["metrics"][target]["mlp"]} for i, target in enumerate(TARGETS)},
        "limitations": ["69 wells; OOD geology remains uncertain", "GroupKFold blocks are spatial, but not a fully separate basin", "point/core joins are nearest-sample <=0.5 m; time-varying depth ties remain unmodelled", "CNN does not yet use text, stratigraphy, NPDID hierarchy or seismic", "a sequence score is not accepted unless it beats the point HistGradientBoosting baseline"],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    pd.DataFrame({"wellbore": joined.wellbore, **{f"y_{t}": y[:, i] for i, t in enumerate(TARGETS)}, **{f"sequence_{t}": pred[:, i] for i, t in enumerate(TARGETS)}}).to_parquet(OUT_DIR / "oof_predictions.parquet", index=False)
    print(json.dumps(report, indent=2, allow_nan=False))
    return report


if __name__ == "__main__":
    run(os.environ.get("MODEL_DEVICE"))
