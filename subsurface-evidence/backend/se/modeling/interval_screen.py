"""Co-located rock and pressure scenario on one reported Sognefjord borehole."""
from itertools import pairwise

import duckdb
import numpy as np
import pandas as pd


def sources(db_path, csv_path, names):
    with duckdb.connect(str(db_path), read_only=True) as db:
        mud = db.execute("""SELECT wlbName wellbore, wlbNpdidWellbore npdid, wlbMD md, wlbMudWeightAtMD density
            FROM wellbore_mud WHERE wlbName IN $1 ORDER BY npdid, md, density""", [sorted(names)]).df()
        tests = db.execute("""SELECT wlbName wellbore, wlbNpdidWellbore npdid, wlbCasingDepth md,
            wlbFormationTestType kind, wlbLotMudDencity density FROM wellbore_casing_and_lot
            WHERE wlbName IN $1 ORDER BY npdid, md, kind, density""", [sorted(names)]).df()
    chunks = pd.read_csv(csv_path, sep=";", usecols=["WELL", "DEPTH_MD", "GR", "RDEP", "DTC"], chunksize=100_000)
    with chunks:
        logs = pd.concat([c[c.WELL.isin(names)] for c in chunks])
    return mud, tests, logs


def _mud_at(rows, top):
    rows = rows[np.isfinite(rows.md) & rows.md.gt(0) & np.isfinite(rows.density) & rows.density.gt(0.9)]
    lower, upper = rows.md[rows.md <= top].max(), rows.md[rows.md >= top].min()
    endpoints = rows[rows.md.isin([lower, upper])][["md", "density"]].drop_duplicates().sort_values(["md", "density"])
    if not np.isfinite([lower, upper]).all() or endpoints.md.duplicated().any():
        return None, endpoints.to_dict("records")
    return float(np.interp(top, endpoints.md, endpoints.density)), endpoints.to_dict("records")


def _tvd(path, depths, kb, water):
    """Stay inside a sampled segment and below seabed. No silent MD = TVD."""
    m = path.md.to_numpy()
    z = np.full(len(depths), np.nan)
    if not len(m) or kb is None or water is None:
        return z
    for ix in np.split(np.arange(len(m)), np.flatnonzero(np.diff(m) > 2) + 1):
        inside = (depths >= m[ix[0]]) & (depths <= m[ix[-1]])
        z[inside] = np.interp(depths[inside], m[ix], path.tvdss.to_numpy()[ix]) + kb
    return np.where((z >= water + kb) & (z > 0) & (z <= depths + 1), z, np.nan)


def _logs_at(rows, centres, tol):
    # Keep the closest original row, not the closest row that happens to pass.
    q = rows[np.isfinite(rows.DEPTH_MD)].copy()
    q["bin"] = np.floor(q.DEPTH_MD).astype(int)
    q["offset"] = abs(q.DEPTH_MD - (q.bin + 0.5))
    duplicate = q.DEPTH_MD.duplicated(keep=False)
    q.loc[duplicate, ["GR", "RDEP", "DTC"]] = np.nan
    q = q[q.offset <= tol].sort_values(["offset", "DEPTH_MD"]).drop_duplicates("bin")
    return q.set_index("bin").reindex(centres.astype(int))


def _runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist(), strict=True))


def _result(known, joint, p):
    runs = _runs(joint)
    best = max(runs, key=lambda span: span[1] - span[0], default=None)
    longest = best[1] - best[0] if best else 0
    support = max((b - a for a, b in _runs(known)), default=0)
    state = ("candidate interval" if longest >= p["continuous_m"] else
             "not seen on supported metres" if support >= p["continuous_m"] else "insufficient evidence")
    return {"state": state, "assessable_bins": int(known.sum()), "longest_assessable_m": support,
            "joint_bins": int(joint.sum()), "longest_joint_m": longest if known.any() else None,
            "longest_bounds_md_m": list(best) if best is not None else None,
            "intervals_md_m": [[a, b] for a, b in runs if b-a >= p["continuous_m"]],
            "reaches_longer_run": longest >= p["longer_run_m"] if known.any() else None}


def _pressure(md, z, pairs, reservoir_z, pp, gas):
    avail = np.full(len(md), np.nan)
    for left, right in pairs:
        lo, hi = left["tvd_rkb_m"], right["tvd_rkb_m"]
        inside = (md >= left["md"]) & (md <= right["md"]) & (z >= lo) & (z <= hi)
        avail[inside] = np.interp(z[inside], [lo, hi], [left["emw"], right["emw"]])
    required = gas + (pp - gas) * reservoir_z / z
    return avail, required


def assess(well, path, tops, mud, tests, logs, rule):
    name, id_ = well["wellbore"], well["npdid"]
    def exact(df):
        return df[df.wellbore.eq(name) & df.npdid.eq(id_)]

    p = rule["parameters"]
    marker = next(m for m in well["markers"] if m["unit_id"] == 151)
    picks = marker["picks"]
    top = picks[0]["top_md_m"] if len(picks) == 1 and not marker["excluded_rows"] else None
    kb, water = well["rkb_m"], well["water_m"]
    raw = logs[logs.WELL.eq(name)]
    centres = np.arange(int(np.floor(top)) if top is not None else 0) + 0.5
    sample = _logs_at(raw, centres, p["log_tolerance_m"])
    md, gr, rd, dt = (sample[k].to_numpy(dtype=float) for k in ("DEPTH_MD", "GR", "RDEP", "DTC"))
    mandatory = np.isfinite(gr) & (gr >= 0) & np.isfinite(rd) & (rd > 0)
    measured = mandatory & np.isfinite(dt) & (dt > 0)
    # Only a genuinely missing sonic may bypass that gate in the sensitivity run.
    basic = mandatory & (gr > p["gamma_min_api"]) & (rd < p["resistivity_max_ohm_m"])
    rock = basic & measured & (dt > p["sonic_min_us_ft"])
    optional = rock | (basic & np.isnan(dt))

    top_z = _tvd(path, np.array([top if top is not None else np.nan]), kb, water)[0]
    mw, endpoints = _mud_at(exact(mud), top) if top is not None else (None, [])
    shoe_rows = exact(tests)
    shoe_rows = shoe_rows[np.isfinite(shoe_rows.md) & shoe_rows.md.gt(0) & shoe_rows.md.lt(top or 0)
                          & np.isfinite(shoe_rows.density) & shoe_rows.density.gt(1)]
    shoes = []
    for depth, rows in shoe_rows[shoe_rows.kind.eq("LOT")].groupby("md", sort=True):
        densities = sorted(rows.density.unique().tolist())
        z = _tvd(path, np.array([depth]), kb, water)[0]
        shoes.append({"md": float(depth), "tvd_rkb_m": float(z) if np.isfinite(z) else None,
                      "reported_emw": densities, "emw": densities[0] if len(densities) == 1 else None})
    pp = max(p["pressure_floor_g_cm3"], mw - p["overbalance_g_cm3"]) if mw is not None else None
    pairs = [(a, b) for a, b in pairwise(shoes) if a["tvd_rkb_m"] is not None and b["tvd_rkb_m"] is not None
             and a["emw"] is not None and b["emw"] is not None and a["tvd_rkb_m"] < b["tvd_rkb_m"]]
    gas = p["gas_g_cm3"]
    z = _tvd(path, md, kb, water)
    def demand(depth, tvd, pressure):
        avail, req = _pressure(depth, tvd, pairs, top_z, np.nan if pressure is None else pressure, gas)
        known = np.isfinite(avail) & np.isfinite(req) & (tvd < top_z)
        return known, known & (avail >= req), avail, req
    known, window, avail, req = demand(md, z, pp)
    _, no_offset, _, _ = demand(md, z, max(p["pressure_floor_g_cm3"], mw) if mw is not None else None)
    strict = _result(known & measured, window & rock, p)
    example = None
    if strict["longest_bounds_md_m"]:
        i = sum(strict["longest_bounds_md_m"]) // 2
        example = {"md": float(md[i]), "tvd_rkb_m": float(z[i]), "gr_api": float(gr[i]), "rdep_ohm_m": float(rd[i]),
                   "dtc_us_ft": float(dt[i]), "available_emw": float(avail[i]), "required_emw": float(req[i])}
    missing = []
    if top is None:
        missing.append("No unique valid Sognefjord interval.")
    if not np.isfinite(top_z):
        missing.append("No supported reservoir TVD below rig floor.")
    if mw is None:
        missing.append("No unambiguous mud-weight bracket at the reservoir.")
    if not pairs:
        missing.append("Need two positioned LOT shoes above the reservoir; no pressure extrapolation.")
    if not measured.any():
        missing.append("No co-measured GR, deep resistivity and sonic above a known target in this source.")
    if not missing and strict["state"] == "insufficient evidence":
        missing.append("Jointly assessable coverage is too short or discontinuous.")

    # Group overlap is a separate screen; it needs the pressure scenario but no rock logs.
    ck, cw, _, _ = demand(centres, _tvd(path, centres, kb, water), pp)
    g = exact(tops)
    g = g[g.level.eq("GROUP") & g.unit.map(rule["groups"]).eq(g.unit_id) & g.top_md.gt(0)
          & g.base_md.gt(g.top_md) & np.isfinite(g.base_md)]
    group = np.zeros(len(centres), dtype=bool)
    for r in g.itertuples():
        group |= (centres - 0.5 >= r.top_md) & (centres + 0.5 <= r.base_md)
    total = int((cw & group).sum()) if (ck & group).any() else None

    return {"rule_id": rule["id"], "target_md_m": top, "target_tvd_rkb_m": float(top_z) if np.isfinite(top_z) else None,
            "rock_log_bins": int(measured.sum()), "rock_signature_bins": int(rock.sum()),
            "mud_bracket": endpoints, "mud_at_target_g_cm3": mw, "assumed_pp_g_cm3": pp,
            "lot_shoes_above": shoes, "unused_other_tests_above": int((~shoe_rows.kind.eq("LOT").fillna(False)).sum()),
            "pressure_supported_log_bins": int(known.sum()), "pressure_window_log_bins": int(window.sum()),
            "strict": strict, "example_in_longest": example, "missing": missing,
            "optional_sonic": _result(known & (measured | (mandatory & np.isnan(dt))), window & optional, p),
            "zero_overbalance": _result(known & measured, no_offset & rock, p),
            "group_screen": {"rows": g[["unit", "unit_id", "top_md", "base_md"]].sort_values(["top_md", "unit"]).to_dict("records"),
                             "supported_m": int((ck & group).sum()), "in_window_m": total,
                             "meets_total": total >= p["group_total_m"] if total is not None else None}}
