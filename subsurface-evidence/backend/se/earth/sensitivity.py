"""Sensitivity of the constants that have no data test of their own (PLAN P12.1, LOG L078).

Each constant is set to a low and a high value around the one used, everything else fixed, and the result it feeds is recomputed:
  ELL, K_UNIT, K_NB   neighbour kernel (km) and shrinkage counts of the target features  -> held-out gain (features as published)
  MIN_GAIN            margin for adding a candidate feature                               -> features chosen, held-out gain
  T_OIL               oil-window temperature                                              -> R-MATURE rate difference near a kitchen
  TRAP_FLOOR          P(trap) where no closure is seen                                     -> chance of success held-out gain
  NTG_SD, th_frac, E  net-to-gross sigma, thickness sigma / top sigma, storage efficiency -> region CO2 capacity P50 (Mt)
  support constants   n0 (3 observations), d0 (30 km), skill scale (0.1)                 -> share of cells with support >= 0.5
A result that moves a published decision (the published form, a rule verdict) or a headline number by more than its own uncertainty is
flagged "matters". Run per region: EARTH_REGION=<r> python -m se.earth.sensitivity
"""
import json
import time

import numpy as np
import pandas as pd

from se.config import EARTH
from se.earth import atomic

TARGETS = ("hydrocarbons", "reservoir", "overpressure")


def _gain(T, t, cols, family="logistic"):
    o = T.observations(t).reset_index(drop=True); FD = T.fold_designs(t, o)
    return T.evaluate(t, o, cols, FD, family=family)[0]["gain_model_vs_base"]


def model_constants(rep) -> list:
    from se.earth import targets as T

    out = []
    for name, lo, hi in (("ELL", 12.5, 50.0), ("K_UNIT", 5.0, 20.0), ("K_NB", 2.5, 10.0)):
        base = getattr(T, name)
        for t in TARGETS:
            cols, fam = rep[t]["features"], rep[t].get("family", "logistic"); g = {}
            for lab, v in (("low", lo), ("base", base), ("high", hi)):
                setattr(T, name, v); g[lab] = round(_gain(T, t, cols, fam), 4)
            setattr(T, name, base)
            out.append({"constant": name, "values": [lo, base, hi], "result": f"held-out gain, {t}", **g,
                        "matters": bool(max(abs(g["low"] - g["base"]), abs(g["high"] - g["base"])) > 0.02 or ((g["low"] > 0) != (g["base"] > 0)))})
    return out


def selection_margin() -> list:
    from se.earth import targets as T

    out = []
    for t in ("hydrocarbons", "oil"):
        o = T.observations(t).reset_index(drop=True); FD = T.fold_designs(t, o); r = {}
        for lab, v in (("low", 0.0), ("base", T.MIN_GAIN), ("high", 0.02)):
            T.MIN_GAIN = v; cols, _ = T.select(t, o, FD); r[lab] = (len(cols), round(T.evaluate(t, o, cols, FD)[0]["gain_model_vs_base"], 4))
        T.MIN_GAIN = 0.005
        out.append({"constant": "MIN_GAIN", "values": [0.0, 0.005, 0.02], "result": f"features chosen and held-out gain, {t}", "low": r["low"], "base": r["base"], "high": r["high"],
                    "matters": bool(abs(r["low"][1] - r["base"][1]) > 0.02 or abs(r["high"][1] - r["base"][1]) > 0.02)})
    return out


def oil_window() -> list:
    from se.earth import factors as Fm
    from se.earth.rules import boot_rate_diff
    from se.earth.targets import OUT_T

    o = pd.read_parquet(OUT_T / "hydrocarbons_obs.parquet"); base = Fm.T_OIL; r = {}
    for lab, v in (("low", 90.0), ("base", base), ("high", 110.0)):
        Fm.T_OIL = v; M = Fm.maturity(); f = Fm.at(o, {k: M[k].astype(np.float32) for k in ("p_oil", "kit_oil")})
        h = (f.lkit < np.log1p(10)).to_numpy()
        r[lab] = [round(x, 3) for x in boot_rate_diff(o[h], o[~h])] if h.sum() >= 20 and (~h).sum() >= 20 else None
    Fm.T_OIL = base
    verd = lambda x: None if x is None else ("agrees" if x[1] > 0 else "disagrees" if x[2] < 0 else "inconclusive")
    return [{"constant": "T_OIL", "values": [90.0, base, 110.0], "result": "R-MATURE: HC rate near a kitchen minus far [diff, p05, p95]", **r,
             "matters": len({verd(r["low"]), verd(r["base"]), verd(r["high"])}) > 1}]


def trap_floor() -> list:
    from se.earth import targets as T

    C = pd.read_parquet(EARTH / "targets" / "cells.parquet"); C["mid"] = 0.5 * (C.top + C.base); P = {t: np.load(EARTH / "targets" / f"{t}.npz")["p"] for t in ("reservoir", "overpressure")}
    K = T.co2_terms(C); g = {}
    for lab, v in (("low", 0.05), ("base", T.TRAP_FLOOR), ("high", 0.4)):
        T.TRAP_FLOOR = v; cs, _ = T.cos(C, P, K, C.zsd.to_numpy()); g[lab] = T.cos_test(C, cs).get("gain_cos")
    T.TRAP_FLOOR = 0.2
    return [{"constant": "TRAP_FLOOR", "values": [0.05, 0.2, 0.4], "result": "chance of success, held-out gain vs hydrocarbons", **g,
             "matters": bool(any(x is not None and x > 0.02 for x in g.values()))}]


def capacity() -> list:
    from se.earth import volumes as V

    C = pd.read_parquet(EARTH / "targets" / "cells.parquet"); phi, sd = V.porosity(C); area, rho, w = V.inputs(C); out = []
    p50 = lambda **kw: round(float(np.percentile(V.realise(C, phi, sd, rho, w, area, n=60, **kw)[0].sum(1), 50)))
    base = p50()
    for name, kw_lo, kw_hi, vals in (("NTG_SD", {"ntg_sd": 0.05}, {"ntg_sd": 0.2}, [0.05, V.NTG_SD, 0.2]), ("thickness sigma / top sigma", {"th_frac": 0.25}, {"th_frac": 1.0}, [0.25, 0.5, 1.0]),
                                     ("storage efficiency P50", {"eff": (0.0025, 0.01, 0.027)}, {"eff": (0.01, 0.04, 0.108)}, ["1 %", "2 %", "4 %"])):
        lo, hi = p50(**kw_lo), p50(**kw_hi)
        out.append({"constant": name, "values": vals, "result": "region CO2 capacity P50 (Mt)", "low": lo, "base": base, "high": hi,
                    "matters": bool(max(abs(lo - base), abs(hi - base)) > 0.25 * base)})
    return out


def support_constants() -> list:
    from scipy.stats import spearmanr

    from se.earth import targets as T

    t = "hydrocarbons"; o = T.observations(t).reset_index(drop=True); C = pd.read_parquet(EARTH / "targets" / "cells.parquet")
    C = C.sample(min(len(C), 30000), random_state=0); F = T.nb_features(o, C); sk = 0.3
    def sup(n0=3.0, d0=30.0, sc=0.1):
        data = 1 - np.exp(-np.nan_to_num(F.n_nb.to_numpy()) / n0); near = np.exp(-np.nan_to_num(F.d_km.to_numpy(), nan=999.0, posinf=999.0) / d0)
        return np.clip(data * near * float(np.clip(sk / sc, 0.2, 1.0)), 0, 1)
    b = sup(); out = []
    for name, kws, vals in (("support n0 (observations)", ({"n0": 1.5}, {"n0": 6.0}), [1.5, 3.0, 6.0]), ("support d0 (km)", ({"d0": 15.0}, {"d0": 60.0}), [15, 30, 60])):
        r = {"base": round(float((b >= 0.5).mean()), 3)}
        for lab, kw in zip(("low", "high"), kws):
            s = sup(**kw); r[lab] = round(float((s >= 0.5).mean()), 3); r[lab + "_rank_corr"] = round(float(spearmanr(b, s)[0]), 3)
        out.append({"constant": name, "values": vals, "result": "share of cells with support >= 0.5 (hydrocarbons); rank correlation with the base", **r,
                    "matters": bool(min(r["low_rank_corr"], r["high_rank_corr"]) < 0.9)})
    return out


def build() -> dict:
    t0 = time.time(); rep = json.loads((EARTH / "targets" / "report.json").read_text()); rows = []
    for f in (model_constants, selection_margin, oil_window, trap_floor, capacity, support_constants):
        try:
            rows += f(rep) if f is model_constants else f()
        except Exception as e:  # a failing study is reported, not hidden
            rows.append({"constant": f.__name__, "error": f"{type(e).__name__}: {e}"[:300]})
    out = {"rows": rows, "matters": [r["constant"] + " -> " + r["result"] for r in rows if r.get("matters")], "seconds": round(time.time() - t0)}
    atomic.write_json(EARTH / "sensitivity.json", out, default=float)
    return out


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=float)[:4000])
