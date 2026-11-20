"""Publish a small search index and independently verifiable packs of borehole evidence."""

import csv
import hashlib
import html
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import duckdb
import yaml
from pyproj import Geod

from se import config
from se.config import AREAS, BACKEND, DATA, OUT, REGIONS
from se.modeling.artifacts import sha256

RULE = BACKEND / "se/knowledge/rules/well_tracks.yaml"
STORE = Path("screen/well_tracks")
SCREEN = "50fe1fd2c6ab16d51bc3e1bb7bf4c573d2bcaf65fa5864fa9ad95f442f89eb7c"
CATALOG = "official/completion_reports/Diskos metatadata for 4462 public end of well reports from the Norwegian continental shelf .csv"
CAT_HASH = "66b5f2c97292cdd6c692e028807b5f02f942cb11ccde6cb3010c605b2a8ab890"
GEOD = Geod(ellps="intl")  # ED50 coordinates in the register
PACK_SIZE = 128


def put(folder, item):
    data = (
        json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()
    digest = hashlib.sha256(data).hexdigest()
    path = folder / (digest + ".json")
    folder.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=folder) as f:
        f.write(data)
        f.flush()
        try:
            os.link(f.name, path)
        except FileExistsError:
            if sha256(path) != digest:
                raise ValueError(f"damaged track artefact: {digest}")
    return digest


def read(folder, digest):
    if not re.fullmatch("[0-9a-f]{64}", digest):
        raise ValueError("invalid track digest")
    raw = (folder / (digest + ".json")).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("track checksum mismatch")
    return json.loads(raw)


def valid_depth(a, b, td, point=False):
    return (
        a is not None
        and b is not None
        and math.isfinite(a)
        and math.isfinite(b)
        and a > 0
        and (a == b if point else a < b)
        and (not td or td <= 0 or b <= td)
    )


def groups(w, local_ids, centre):
    la, lo = w["lat"], w["lon"]
    if (
        w["datum"] != "ED50"
        or la is None
        or lo is None
        or not (50 < la < 90 and -20 < lo < 60)
    ):
        return []
    scopes = ["smeaheia"] if w["npdid"] in local_ids else []
    scopes += [
        k
        for k, v in REGIONS.items()
        if v["lat"][0] <= la <= v["lat"][1] and v["lon"][0] <= lo <= v["lon"][1]
    ]
    b = AREAS["sleipner"]["bbox"]
    if b["lat_min"] <= la <= b["lat_max"] and b["lon_min"] <= lo <= b["lon_max"]:
        scopes.append("sleipner")
    if (
        GEOD.inv(centre["lon"], centre["lat"], lo, la)[2]
        <= AREAS["northern-lights"]["radius_km"] * 1000
    ):
        scopes.append("northern-lights")
    return scopes


def event(kind, a, b, label, source, **facts):
    return {
        "kind": kind,
        "top": a,
        "base": b,
        "label": label,
        "source": source,
        **facts,
    }


def exact(wells, i, name):
    w = wells.get(i)
    return w if w and w["name"] == name else None


def build(data=DATA, out=OUT, focus_dir=None):
    focus = read(focus_dir or out / "screen/smeaheia", SCREEN)
    register = focus["inputs"]["source_receipts"]["register"]
    dbfile, catalogue = data / register["path"], data / CATALOG
    for path, digest in [(dbfile, register["sha256"]), (catalogue, CAT_HASH)]:
        if sha256(path) != digest:
            raise ValueError(f"track input changed: {path.name}")
    rule = yaml.safe_load(RULE.read_text())
    for ref in rule["reports"].values():
        if "archive" in ref:
            with ZipFile(data / ref["archive"]) as z:
                actual = hashlib.sha256(z.read(ref["member"])).hexdigest()
        else:
            actual = sha256(data / ref["path"])
        if actual != ref["sha256"]:
            raise ValueError("reviewed report changed")
    with duckdb.connect(str(dbfile), read_only=True) as db:
        cols = """wlbNpdidWellbore npdid,wlbWellboreName name,wlbStatus status,wlbTotalDepth td,
            wlbGeodeticDatum datum,wlbNsDecDeg lat,wlbEwDecDeg lon,wlbFactPageUrl url"""
        res = db.execute(
            f"SELECT {cols},'exploration' kind FROM wellbore_exploration UNION ALL "
            f"SELECT {cols},'development' kind FROM wellbore_development ORDER BY npdid"
        )
        wells = {}
        labels = [r[0] for r in res.description]
        for row in res.fetchall():
            w = dict(zip(labels, row, strict=True))
            if not w["name"] or not w["npdid"] or w["npdid"] in wells:
                raise ValueError("missing or ambiguous registry identity")
            wells[w["npdid"]] = dict(
                w, events=[], leads=[], excluded=0, overlaps=[], scenario=None
            )

        missed = Counter()

        def add(table, query, make):
            for i, n, a, b, *facts in db.execute(query + " ORDER BY ALL").fetchall():
                w = exact(wells, i, n)
                if w is None:
                    missed[table] += 1
                elif not valid_depth(
                    a, b, w["td"], point=table == "wellbore_casing_and_lot"
                ):
                    w["excluded"] += 1
                else:
                    w["events"].append(make(a, b, *facts))

        add(
            "wellbore_formation_top",
            """SELECT wlbNpdidWellbore,wlbName,lsuTopDepth,lsuBottomDepth,lsuName,
            lsuNpdidLithoStrat FROM wellbore_formation_top WHERE lsuLevel='FORMATION' AND lsuName IS NOT NULL
            AND lsuNpdidLithoStrat > 0""",
            lambda a, b, n, i: event(
                "formation", a, b, n, "wellbore_formation_top", unit_id=i
            ),
        )
        add(
            "wellbore_casing_and_lot",
            """SELECT wlbNpdidWellbore,wlbName,wlbCasingDepth,wlbCasingDepth,
            trim(wlbFormationTestType),wlbLotMudDencity FROM wellbore_casing_and_lot
            WHERE trim(wlbFormationTestType) IN ('LOT','FIT','XLOT','XLO') AND wlbLotMudDencity > 0""",
            lambda a, b, k, v: event(
                "formation test", a, b, k, "wellbore_casing_and_lot", emw_g_cm3=v
            ),
        )
        add(
            "wellbore_dst",
            """SELECT wlbNpdidWellbore,wlbName,wlbDstFromDepth,wlbDstToDepth,wlbDstTestNumber
            FROM wellbore_dst""",
            lambda a, b, n: event("reservoir test", a, b, f"DST {n}", "wellbore_dst"),
        )
        for (
            i,
            n,
            k,
            title,
            url,
        ) in db.execute("""SELECT wlbNpdidWellbore,wlbName,wlbDocumentType,wlbDocumentName,
                wlbDocumentUrl FROM wellbore_document ORDER BY ALL""").fetchall():
            w = exact(wells, i, n)
            if w:
                w["leads"].append(
                    {
                        "source": "wellbore_document",
                        "title": title,
                        "type": k,
                        "url": url,
                    }
                )
            else:
                missed["wellbore_document"] += 1

        def verify_history(i, n, fragment):
            rows = db.execute(
                "SELECT wlbHistory FROM wellbore_history WHERE wlbNpdidWellbore=? AND wlbName=?",
                [i, n],
            ).fetchall()
            if not any(
                fragment
                in " ".join(html.unescape(re.sub("<[^>]+>", " ", t or "")).split())
                for (t,) in rows
            ):
                raise ValueError(f"{n}: curated history claim missing")

        for case in rule["dst_notes"]:
            i, n = case["npdid"], case["name"]
            verify_history(i, n, case["fragment"])
            w = exact(wells, i, n)
            if not w:
                raise ValueError(f"{n}: DST identity mismatch")
            (dst,) = [
                e
                for e in w["events"]
                if e["source"] == "wellbore_dst"
                and [e["top"], e["base"]] == case["table_md"]
            ]
            dst.update(
                note=case["note"],
                evidence=case["fragment"],
                also_source="wellbore_history",
            )

        for i, n, a, b, fragment, note in rule["history"]:
            verify_history(i, n, fragment)
            w = exact(wells, i, n)
            if not w or not valid_depth(a, b, w["td"]):
                raise ValueError(f"{n}: history identity or depth mismatch")
            w["events"].append(
                event(
                    "placement",
                    a,
                    b,
                    "Reported cement placement",
                    "wellbore_history",
                    evidence=fragment,
                    note=note,
                    datum="Reported metres; reference not confirmed.",
                )
            )
    by_name = defaultdict(list)
    for w in wells.values():
        by_name[w["name"]].append(w)
    with catalogue.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            matches = by_name.get(row["Wellbore Name"], [])
            if (
                row["Public"] == "Y"
                and row["FolderFileName"].lower().endswith(".pdf")
                and len(matches) == 1
            ):
                matches[0]["leads"].append(
                    {
                        "source": "Diskos catalogue",
                        "title": row["FolderFileName"],
                        "item": row["DISKOS Info Item Id"],
                        "type": "Public PDF listing; content not assessed",
                    }
                )
    for case in rule["cases"]:
        w = wells[case["npdid"]]
        if w["name"] != case["name"]:
            raise ValueError("reviewed case identity mismatch")
        ref = rule["reports"][case["report"]]
        if "item" in ref and not any(
            r["source"] == "Diskos catalogue"
            and r["item"].replace(",", "") == str(ref["item"])
            and r["title"] == Path(ref["path"]).name
            for r in w["leads"]
        ):
            raise ValueError(
                "reviewed report does not match the public catalogue entry"
            )
        for a, b, n in case["placements"]:
            if not valid_depth(a, b, w["td"]):
                raise ValueError(f"invalid reviewed placement: {n}")
            w["events"].append(
                event(
                    "placement",
                    a,
                    b,
                    n,
                    case["report"],
                    page=case["page"],
                    datum=case["datum"],
                )
            )
            for e in w["events"]:
                if e["kind"] == "formation" and e["unit_id"] in case.get("compare", []):
                    overlap = min(b, e["base"]) - max(a, e["top"])
                    if overlap > 0:
                        w["overlaps"].append(
                            {
                                "placement": n,
                                "formation": e["label"],
                                "m": overlap,
                                "formation_m": e["base"] - e["top"],
                                "datum": case["datum"],
                            }
                        )
        for text in case.get("tests", []):
            w["events"].append(
                event(
                    "equipment test",
                    None,
                    None,
                    text,
                    case["report"],
                    page=case["page"],
                )
            )
    local_ids = set()
    for fw in focus["wells"]:
        w = wells[fw["npdid"]]
        if w["name"] != fw["wellbore"]:
            raise ValueError("focused screen identity mismatch")
        if any(s["in_hull"] for s in fw["surveys"]):
            local_ids.add(w["npdid"])
        w["scenario"] = fw["interval_screen"]["strict"]
    (centre,) = by_name[AREAS["northern-lights"]["center_well"]]
    if centre["datum"] != "ED50" or not centre["lat"] or not centre["lon"]:
        raise ValueError("unresolved Northern Lights centre")
    scope_labels = {
        "all": "All registry wellbores",
        **{k: v["title"] for k, v in AREAS.items()},
        **{k: v["title"] for k, v in REGIONS.items()},
    }
    index, packs = [], defaultdict(dict)
    coverage = {
        k: {"wells": 0, "positioned": 0, "placements": 0, "leads_only": 0}
        for k in scope_labels
    }
    for i, w in wells.items():
        scopes = groups(w, local_ids, centre)
        w["scopes"] = scopes
        for k in ["all", *scopes]:
            c = coverage[k]
            c["wells"] += 1
            c["positioned"] += any(e["top"] is not None for e in w["events"])
            c["placements"] += any(e["kind"] == "placement" for e in w["events"])
            c["leads_only"] += bool(w["leads"]) and not w["events"]
        index.append([i, w["name"], w["status"], scopes])
        packs[i // PACK_SIZE][i] = w
    folder = out / STORE
    return put(
        folder,
        {
            "schema": 1,
            "columns": ["npdid", "name", "status", "scopes"],
            "index": index,
            "scopes": scope_labels,
            "coverage": coverage,
            "focus_version": SCREEN,
            "pack_size": PACK_SIZE,
            "packs": {k: put(folder, d) for k, d in packs.items()},
            "rules": rule,
            "excluded_identity_rows": dict(missed),
            "inputs": {
                "registry": register,
                "catalogue": {"path": CATALOG, "sha256": CAT_HASH},
            },
            "regions": REGIONS,
            "sites": AREAS,
            "code": {
                p.name: sha256(p)
                for p in (
                    Path(__file__),
                    Path(config.__file__),
                    RULE,
                    BACKEND / "uv.lock",
                )
            },
        },
    )


if __name__ == "__main__":
    print(build())
