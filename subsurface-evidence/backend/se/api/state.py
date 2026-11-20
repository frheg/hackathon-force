"""Model state: units, fitted layers, validation results, knowledge checks. Built once at start, read by the API and the worker."""
import json
import time

import pandas as pd

from se.config import OUT, device
from se.evidence import REGISTRY
from se.infer.combine import ORDER, Platt, contributions, fit_layers
from se.knowledge import kb
from se.targets import store
from se.validate.cv import load, without_logs

STATUS_TEXT = {"helps": "interval above 0", "no_evidence": "interval spans 0", "hurts": "interval below 0", "not_built": "no code yet"}


def status_of(d: dict | None) -> str:
    if not d:
        return "not_built"
    return "helps" if d["p05"] > 0 else "hurts" if d["p95"] < 0 else "no_evidence"


def default_layers(status: dict) -> list:
    return [n for n in ORDER if status.get(n) == "helps"]


class State:
    def __init__(self, target: str = "green_clay"):
        t0 = time.time()
        self.target = target
        if target == "green_clay":  # built in: log layer and the sourced knowledge base exist only here
            d0, self.spec, self.units = OUT, store.GREEN, load()
        else:
            d0 = store.path(target)
            self.spec, self.units = json.loads((d0 / "spec.json").read_text()), without_logs(pd.read_parquet(d0 / "units.parquet"))
        self.words = store.words(self.spec)
        self.lab = self.units[self.units.label >= 0]
        self.layers = fit_layers(self.lab, n_boot=100 if target == "green_clay" else 0)
        for n in ("strat", "spatial"):
            self.layers[n].words = self.words  # the layers explain themselves in the target's own words
        self.results = json.loads((d0 / "results.json").read_text())
        self.oof = pd.read_parquet(d0 / "oof.parquet")
        self.kb = kb.check(self.units) if target == "green_clay" else []
        d = self.results["delta"]
        self.status = {"strat": status_of(d["strat_over_constant"]), "spatial": status_of(d["spatial_over_strat"]), "logs": status_of(d.get("logs_over_strat_on_logs_subset")), "seismic": "not_built"}
        # A layer is enabled only after evidence that it helps; callers can still override explicitly.
        self.default_on = default_layers(self.status)
        self._platt, self.loaded_seconds, self.device = {}, round(time.time() - t0, 1), device()

    def platt(self, use) -> Platt:
        """Calibrator for any subset of layers: fitted on the out-of-fold contributions of exactly those layers (no leakage into the final model)."""
        key = tuple(sorted(use))
        if key not in self._platt:
            o = self.oof
            x = o["base"] + sum(o[n].fillna(0.0) for n in key)
            self._platt[key] = Platt().fit(x, o.n_green, o.coverage)
        return self._platt[key]

    def rate(self, df: pd.DataFrame, use) -> pd.DataFrame:
        c = contributions(self.layers, df, tuple(use))
        c["rate"] = self.platt(use)(c["logit"].to_numpy())
        return c

    def layer_info(self) -> list:
        out = []
        for n, cls in REGISTRY.items():
            lay = self.layers.get(n)
            p = lay.params() if lay is not None else cls().params()
            if n == "logs" and "weights" in p:
                p = {**p, "note": "weights are on formation-relative z-scores; see Knowledge for sign checks"}
            key, vs, units = {"strat": ("strat_over_constant", "always guessing the overall rate", None), "spatial": ("spatial_over_strat", "the formation layer alone", None),
                              "logs": ("logs_over_strat_on_logs_subset", "the formation layer alone, on the units that have logs", int(self.results.get("ablation_logs_subset", {}).get("strat", {}).get("units", 0)) or None)}.get(n, (None, None, None))
            ev = dict(self.results["delta"][key], compared_with=vs, units=units) if key and self.results["delta"].get(key) else None
            out.append({"name": n, "title": cls.title, "doc": cls.doc, "status": self.status[n], "status_text": STATUS_TEXT[self.status[n]], "on_by_default": n in self.default_on, "params": p,
                        "built": getattr(cls, "implemented", True), "evidence": ev})
        return out

    def explain(self, row: pd.Series, use) -> dict:
        df = pd.DataFrame([row])
        c = self.rate(df, use).iloc[0]
        parts = [{"layer": "base", "llr": float(c["base"]), "speaks": True, "why": f"overall share of {self.words['rows']} that {self.words['hit']}: {self.layers['strat'].p0:.1%} (logit shown)"}]
        for n in ORDER:
            speaks = bool(c[n + "_speaks"]) and n in use
            parts.append({"layer": n, "llr": float(c[n]) if speaks else None, "speaks": speaks, "why": self.layers[n].why(row) if n in use else "switched off",
                          "status": self.status[n]})
        return {"rate": float(c["rate"]), "raw_rate": float(c["p"]), "logit": float(c["logit"]), "parts": parts}
