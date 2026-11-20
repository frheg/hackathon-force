"""Build a self-contained, content-addressed Smeaheia review receipt. Never activates an Earth build."""
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import duckdb
import numpy as np
import pandas as pd
import yaml
from pyproj import Transformer
from scipy.spatial import ConvexHull, Delaunay

from se.config import BACKEND, DATA, OUT
from se.earth import snapshot
from se.ingest.names import norm
from se.modeling import interval_screen, screen_validation
from se.modeling.artifacts import sha256

BUILD = "f46ffd5abca4"
SUPPORT = "velocity/smeaheia_support_v2.json"
SUPPORT_HASH = "4174d4e36b5e7a230d6f8f5b6d7126dfef4162f0dfd816a07567186e18b8a1f9"
RULE = BACKEND / "se/knowledge/rules/smeaheia_screen.yaml"
INTERVAL_RULE = RULE.with_name("smeaheia_interval.yaml")
STORE = Path("screen/smeaheia")
TO_FRAME = Transformer.from_crs(23031, 3035, always_xy=True)


def checked(path, expected):
    if sha256(path) != expected:
        raise ValueError(f"{path.name}: source digest mismatch")
    return path


def path_segments(path):
    """Keep gap boundaries before display thinning. No artificial link to the head."""
    segments = []
    for _, seg in path.groupby(path.md.diff().gt(2).cumsum()):
        subset = seg.iloc[np.unique(np.r_[np.arange(0, len(seg), 20), len(seg) - 1])]
        segments.append(subset[["x", "y", "tvdss", "md"]].round(5).values.tolist())
    return segments


def markers(rows, identity, rules, path):
    exact = rows[rows.npdid.eq(identity.npdid) & rows.wellbore.eq(identity.wellbore) & rows.level.eq("FORMATION")]
    results = []
    for rule in rules:
        picks = []
        strata = exact[exact.unit_id.eq(rule["unit_id"]) & exact.unit.eq(rule["name"])]
        for r in strata.sort_values("top_md").itertuples():
            if (pd.isna(r.top_md) or pd.isna(r.base_md) or not (0 < r.top_md < r.base_md)
                    or (pd.notna(identity.td) and identity.td > 0 and r.base_md > identity.td)):
                continue
            point = screen_validation.bracket(path, r.top_md)
            picks.append({"top_md_m": float(r.top_md), "base_md_m": float(r.base_md), "top_position": point})
        results.append({**rule, "state": "reported interval" if picks else "unknown", "picks": picks,
                        "excluded_rows": len(strata) - len(picks)})
    return results


def tables(path):
    fields = """wlbWellboreName wellbore, wlbNpdidWellbore npdid, trim(wlbWell) family, wlbStatus status,
                wlbFactPageUrl url, wlbKellyBushElevation kb, wlbWaterDepth wd, wlbTotalDepth td,
                wlbGeodeticDatum datum, wlbUtmZone zone, wlbEwUtm east, wlbNsUtm north, wlbCompletionYear AS completion_year"""
    with duckdb.connect(str(path), read_only=True) as db:
        reg = db.execute(f"SELECT {fields}, 'exploration' kind FROM wellbore_exploration UNION ALL "
                         f"SELECT {fields}, 'development' kind FROM wellbore_development ORDER BY npdid").df()
        tops = db.execute("""SELECT wlbName wellbore, wlbNpdidWellbore npdid, lsuName unit, lsuNpdidLithoStrat unit_id,
                             lsuLevel level, lsuTopDepth top_md, lsuBottomDepth base_md FROM wellbore_formation_top""").df()
        docs = db.execute("""SELECT wlbName wellbore, wlbNpdidWellbore npdid, wlbDocumentName name,
                             wlbDocumentType kind, wlbDocumentUrl url FROM wellbore_document
                             ORDER BY npdid, kind, name, url""").df()
    if reg.npdid.isna().any() or reg.npdid.duplicated().any():
        raise ValueError("ambiguous FactPages ID")
    reg["key"] = reg.wellbore.map(norm)
    return reg, tops, docs


def head(r):
    if r.datum != "ED50" or r.zone != 31 or not (0 < r.east < 1e6 and 0 < r.north < 1e7):
        raise ValueError(f"{r.wellbore}: unresolved ED50 UTM 31N position")
    return [v / 1000 for v in TO_FRAME.transform(r.east, r.north)]


def depth_test(reg, tops, paths, pilot_names, rules):
    eligible, exclusions = [], {}
    raw = tops[tops.unit.eq("SOGNEFJORD FM") & tops.level.eq("FORMATION") & tops.wellbore.map(norm).isin(pilot_names)]
    for (id_, name), picks in raw.groupby(["npdid", "wellbore"], sort=True):
        w = reg[reg.npdid.eq(id_) & reg.wellbore.eq(name)]
        reason = "unresolved identity"
        if len(w) == 1 and w.iloc[0].key not in reg.loc[reg.key.duplicated(False), "key"].values:
            r = w.iloc[0]
            reason = "no sampled FORCE path"
            if r.key in paths:
                marker = markers(picks, r, rules, paths[r.key])[0]
                reason = "nonunique/invalid top or no close trajectory bracket"
                if len(marker["picks"]) == 1 and not marker["excluded_rows"]:
                    pick = marker["picks"][0]
                    pos = pick["top_position"]
                    if pos and pd.notna(r.family) and r.family and np.isfinite(r.wd) and pos["tvdss"] >= r.wd:
                        x, y = head(r)
                        eligible.append({"wellbore": name, "npdid": int(id_), "family": r.family,
                                         "head_x": x, "head_y": y, "top_md_m": pick["top_md_m"], **pos})
                        continue
        exclusions[reason] = exclusions.get(reason, 0) + 1
    result = screen_validation.evaluate(eligible)
    return {**result, "registry_wells_with_top": raw.npdid.nunique(), "excluded": exclusions}


def context_surface(root, hulls):
    """Historical blended surface: retain only masked grid nodes in the actual indexed footprints."""
    with np.load(root / "surfaces.npz") as s, np.load(root / "grid.npz") as grid:
        ix = s["names"].tolist().index("SOGNEFJORD FM")
        xx, yy = np.meshgrid(s["x"], s["y"])
        xy = np.column_stack((xx.ravel(), yy.ravel()))
        mask = s["inside"] & grid["inside"]
        mask &= np.logical_or.reduce([Delaunay(p).find_simplex(xy) >= 0 for p in hulls]).reshape(xx.shape)
        mask &= np.isfinite(s["mean"][ix]) & np.isfinite(s["sd"][ix]) & (s["sd"][ix] >= 0)
        rows, cols = np.nonzero(mask)
        if not len(rows):
            raise ValueError("historical surface has no supported grid nodes in these footprints")
        sl = np.s_[rows.min():rows.max()+1, cols.min():cols.max()+1]
        def masked(a):
            return np.where(mask[sl], a[sl].round(1).astype(object), None).tolist()
        return {"x": xx[sl][0].tolist(), "y": yy[sl][:, 0].tolist(), "z": masked(s["mean"][ix]),
                "sd": masked(s["sd"][ix]), "note": "Historical 2 km Horda mean and model SD, conditional on formation. "
                "Includes the 2010 interpreted horizon blend. Not independent of the wells, a calibrated site interval, or a crossing test."}


def build(data=DATA, out=OUT):
    root = snapshot.resolve(out / "earth/pilot", BUILD)
    hashes = json.loads((root / snapshot.RECEIPT).read_text())["files_sha256"]
    used = ["wells.parquet", "wells.parquet.manifest.json", "force_paths.parquet", "surfaces.npz", "grid.npz"]
    for name in used:
        checked(root / name, hashes[name])
    audit = json.loads(checked(out / SUPPORT, SUPPORT_HASH).read_text())
    src = audit["sources"]
    db = checked(data / src["register"]["path"], src["register"]["sha256"])
    inputs = json.loads((root / "wells.parquet.manifest.json").read_text())["inputs"]
    if not any(Path(i["path"]).name == db.name and i["hashed"] == "whole file" and i["sha256"] == src["register"]["sha256"] for i in inputs):
        raise ValueError("registry not from this Earth build")
    cov = json.loads(checked(out / src["hull_receipt"]["path"], src["hull_receipt"]["sha256"]).read_text())
    recipe = yaml.safe_load(RULE.read_text())
    interval_rule = yaml.safe_load(INTERVAL_RULE.read_text())
    train = src["wireline_training"]
    if train["path"] != "force2020/train.csv":
        raise ValueError("interval screen requires the pinned FORCE training logs")
    names = {w["wellbore"] for survey in audit["surveys"] for w in survey["wells"]}
    mud, tests, logs = interval_screen.sources(db, checked(data / train["path"], train["sha256"]), names)
    for ref in recipe["sources"].values():
        with ZipFile(data / ref["archive"]) as z:
            if hashlib.sha256(z.read(ref["member"])).hexdigest() != ref["sha256"]:
                raise ValueError(f"source report changed: {ref['member']}")
    reg, tops, docs = tables(db)
    frame = pd.read_parquet(root / "wells.parquet")
    fp = pd.read_parquet(root / "force_paths.parquet").sort_values(["wellbore", "md"])
    if fp.duplicated(["wellbore", "md"]).any() or not np.isfinite(fp[["md", "x", "y", "tvdss"]]).all().all():
        raise ValueError("invalid frozen trajectory samples")
    paths = dict(tuple(fp.groupby("wellbore")))
    ambiguous = set(reg.loc[reg.key.duplicated(False), "key"])
    wells, footprints = {}, []
    rules = recipe["formations"]
    for survey in audit["surveys"]:
        sid = survey["id"]
        geom = next(v for v in cov["surveys"] if v["id"] == sid)
        if geom["epsg"] != 23031:
            raise ValueError("unexpected survey CRS")
        xy = np.load(checked(out / "seismic" / sid / "xy.npy", geom["geometry_sha256"]))
        ring = xy[ConvexHull(xy).vertices]
        poly = np.column_stack(TO_FRAME.transform(*ring.T)) / 1000
        footprints.append({"id": sid, "xy": poly.tolist(), "index_xy_sha256": geom["geometry_sha256"]})
        for item in survey["wells"]:
            id_, name = item["npdid"], item["wellbore"]
            hit = reg[reg.npdid.eq(id_) & reg.wellbore.eq(name)]
            if len(hit) != 1 or norm(name) in ambiguous:
                raise ValueError(f"unresolved footprint identity: {name}")
            r = hit.iloc[0]
            context = {"id": sid, "in_hull": item["in_hull"], "tie_status": item["tie_status"],
                       "datum_issue": item.get("datum_issue"), "nearest_indexed_trace_m": item.get("nearest_indexed_trace_m")}
            if id_ in wells:
                wells[id_]["surveys"].append(context)
                continue
            path = paths.get(r.key, fp.iloc[:0])
            docrows = docs[docs.npdid.eq(id_) & docs.wellbore.eq(name)]
            claim = recipe["sources"]["abandonment"]
            wells[id_] = {"npdid": id_, "wellbore": name, "registry_table": "wellbore_" + r.kind, "url": r.url,
                          "registry_status": r.status, "completion_year": int(r.completion_year) if pd.notna(r.completion_year) else None,
                          "head_xy": head(r), "water_m": float(r.wd) if pd.notna(r.wd) and r.wd > 0 else None,
                          "rkb_m": float(r.kb) if pd.notna(r.kb) else None,
                          "surveys": [context], "path_segments": path_segments(path),
                          "markers": markers(tops, r, rules, path),
                          "report_claim": claim if (id_, name) == (claim["npdid"], claim["wellbore"]) else None,
                          "documents": docrows[["name", "kind", "url"]].to_dict("records"),
                          "barrier_integrity": "unknown", "containment_boundary_crossing": "unknown"}
            wells[id_]["interval_screen"] = interval_screen.assess(wells[id_], path, tops, mud, tests, logs, interval_rule)
    return {"schema": 2, "earth_build": BUILD, "region": "pilot", "scope": cov["scope"], "registry_screen": cov["registry"],
            "wells": list(wells.values()), "footprints": footprints, "rule": recipe,
            "interval_rule": interval_rule,
            "historical_surface": context_surface(root, [f["xy"] for f in footprints]),
            "validation": depth_test(reg, tops, paths, set(frame[frame.pilot].wellbore), rules),
            "independent_ties": audit["independent_ties_verified"], "credit": "Smeaheia: Equinor and Gassnova. "
            "Registry, stratigraphy, mud and casing tests: Norwegian Offshore Directorate. Paths and measured curves: FORCE 2020 training logs (CC BY 4.0).",
            "inputs": {"snapshot.json": sha256(root / snapshot.RECEIPT), "snapshot_files": {n: hashes[n] for n in used},
                       SUPPORT: SUPPORT_HASH, "source_receipts": src},
            "implementation": {p.name: sha256(p) for p in [Path(__file__), Path(screen_validation.__file__),
                               Path(interval_screen.__file__), RULE, INTERVAL_RULE, BACKEND / "uv.lock"]}}


def publish(receipt, out=OUT):
    payload = (json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    digest = hashlib.sha256(payload).hexdigest()
    folder = out / STORE
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest}.json"
    with NamedTemporaryFile(dir=folder) as f:
        f.write(payload)
        f.flush()
        try:
            os.link(f.name, path)
        except FileExistsError:
            checked(path, digest)
    return digest


if __name__ == "__main__":
    print(publish(build()))
