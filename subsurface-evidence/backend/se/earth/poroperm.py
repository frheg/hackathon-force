"""Porosity and permeability per formation from core plugs (PLAN P3.2, LOG L064).

Truth: RealPore core plugs (porosity %, permeability mD) in pilot wells, MD -> TVDSS by the frame, unit by the Sodir tops.
Plugs in one well and unit are correlated: they are averaged to one value per well and unit (log10 for permeability), weighted by count.
Candidates, scored on held-out 40 km blocks of wells:
  formation  the unit's mean
  athy       compaction only: phi = phi0 exp(-c z), z below the seabed, one curve for all units (Athy 1930; compared with Sclater and
             Christie 1980: sandstone phi0 49 percent, c 0.27 per km)
  unit_athy  the unit's offset on the Athy curve (shrunk to zero for units with few wells) + neighbours' residuals (Gaussian weights)
Permeability: log10 k from porosity per unit (a + b phi) + the same neighbour residual.
"""
import json

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.model_selection import GroupKFold

from se.config import DATA, EARTH
from se.earth import manifest
from se.earth.frame import Frame
from se.ingest.names import norm

SC80 = {"sandstone": (49.0, 0.27), "shale": (63.0, 0.51)}  # Sclater and Christie (1980), porosity percent and per km
ELL_KM, SHRINK = 15.0, 5.0


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
    return pd.DataFrame({"phi": g.porosity.mean(), "lk": g.lk.mean(), "n_phi": g.porosity.count(), "n_k": g.perm.count(),
                         "zb": g.zb.mean(), "x": g.x.first(), "y": g.y.first()}).reset_index().dropna(subset=["phi"])


def athy(z, phi0, c):
    return phi0 * np.exp(-c * z / 1000.0)


class Model:
    def fit(self, t: pd.DataFrame):
        self.p0, self.c = curve_fit(athy, t.zb, t.phi, p0=(40.0, 0.3), sigma=1 / np.sqrt(t.n_phi), maxfev=20000)[0]
        r = t.phi - athy(t.zb, self.p0, self.c)
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

    def predict(self, X, zb, unit, kind="unit_athy"):
        X = np.atleast_2d(X); zb = np.asarray(zb, float)
        if kind == "formation":
            phi = np.full(len(zb), self.mean.get(unit, self.gmean))
        elif kind == "athy":
            phi = athy(zb, self.p0, self.c)
        else:
            phi = athy(zb, self.p0, self.c) + self.off.get(unit, 0.0) + self._nb(X, unit, "res", self.t)
        phi = np.clip(phi, 0.0, 45.0)
        lk = np.polyval(self.kb.get(unit, self.kg), phi) + (self._nb(X, unit, "kres", self.tk) if kind == "unit_athy" else 0.0)
        return phi, lk


def build() -> dict:
    p = plugs(); t = per_well_unit(p)
    bl = (np.floor(t.x / 40).astype(int) * 100003 + np.floor(t.y / 40).astype(int)).to_numpy()
    err = {k: [] for k in ("formation", "athy", "unit_athy")}; kerr = {k: [] for k in err}; wts, kw, zs = [], [], []
    for tr, te in GroupKFold(5).split(t, groups=bl):
        m = Model().fit(t.iloc[tr]); b = t.iloc[te]
        for kind in err:
            for u, g in b.groupby("unit"):
                phi, lk = m.predict(g[["x", "y"]].to_numpy(), g.zb.to_numpy(), u, kind)
                err[kind] += list(phi - g.phi); kerr[kind] += list(np.where(g.lk.notna(), lk - g.lk, np.nan))
                if kind == "formation":
                    wts += list(g.n_phi); kw += list(g.n_k)
    wts, kw = np.array(wts, float), np.array(kw, float)
    w = np.sqrt(wts)  # weight a well-unit by sqrt(plugs): more plugs, better mean, but still one well
    rm = lambda e, ww: round(float(np.sqrt(np.nansum(ww * np.square(e)) / np.nansum(ww * np.isfinite(e)))), 2)
    m = Model().fit(t)
    sd_phi = rm(err["unit_athy"], w); sd_lk = rm(kerr["unit_athy"], np.sqrt(kw))
    out = {"plugs": int(len(p)), "wells": int(p.wellbore.nunique()), "well_units": int(len(t)), "units": int(t.unit.nunique()),
           "athy_fit": {"phi0_pct": round(float(m.p0), 1), "c_per_km": round(float(m.c), 3)}, "sclater_christie_1980": SC80,
           "rmse_phi_pct": {k: rm(v, w) for k, v in err.items()}, "rmse_log10k": {k: rm(v, np.sqrt(kw)) for k, v in kerr.items()},
           "sigma_phi_pct": sd_phi, "sigma_log10k": sd_lk}
    t.to_parquet(EARTH / "poroperm_wells.parquet")
    (EARTH / "poroperm_report.json").write_text(json.dumps(out, indent=1))
    manifest.write(EARTH / "poroperm_wells.parquet", [DATA / "official/realpore/realpore.parquet", EARTH / "tops.parquet"], {"ell_km": ELL_KM, "shrink": SHRINK})
    return out


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
