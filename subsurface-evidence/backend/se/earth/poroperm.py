"""Porosity and permeability per formation from core plugs (PLAN P3.2, LOG L064).

Truth: RealPore core plugs (porosity %, permeability mD) in pilot wells, MD -> TVDSS by the frame, unit by the Sodir tops.
Plugs in one well and unit are correlated: they are averaged to one value per well and unit (log10 for permeability), weighted by count.
Candidates, scored on held-out 40 km blocks of wells:
  formation  the unit's mean
  athy       compaction only: phi = phi0 exp(-c z), z below the seabed, one curve for all units (Athy 1930; compared with Sclater and
             Christie 1980: sandstone phi0 49 percent, c 0.27 per km)
  unit_athy  the unit's offset on the Athy curve (shrunk to zero for units with few wells) + neighbours' residuals (Gaussian weights)
Permeability: log10 k from porosity per unit (a + b phi) + the same neighbour residual.
P9.2 trend candidates (each with the unit offsets and neighbours of unit_athy; adopted only if 2 percent better on held-out blocks):
  qtz        quartz cement: phi = phi0 exp(-c z) - q (T - 70 C)+ / 10 (Walderhaug 1996: quartz cement grows above about 70-80 C)
  burial     effective burial z + E: E per well is the extra depth that puts its porosity on the normal (pilot) compaction curve,
             mapped between wells (Gaussian ELL_E km, shrunk to 0); uplifted basins (Barents) were buried deeper than today
  burial_qtz both, with the temperature at maximum burial T + g E
"""
import json

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.model_selection import GroupKFold

from se.config import DATA, EARTH
from se.earth import manifest
from se.earth.folds import blocks
from se.earth.frame import Frame
from se.ingest.names import norm

SC80 = {"sandstone": (49.0, 0.27), "shale": (63.0, 0.51)}  # Sclater and Christie (1980), porosity percent and per km
ELL_KM, SHRINK = 15.0, 5.0
REF = (38.5, 0.295)  # normal compaction: the pilot fit of L064 (Horda Platform, little uplift)
ELL_E, K_E, T_Q = 60.0, 3.0, 70.0
TRENDS = ("athy", "qtz", "burial", "burial_qtz")


def plugs() -> pd.DataFrame:
    from se.earth.pressure import _interval, unit_at

    r = pd.read_parquet(DATA / "official/realpore/realpore.parquet", columns=["wellbore", "md", "porosity", "perm"])
    r["wellbore"] = r.wellbore.map(norm)
    w = pd.read_parquet(EARTH / "wells.parquet"); w = w[w.pilot].set_index("wellbore")
    r = r[r.wellbore.isin(w.index) & r.md.notna() & (r.md > 0)]
    fr = Frame(json.loads((EARTH / "frame_calibration.json").read_text())); iv = _interval(pd.read_parquet(EARTH / "tops.parquet"))
    out = []
    for wb, g in r.groupby("wellbore"):
        a = fr.at(wb, g.md.to_numpy())
        g = g.assign(tvdss=np.asarray(a["tvdss"], float), x=float(w.x[wb]), y=float(w.y[wb]), wd=float(w.wd[wb]))
        g["unit"] = [unit_at(iv, wb, m)[0] for m in g.md]
        out.append(g)
    p = pd.concat(out)
    p["zb"] = p.tvdss - p.wd
    return p[p.unit.notna() & (p.zb > 0)]


def per_well_unit(p: pd.DataFrame) -> pd.DataFrame:
    q = p.assign(lk=np.log10(p.perm.clip(lower=0.001)))
    g = q.groupby(["wellbore", "unit"])
    t = pd.DataFrame({"phi": g.porosity.mean(), "lk": g.lk.mean(), "n_phi": g.porosity.count(), "n_k": g.perm.count(),
                      "zb": g.zb.mean(), "x": g.x.first(), "y": g.y.first(), "wd": g.wd.first()}).reset_index().dropna(subset=["phi"])
    from se.earth.temperature import predict

    t["T"] = predict(t.x.to_numpy(), t.y.to_numpy(), t.zb.to_numpy(), t.wd.to_numpy())[0]
    t["E_own"] = -1000 / REF[1] * np.log(np.clip(t.phi, 1.0, None) / REF[0]) - t.zb  # extra burial that puts this porosity on REF
    return t


def burial_map(tr: pd.DataFrame, x, y, exclude=None) -> np.ndarray:
    """Net exhumation E (m) at points from training wells (one value per well: median of its well-units), shrunk to 0 far from wells."""
    w = tr.groupby("wellbore").agg(E=("E_own", "median"), x=("x", "first"), y=("y", "first"), n=("E_own", "size"))
    X = np.c_[np.ravel(x), np.ravel(y)]; d2 = ((X[:, None] - w[["x", "y"]].to_numpy()[None]) ** 2).sum(-1)
    k = np.exp(-0.5 * d2 / ELL_E ** 2) * np.sqrt(w.n.to_numpy())[None]
    if exclude is not None:  # a training row's own well is left out of its own E
        k = k * (np.asarray(exclude)[:, None] != w.index.to_numpy()[None])
    return (k @ w.E.to_numpy()) / (k.sum(1) + K_E)


def gradient() -> float:
    return json.loads((EARTH / "temperature_report.json").read_text())["gradient_C_per_km"] / 1000


def athy(z, phi0, c):
    return phi0 * np.exp(-c * z / 1000.0)


class Model:
    def __init__(self, trend="athy"):
        self.trend = trend

    def _drivers(self, zb, T, E):
        b = "burial" in self.trend; z = zb + (E if b else 0.0)
        q = np.maximum(0.0, (T + (self.g * E if b else 0.0)) - T_Q) / 10 if "qtz" in self.trend else np.zeros(len(zb))
        return np.vstack([z, q])

    def curve(self, zb, T=None, E=None):
        zb = np.asarray(zb, float); T = np.zeros(len(zb)) if T is None else np.asarray(T, float); E = np.zeros(len(zb)) if E is None else np.asarray(E, float)
        D = self._drivers(zb, T, E); return athy(D[0], self.p0, self.c) - self.q * D[1]

    def fit(self, t: pd.DataFrame):
        self.g = gradient() if self.trend != "athy" else 0.0
        self.tr = t; E = burial_map(t, t.x, t.y, exclude=t.wellbore.to_numpy()) if "burial" in self.trend else np.zeros(len(t))
        D = self._drivers(t.zb.to_numpy(), t["T"].to_numpy(), E)
        if "qtz" in self.trend:
            f = lambda d, p0, c, q: athy(d[0], p0, c) - q * d[1]
            self.p0, self.c, self.q = curve_fit(f, D, t.phi, p0=(40.0, 0.3, 0.5), sigma=1 / np.sqrt(t.n_phi), maxfev=20000)[0]
        else:
            self.p0, self.c = curve_fit(athy, D[0], t.phi, p0=(40.0, 0.3), sigma=1 / np.sqrt(t.n_phi), maxfev=20000)[0]; self.q = 0.0
        r = t.phi - (athy(D[0], self.p0, self.c) - self.q * D[1])
        g = t.assign(r=r).groupby("unit")
        self.off = (g.r.sum() / (g.r.count() + SHRINK)).to_dict()  # shrunk unit offsets
        self.mean = t.groupby("unit").phi.mean().to_dict(); self.gmean = float(t.phi.mean())
        t = t.assign(res=r - t.unit.map(self.off).fillna(0))
        self.t = t
        k = t.dropna(subset=["lk"])
        self.kb = {}
        for u, gk in k.groupby("unit"):  # log10 k = a + b phi per unit; global fit for units with few wells
            if len(gk) >= 8:
                self.kb[u] = np.polyfit(gk.phi, gk.lk, 1)
        self.kg = np.polyfit(k.phi, k.lk, 1)
        kk = k.assign(kres=k.lk - [np.polyval(self.kb.get(u, self.kg), f) for u, f in zip(k.unit, k.phi)])
        self.tk = kk
        return self

    def _nb(self, X, unit, col, tab):
        t = tab[tab.unit == unit]
        if not len(t):
            return np.zeros(len(X))
        d2 = ((X[:, None, :] - t[["x", "y"]].to_numpy()[None]) ** 2).sum(-1)
        w = np.exp(-0.5 * d2 / ELL_KM ** 2) * np.sqrt(t.n_phi.to_numpy())[None]
        return (w @ t[col].to_numpy()) / (w.sum(1) + 3.0)  # +3: shrink to zero far from wells

    def trend_at(self, X, zb, T):
        E = burial_map(self.tr, X[:, 0], X[:, 1]) if "burial" in self.trend else None
        return self.curve(zb, T, E)

    def predict(self, X, zb, unit, kind="unit_athy", T=None):
        X = np.atleast_2d(X); zb = np.asarray(zb, float)
        if kind == "formation":
            phi = np.full(len(zb), self.mean.get(unit, self.gmean))
        elif kind == "athy":
            phi = self.trend_at(X, zb, T)
        else:
            phi = self.trend_at(X, zb, T) + self.off.get(unit, 0.0) + self._nb(X, unit, "res", self.t)
        phi = np.clip(phi, 0.0, 45.0)
        lk = np.polyval(self.kb.get(unit, self.kg), phi) + (self._nb(X, unit, "kres", self.tk) if kind == "unit_athy" else 0.0)
        return phi, lk


def trend(x, y, zb, wd, exclude=None) -> np.ndarray:
    """Porosity (percent) of the adopted compaction trend at points, no unit offset (feature for the reservoir target).
    exclude: wellbores left out of the fit (P12.2)."""
    r = json.loads((EARTH / "poroperm_report.json").read_text()); a = r.get("adopted_trend", "athy")
    if a == "athy" and not exclude:
        return athy(np.asarray(zb, float), r["athy_fit"]["phi0_pct"], r["athy_fit"]["c_per_km"])
    from se.earth.temperature import predict

    t = pd.read_parquet(EARTH / "poroperm_wells.parquet"); t = t[~t.wellbore.isin(exclude)] if exclude else t
    m = Model(a).fit(t); T = predict(x, y, zb, wd, exclude=exclude)[0]
    return m.trend_at(np.c_[np.ravel(x), np.ravel(y)], np.ravel(zb), np.ravel(T))


def build() -> dict:
    p = plugs(); t = per_well_unit(p)
    bl = blocks(t.x, t.y)
    err = {k: [] for k in ("formation", "athy", "unit_athy", *[f"unit_{tr_}" for tr_ in TRENDS[1:]])}; kerr = {k: [] for k in err}; wts, kw, zs = [], [], []
    for tr, te in GroupKFold(5).split(t, groups=bl):
        ms = {tr_: Model(tr_).fit(t.iloc[tr]) for tr_ in TRENDS}; b = t.iloc[te]
        for kind in err:
            m, kd = (ms[kind[5:]], "unit_athy") if kind.startswith("unit_") and kind != "unit_athy" else (ms["athy"], kind)
            for u, g in b.groupby("unit"):
                phi, lk = m.predict(g[["x", "y"]].to_numpy(), g.zb.to_numpy(), u, kd, g["T"].to_numpy())
                err[kind] += list(phi - g.phi); kerr[kind] += list(np.where(g.lk.notna(), lk - g.lk, np.nan))
                if kind == "formation":
                    wts += list(g.n_phi); kw += list(g.n_k)
    wts, kw = np.array(wts, float), np.array(kw, float)
    w = np.sqrt(wts)  # weight a well-unit by sqrt(plugs): more plugs, better mean, but still one well
    rm = lambda e, ww: round(float(np.sqrt(np.nansum(ww * np.square(e)) / np.nansum(ww * np.isfinite(e)))), 2)
    r_phi = {k: rm(v, w) for k, v in err.items()}
    best = min(TRENDS[1:], key=lambda k: r_phi[f"unit_{k}"]); adopted = best if r_phi[f"unit_{best}"] <= 0.98 * r_phi["unit_athy"] else "athy"
    key = "unit_athy" if adopted == "athy" else f"unit_{adopted}"
    m = Model().fit(t); ma = Model(adopted).fit(t) if adopted != "athy" else m
    sd_phi = rm(err[key], w); sd_lk = rm(kerr[key], np.sqrt(kw))
    Ew = t.groupby("wellbore").E_own.median()
    out = {"plugs": int(len(p)), "wells": int(p.wellbore.nunique()), "well_units": int(len(t)), "units": int(t.unit.nunique()),
           "athy_fit": {"phi0_pct": round(float(m.p0), 1), "c_per_km": round(float(m.c), 3)}, "sclater_christie_1980": SC80,
           "rmse_phi_pct": r_phi, "rmse_log10k": {k: rm(v, np.sqrt(kw)) for k, v in kerr.items()},
           "sigma_phi_pct": sd_phi, "sigma_log10k": sd_lk, "adopted_trend": adopted,
           "adopted_fit": {"phi0_pct": round(float(ma.p0), 1), "c_per_km": round(float(ma.c), 3), "q_pct_per_10C": round(float(ma.q), 3)},
           "burial": {"reference": {"phi0_pct": REF[0], "c_per_km": REF[1], "from": "pilot fit, L064"}, "wells": int(len(Ew)),
                      "E_median_m": round(float(Ew.median())), "E_p10_m": round(float(Ew.quantile(0.1))), "E_p90_m": round(float(Ew.quantile(0.9))),
                      "ell_km": ELL_E, "k": K_E},
           "fits": {k: (lambda f: {"phi0_pct": round(float(f.p0), 1), "c_per_km": round(float(f.c), 3), "q_pct_per_10C": round(float(f.q), 3)})(Model(k).fit(t)) for k in TRENDS},
           "quartz": {"T_onset_C": T_Q, "share_of_well_units_above_onset": round(float((t["T"] > T_Q).mean()), 3)}}
    t.to_parquet(EARTH / "poroperm_wells.parquet")
    (EARTH / "poroperm_report.json").write_text(json.dumps(out, indent=1))
    manifest.write(EARTH / "poroperm_wells.parquet", [DATA / "official/realpore/realpore.parquet", EARTH / "tops.parquet"], {"ell_km": ELL_KM, "shrink": SHRINK})
    return out


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
