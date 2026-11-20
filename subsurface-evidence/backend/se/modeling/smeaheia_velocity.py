"""Reproduce the GN1101 depth pilot from versioned Smeaheia source records.

Run: uv run --frozen python -m se.modeling.smeaheia_velocity
"""

import hashlib
import json
import math
import re
from io import BytesIO, StringIO
from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import duckdb
import numpy as np
from scipy.spatial import cKDTree

from se.config import DATA, OUT
from se.modeling.artifacts import sha256, write_json
from se.modeling.velocity import HorizonTie, WellTie, evaluate, vertical_velocity

SCHEMA_VERSION = 1
RELATIVE_OUT = Path("velocity/gn1101.json")
WORKBOOK = "Well_Reports/data/Smeaheia well picks Feasibility phase.xlsx"
SEABED_TIME = "Surfaces/data/Surfaces_GN1101_2012(Gassnova)/Seabed"
SEABED_DEPTH = "Surfaces/data/Surface_Picks_From_Feasibility_Phase/GN1101 Depth Surfaces converted from TWT depth surfaces/Sea bed"
LOG_32_2_1 = "Well_Logs/data/32 2-1"
LOG_32_4_1 = "Well_Logs/data/32 4-1"
WELL_SITES = {"NO 32/2-1": "32/2-1", "NO 32/4-1 T2": "32/4-1"}
XML = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
COLUMN_NAMES = {"A": "Well name", "C": "Surface name", "D": "MD", "E": "TVD", "F": "TVDSS", "G": "TWT", "H": "Easting", "I": "Northing"}
GRID_SPACING_M = 50


def _member(zip_path: Path, key: str, data_root: Path) -> tuple[bytes, dict]:
    with ZipFile(zip_path) as z:
        content = z.read(key)
    return content, {
        "archive": str(zip_path.relative_to(data_root)), "member": key,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def read_well_picks(content: bytes) -> list[dict]:
    with ZipFile(BytesIO(content)) as x:
        workbook = ET.fromstring(x.read("xl/workbook.xml"))
        if [s.get("name") for s in workbook.findall("x:sheets/x:sheet", XML)] != ["Smeaheia picks"]:
            raise ValueError("unexpected Smeaheia well picks worksheets")
        shared = ["".join(t.text or "" for t in si.iterfind(".//x:t", XML))
                  for si in ET.fromstring(x.read("xl/sharedStrings.xml"))]
        sheet = ET.fromstring(x.read("xl/worksheets/sheet1.xml"))

    out, header = [], False
    for row in sheet.findall(".//x:row", XML):
        cells = {}
        for c in row.findall("x:c", XML):
            if (value := c.findtext("x:v", namespaces=XML)) is None:
                continue
            ref = c.attrib["r"].rstrip("0123456789")
            cells[ref] = shared[int(value)] if c.get("t") == "s" else value
        if cells.get("A") == "Well name":
            if any(cells.get(k) != name for k, name in COLUMN_NAMES.items()):
                raise ValueError("unexpected Smeaheia well picks column layout")
            header = True
        elif cells.get("C", "").startswith("Smeaheia_"):
            if not header:
                raise ValueError("Smeaheia well picks header is missing")
            label = cells["A"]
            if label not in WELL_SITES:
                raise ValueError(f"unverified workbook well-site link: {label}")
            md, tvd, tvdss, twt, east, north = (float(cells[k]) for k in "DEFGHI")
            if not all(map(math.isfinite, (md, tvd, tvdss, twt, east, north))) or not (md >= tvd > 0 > tvdss and twt > 0):
                raise ValueError(f"invalid pick coordinates at worksheet row {row.get('r')}")
            out.append({
                "sheet": "Smeaheia picks", "row": int(row.attrib["r"]), "source_well": label,
                "site": WELL_SITES[label], "horizon": cells["C"], "md_m": md, "tvd_m": tvd, "tvdss_m_signed": tvdss,
                "twt_ms": twt, "east_m": east, "north_m": north, "pick_rkb_m": tvd + tvdss,
            })
    if {r["site"] for r in out} != set(WELL_SITES.values()):
        raise ValueError("the two expected Smeaheia well sites are missing")
    return out


def _well_sites(database: Path) -> dict:
    with duckdb.connect(str(database), read_only=True) as db:
        rows = db.execute("""
            select wlbWellboreName, wlbNpdidWellbore, wlbWaterDepth, wlbKellyBushElevation, wlbGeodeticDatum,
                   wlbUtmZone, wlbEwUtm, wlbNsUtm
            from wellbore_exploration
            where wlbWellboreName in (?, ?)
            order by wlbWellboreName
        """, list(WELL_SITES.values())).fetchall()
    if len(rows) != len(WELL_SITES) or len({r[1] for r in rows}) != len(rows):
        raise ValueError("expected unique FactPages site identities")
    out = {}
    for well, npdid, water, rkb, datum, zone, east, north in rows:
        if (datum, zone) != ("ED50", 31) or water <= 0 or not all(map(math.isfinite, (water, rkb, east, north))):
            raise ValueError(f"{well}: invalid FactPages ED50 UTM 31N site reference")
        out[well] = {"npdid": npdid, "water_depth_m": water, "factpages_rkb_m": rkb, "east_m": east, "north_m": north}
    return out


def _grid_samples(content: bytes, sites: dict, unit: str) -> dict:
    if f"# Field: 3 z {unit}".encode() not in content[:1024] or b"# Projection: Local Rectangular" not in content[:1024]:
        raise ValueError(f"expected source grid Z in {unit}")
    grid = np.loadtxt(BytesIO(content), usecols=(0, 1, 2), encoding="utf-8")
    # Source surface exports are negative down; null/sentinel values are not controls.
    grid = grid[np.isfinite(grid).all(axis=1) & (grid[:, 2] < 0) & (grid[:, 2] > -10_000)]
    if not len(grid):
        raise ValueError("seabed grid has no valid values")
    spacing = [float(np.min(np.diff(np.unique(grid[:, i])))) for i in (0, 1)]
    if not np.allclose(spacing, GRID_SPACING_M, atol=0.01):
        raise ValueError(f"unexpected grid spacing: {spacing}")
    tree = cKDTree(grid[:, :2])
    out = {}
    for name, site in sites.items():
        dist, i = tree.query([site["east_m"], site["north_m"]])
        if dist > GRID_SPACING_M / math.sqrt(2) + 0.01:
            raise ValueError(f"{name}: no valid seabed cell within half a sample-cell diagonal")
        out[name] = {"east_m": float(grid[i, 0]), "north_m": float(grid[i, 1]),
                     "distance_m": float(dist), "source_z": float(grid[i, 2]), "positive_down_value": -float(grid[i, 2])}
    return out


def _las_curve(content: bytes, name: str, unit: str) -> tuple[np.ndarray, np.ndarray]:
    las = content.decode("utf-8-sig")
    sections = re.split(r"^~", las, flags=re.MULTILINE)
    curves = next(s for s in sections if s.startswith("Curve")).splitlines()[1:]
    curves = [c.strip() for c in curves if c.strip() and not c.startswith("#")]
    cols = [i for i, c in enumerate(curves) if c.split(".", 1)[0].strip() == name and c.split(".", 1)[1].split()[0] == unit]
    if len(cols) != 1 or curves[0].split(".", 1)[0].strip() != "DEPT" or curves[0].split(".", 1)[1].split()[0] != "m":
        raise ValueError(f"missing or ambiguous LAS curve {name}.{unit}, or unexpected depth unit")
    sentinel = re.search(r"^NULL\s*\.\s*(-?\d+(?:\.\d+)?)", las, re.MULTILINE)
    if sentinel is None:
        raise ValueError(f"{name}: LAS null sentinel missing")
    null = float(sentinel.group(1))
    text = next(s for s in sections if s.startswith("Ascii")).split("\n", 1)[1]
    d, v = np.loadtxt(StringIO(text), usecols=(0, cols[0]), unpack=True)
    valid = np.isfinite(d) & np.isfinite(v) & (v != null)
    d, v = d[valid], v[valid]
    if len(d) < 2 or np.any(np.diff(d) <= 0):
        raise ValueError(f"{name}: missing samples or nonmonotone LAS measured depth")
    return d, v


def _log_diagnostics(content: bytes, name: str, picks: list[dict], sonic: str) -> dict:
    d, dt = _las_curve(content, sonic, "us/ft")
    bands = []
    for a, b in pairwise(picks):
        lo, hi = a["md_m"], b["md_m"]
        if not d[0] <= lo < hi <= d[-1]:
            raise ValueError(f"{name}: sonic does not span the tied interval")
        start, stop = np.searchsorted(d, [lo, hi])
        support = slice(max(0, start - 1), stop + 1)
        if np.max(np.diff(d[support])) > 5 or np.any(dt[support] <= 0):
            raise ValueError(f"{name}: invalid sonic or raw sample gap >5 m in the tied interval")
        knots = np.r_[lo, d[(d > lo) & (d < hi)], hi]
        integrated_owt_ms = float(np.trapezoid(np.interp(knots, d, dt), knots) / 304.8)
        bands.append({
            "top": a["horizon"], "bottom": b["horizon"], "curve": sonic, "las_one_way_ms": integrated_owt_ms,
            "pick_one_way_ms": (b["twt_ms"] - a["twt_ms"]) / 2,
            "las_effective_velocity_along_md_mps": (hi - lo) * 1000 / integrated_owt_ms,
        })
    result = {"role": "diagnostic only; not fitted and not an independent time tie", "intervals": bands}
    if name == "32/2-1":
        d, owt = _las_curve(content, "OWT32/2-1", "ms")
        if not all(d[0] <= p["md_m"] <= d[-1] for p in picks):
            raise ValueError("OWT is unavailable at the Smeaheia workbook picks")
        offsets = [float(2 * np.interp(p["md_m"], d, owt) - p["twt_ms"]) for p in picks]
        result["las_two_way_minus_workbook_twt_ms"] = offsets
    return result


def build(data_root: Path) -> dict:
    source = data_root / "seismic" / "smeaheia"
    workbook, wb_ref = _member(source / "well_reports.zip", WORKBOOK, data_root)
    raw_picks = read_well_picks(workbook)
    db = data_root / "ncs.duckdb"
    sites = _well_sites(db)
    sources = {"picks": wb_ref, "sites": {"path": "ncs.duckdb", "table": "wellbore_exploration", "sha256": sha256(db)}}
    grids = {}
    for key, member, unit in (("seabed_time", SEABED_TIME, "milliseconds"), ("seabed_depth_derived", SEABED_DEPTH, "meters")):
        content, sources[key] = _member(source / "surfaces.zip", member, data_root)
        crs, sources[f"{key}_crs"] = _member(source / "surfaces.zip", member + ".crsmeta.xml", data_root)
        if b"ST_ED50_UTM31N_P23031" not in crs:
            raise ValueError(f"{member}: source CRS is not the expected ED50 UTM 31N")
        grids[key] = _grid_samples(content, sites, unit)

    ties, controls = [], []
    for site, sample in sites.items():
        picks = sorted((p for p in raw_picks if p["site"] == site), key=lambda p: p["twt_ms"])
        if len(picks) != 4:
            raise ValueError(f"{site}: expected four feasibility picks")
        for p in picks:
            p["distance_to_factpages_site_m"] = math.hypot(p["east_m"] - sample["east_m"], p["north_m"] - sample["north_m"])
            p["rkb_difference_vs_factpages_m"] = p["pick_rkb_m"] - sample["factpages_rkb_m"]
            if p["distance_to_factpages_site_m"] > GRID_SPACING_M:
                raise ValueError(f"{site}: workbook pick is not within one grid cell of the candidate site")
        t0 = grids["seabed_time"][site]["positive_down_value"]
        tie = WellTie(site, t0, sample["water_depth_m"],
                      tuple(HorizonTie(p["horizon"], p["twt_ms"], -p["tvdss_m_signed"]) for p in picks))
        ties.append(tie)
        log_member, sonic = (LOG_32_2_1, "DT") if site == "32/2-1" else (LOG_32_4_1, "HAC")
        las, sources[f"las_{site}"] = _member(source / "well_logs.zip", log_member, data_root)
        controls.append({
            "site": site, "factpages": sample, "horizontal_epsg": 23031,
            "site_link": "32/4-1 T2 workbook picks remain a distinct borehole label; FactPages supplies parent site and water depth only"
                         if site == "32/4-1" else "exact well name and coordinate check",
            "seabed_time": grids["seabed_time"][site], "seabed_depth_derived_diagnostic": grids["seabed_depth_derived"][site],
            "effective_water_velocity_if_zero_at_msl_mps": vertical_velocity(t0, tie.water_depth_m),
            "picks": picks, "wireline_diagnostics": _log_diagnostics(las, site, picks, sonic),
        })
    result = evaluate(ties)
    return {
        "schema_version": SCHEMA_VERSION, "id": "gn1101-time-depth-pilot", "survey": "gn1101", "status": "research_only",
        "activate_overlay": False,
        "target": "depth below mean sea level (m, positive down) at the four supplied Smeaheia horizons",
        "test_reference": "publisher feasibility TVDSS picks; not independent measured checkshots",
        "test_features": "withheld site FactPages water depth, mapped seabed TWT, and corresponding horizon TWT picks only",
        "assumptions": [
            "Use source minus-Z depth/time orientation and millisecond Petrel time values. Absolute equivalence of survey, workbook and LAS time references is not established.",
            "Use FactPages seawater depth at the site; the converted Petrel seabed depth is derived and is not a training anchor.",
            "Effective vertical layer velocities use interval time and TVDSS, not log MD or migration/RMS velocity.",
            "32/4-1 wireline and T2 picks are compared at site level only; trajectory identity is not verified.",
        ],
        "limitations": [
            "Two held-out well sites are a transfer check within one area, not external validation; picks within a site are correlated.",
            "Do not extrapolate laterally or below these horizons, infer materials, or publish a calibrated prediction interval from two sites.",
            "A release needs independent checkshots or well ties, co-registered horizon versions, datum reconciliation and additional held-out wells or a survey.",
        ],
        "sources": sources, "controls": controls, "evaluation": result,
        "implementation_sha256": {p.name: sha256(p) for p in (Path(__file__), Path(__file__).with_name("velocity.py"))},
    }


def main() -> None:
    artifact = build(DATA)
    path = OUT / RELATIVE_OUT
    write_json(path, artifact)
    print(json.dumps({"artifact": str(path), "scores": artifact["evaluation"]["pooled_scores"]}, indent=2))


if __name__ == "__main__":
    main()
