"""Nature's Plug (Jeham, MIT, commit 3df7c52) inside the earth model (PLAN P13, LOG L090).

A  Green Clay surface: his relation, Green Clay top = Rogaland top - clip(194 + 0.14 x Hordaland thickness, 141, 430) m, applied to our
   kriged Hordaland and Rogaland group tops in every column of every region. Tested at his 29 report sites (89 wellbores whose reports give
   a TVD for the Green Clay top): our surface vs the report depth, beside his own prediction (nearest vertical exploration well's tops).
   Caveats: his coefficients were fitted on these sites, so neither number is held out here; the report TVDs are below the rig floor
   (datum not always stated) and our surfaces are below sea level, so about 25-30 m of bias is datum, not geology.
B  Formation-level clay window: his engine's verdict per exploration well (Hordaland/Rogaland inside the leak-off pressure window),
   counted by region.
C  Barrier cases: his 15 hand-read report cases (used, held, failed, planned) with what our model's Green Clay surface says there.
D  Nearest-well inheritance: his verdict for each wellbore left to plug (nearest assessed log well within 10 km), counted by region; a
   comparison, not a decision (our Smeaheia screen judges exact boreholes only).
"""
import json

import numpy as np

from se.config import DATA, OUT, REGIONS
from se.earth import atomic

NP = DATA / "natures_plug"
A0, A1, TMIN, TMAX = 194.0, 0.14, 141.0, 430.0


def region_of(lat, lon):
    for r, b in REGIONS.items():
        if b["lat"][0] <= lat <= b["lat"][1] and b["lon"][0] <= lon <= b["lon"][1]:
            return r
    return None


def gc_surface(region):
    """(top TVDSS, thickness) of the Green Clay per lattice column from our Hordaland and Rogaland tops; NaN off the shelf or where absent."""
    E = OUT / "earth" / region; s = np.load(E / "surfaces.npz"); names = list(s["names"])
    if "HORDALAND GP" not in names or "ROGALAND GP" not in names:
        return None
    ho, ro = s["mean"][names.index("HORDALAND GP")].astype(float), s["mean"][names.index("ROGALAND GP")].astype(float)
    inside = s["inside"] & np.load(E / "grid.npz")["inside"] if (E / "grid.npz").exists() else s["inside"]
    T = np.clip(A0 + A1 * (ro - ho), TMIN, TMAX); top = ro - T
    return np.where(inside, top, np.nan), np.where(inside, T, np.nan), s["x"], s["y"]


def build() -> dict:
    from se.evidence.spatial import project

    gc = json.loads((NP / "greenclay.json").read_text()); eng = json.loads((NP / "engine_results.json").read_text())
    bar = json.loads((NP / "barrier.json").read_text())["cases"]; out = {"source": eng["source"], "relation": f"top = Rogaland top - clip({A0:g} + {A1:g} x Hordaland thickness, {TMIN:g}, {TMAX:g}) m", "regions": {}}
    surf = {r: gc_surface(r) for r in REGIONS if (OUT / "earth" / r / "surfaces.npz").exists()}
    def at(r, lat, lon):
        if not surf.get(r):
            return None
        top, T, x, y = surf[r]; p = project([lon], [lat])[0]; i = int(np.abs(x - p[0]).argmin()); j = int(np.abs(y - p[1]).argmin())
        return None if not np.isfinite(top[j, i]) else (float(top[j, i]), float(T[j, i]))
    sites = []
    for s in gc["sites"]:
        r = region_of(s["la"], s["lo"]); v = at(r, s["la"], s["lo"]) if r else None
        sites.append({"field": s["field"], "lat": s["la"], "lon": s["lo"], "region": r, "report_tvd_m": s["tvd"], "his_pred_m": s.get("pred"), "his_err_m": s.get("err"),
                      "our_top_tvdss_m": round(v[0], 1) if v else None, "our_err_m": round(v[0] - s["tvd"], 1) if v else None, "quote": s.get("text", "")[:160], "file": s.get("file"), "page": s.get("page")})
    ok = [x for x in sites if x["our_err_m"] is not None and x["his_err_m"] is not None]
    mae = lambda k: round(float(np.mean([abs(x[k]) for x in ok])), 1) if ok else None
    out["green_clay_test"] = {"sites": len(sites), "compared": len(ok), "mean_abs_miss_ours_m": mae("our_err_m"), "mean_abs_miss_his_m": mae("his_err_m"),
                              "median_signed_miss_ours_m": round(float(np.median([x["our_err_m"] for x in ok])), 1) if ok else None,
                              "his_field_held_out_m": 55, "note": "both use coefficients fitted on these sites (not held out); report TVDs are below the rig floor, our surfaces below sea level (about 25-30 m datum offset)"}
    out["green_clay_sites"] = sites
    for r in REGIONS:
        R = {}
        if surf.get(r):
            top, T, x, y = surf[r]; m = np.isfinite(top)
            R["green_clay"] = {"columns": int(m.sum()), "top_median_m": round(float(np.nanmedian(top)), 0) if m.any() else None, "thickness_median_m": round(float(np.nanmedian(T)), 0) if m.any() else None}
            atomic.savez(OUT / "earth" / r / "green_clay.npz", top=np.nan_to_num(top, nan=-1).astype(np.float32), thick=np.nan_to_num(T, nan=-1).astype(np.float32), x=x, y=y)
        l1 = [w for w in eng["layer1"] if region_of(w["lat"], w["lon"]) == r]
        R["formation_level"] = {"exploration_wells": len(l1), **{v: sum(1 for w in l1 if w["verdict"] == v) for v in ("present", "thin", "absent", "none")}}
        wb = [w for w in eng["wellbores_left_to_plug"] if region_of(w["lat"], w["lon"]) == r]
        R["inheritance"] = {"wellbores_left_to_plug": len(wb), **{f"log_{v}": sum(1 for w in wb if w["log"] == v) for v in ("pass", "fail", "none")}}
        out["regions"][r] = R
    out["barrier_cases"] = []
    for c in bar:
        la, lo = c.get("la"), c.get("lo"); r = region_of(la, lo) if la is not None else None; v = at(r, la, lo) if r else None
        out["barrier_cases"].append({"well": c["w"], "area": c.get("area"), "unit": c.get("unit"), "outcome": c.get("outcome"), "how": c.get("how"), "summary": c.get("summary"),
                                     "src": c.get("src"), "his_log": c.get("log"), "his_formation": c.get("fm"), "region": r, "our_green_clay_top_tvdss_m": round(v[0]) if v else None})
    out["engine_totals"] = eng["totals"]; out["agree"] = eng["agree"]
    atomic.write_json(OUT / "earth" / "jeham.json", out, default=float)
    return {k: out[k] for k in ("green_clay_test", "engine_totals")} | {"regions": out["regions"]}


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=float))
