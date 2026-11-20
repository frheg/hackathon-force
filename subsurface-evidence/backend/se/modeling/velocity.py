"""Fit effective vertical interval velocities; evaluate only at tied horizons."""

from dataclasses import dataclass
from itertools import pairwise
from math import isfinite, sqrt
from statistics import mean


@dataclass(frozen=True)
class HorizonTie:
    horizon: str
    twt_ms: float
    depth_m: float  # Positive down, below mean sea level.


@dataclass(frozen=True)
class WellTie:
    well: str
    seabed_twt_ms: float
    water_depth_m: float
    horizons: tuple[HorizonTie, ...]


def steps(tie: WellTie) -> list[tuple[float, float]]:
    t, z = tie.seabed_twt_ms, tie.water_depth_m
    if not isfinite(t) or not isfinite(z) or t <= 0 or z <= 0:
        raise ValueError(f"{tie.well}: invalid seabed reference")
    out = []
    for h in tie.horizons:
        dt, dz = h.twt_ms - t, h.depth_m - z
        if not isfinite(dt) or not isfinite(dz) or dt <= 0 or dz <= 0:
            raise ValueError(f"{tie.well}: time and depth must increase at {h.horizon}")
        out.append((dt, dz))
        t, z = h.twt_ms, h.depth_m
    return out


def vertical_velocity(dt_ms: float, dz_m: float) -> float:
    return 2000 * dz_m / dt_ms


def _time_steps(tie: WellTie) -> list[float]:
    # Prediction may use interpreted horizon times, never their test-well depths.
    times = [tie.seabed_twt_ms, *(h.twt_ms for h in tie.horizons)]
    return [b - a for a, b in pairwise(times)]


def _layer_depths(tie: WellTie, velocities: list[float]) -> list[float]:
    z = tie.water_depth_m
    out = []
    for dt, v in zip(_time_steps(tie), velocities, strict=True):
        z += 0.0005 * dt * v
        out.append(z)
    return out


def _fit_average_rock_velocity(ties: list[WellTie]) -> float:
    """Through-origin least squares on cumulative rock times; equal weight per well."""
    numerators, denominators = [], []
    for tie in ties:
        dt = [h.twt_ms - tie.seabed_twt_ms for h in tie.horizons]
        dz = [h.depth_m - tie.water_depth_m for h in tie.horizons]
        numerators.append(mean(t * z for t, z in zip(dt, dz, strict=True)))
        denominators.append(mean(t * t for t in dt))
    return 2000 * mean(numerators) / mean(denominators)


def score(errors: list[float]) -> dict:
    return {
        "n": len(errors),
        "mae_m": mean(abs(x) for x in errors),
        "rmse_m": sqrt(mean(x * x for x in errors)),
        "bias_m": mean(errors),
        "max_abs_m": max(abs(x) for x in errors),
    }


def evaluate(ties: list[WellTie], preview_velocity_mps: float = 2000.0) -> dict:
    """Withhold entire well sites; the target is TVDSS at corresponding horizon picks."""
    if len(ties) < 2 or len({t.well for t in ties}) != len(ties):
        raise ValueError("evaluation needs at least two distinct well sites")
    if not isfinite(preview_velocity_mps) or preview_velocity_mps <= 0:
        raise ValueError("preview velocity must be positive and finite")
    horizons = tuple(h.horizon for h in ties[0].horizons)
    if not horizons or len(set(horizons)) != len(horizons):
        raise ValueError("need a unique, nonempty shared sequence of horizon identifiers")
    for tie in ties:
        if tuple(h.horizon for h in tie.horizons) != horizons:
            raise ValueError(f"{tie.well}: horizon sequence does not match the other well sites")
        steps(tie)

    folds = []
    for held in ties:
        train = [t for t in ties if t.well != held.well]
        intervals = [steps(t) for t in train]
        velocities = [mean(vertical_velocity(*x) for x in layer) for layer in zip(*intervals, strict=True)]
        average = _fit_average_rock_velocity(train)
        fitted = {
            "ui_constant": [0.0005 * h.twt_ms * preview_velocity_mps for h in held.horizons],
            "seabed_fixed_rock": _layer_depths(held, [preview_velocity_mps] * len(horizons)),
            "seabed_fitted_rock": _layer_depths(held, [average] * len(horizons)),
            "layer_cake": _layer_depths(held, velocities),
        }
        rows = []
        for i, h in enumerate(held.horizons):
            predicted = {name: p[i] for name, p in fitted.items()}
            rows.append({
                "horizon": h.horizon, "twt_ms": h.twt_ms, "reference_depth_m": h.depth_m,
                "prediction_m": predicted, "error_m": {name: p - h.depth_m for name, p in predicted.items()},
            })
        folds.append({
            "held_out_site": held.well, "training_sites": [t.well for t in train],
            "average_rock_velocity_mps": average, "interval_velocities_mps": dict(zip(horizons, velocities, strict=True)),
            "scores": {name: score([r["error_m"][name] for r in rows]) for name in fitted}, "rows": rows,
        })
    return {
        "split": "leave one well site out",
        "sites": len(ties), "horizons": list(horizons), "folds": folds,
        "pooled_scores": {name: score([r["error_m"][name] for f in folds for r in f["rows"]]) for name in folds[0]["scores"]},
        "prediction_interval": None,
    }
