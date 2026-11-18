"""Facts about one wellbore from FactPages, each tagged with the table it came from so answers can cite it."""

import re

from common import clean, norm, rows, wellbore


def _name(name: str) -> str:
    w = wellbore(name)
    return w["name"] if w else name


def header(name: str) -> dict | None:
    w = wellbore(name)
    return clean({k: v for k, v in w.items() if k not in ("north", "east")}) if w else None


def tops(name: str) -> list[dict]:
    return [
        clean(r)
        for r in rows(
            "select lsuName as unit, lsuLevel as level, lsuNameParent as parent, lsuTopDepth as top, "
            "lsuBottomDepth as base from wellbore_formation_top where wlbName = ? order by lsuTopDepth, lsuLevel",
            _name(name),
        )
    ]


def casing(name: str) -> list[dict]:
    """Casing strings with shoe depth, hole size and the leak-off or formation integrity test at the shoe."""
    return [
        clean(r)
        for r in rows(
            "select wlbCasingType as type, wlbCasingDiameter as diameter, wlbCasingDepth as depth, "
            "wlbHoleDiameter as hole, wlbHoleDepth as hole_depth, wlbLotMudDencity as lot_mud_density, "
            "wlbFormationTestType as test from wellbore_casing_and_lot where wlbName = ? order by wlbCasingDepth",
            _name(name),
        )
    ]


def mud(name: str) -> list[dict]:
    return [
        clean(r)
        for r in rows(
            "select wlbMD as md, wlbMudWeightAtMD as weight, wlbMudType as type, wlbMudDateMeasured as date "
            "from wellbore_mud where wlbName = ? order by wlbMD",
            _name(name),
        )
    ]


def dst(name: str) -> list[dict]:
    return [clean(r) for r in rows("select * from wellbore_dst where wlbName = ?", _name(name))]


def cores(name: str) -> list[dict]:
    return [
        clean(r)
        for r in rows(
            "select wlbCoreNumber as core, wlbCoreIntervalTop as top, wlbCoreIntervalBottom as base, "
            "wlbCoreIntervalUom as unit, wlbTotalCoreLength as total_length from wellbore_core where wlbName = ? "
            "order by wlbCoreNumber",
            _name(name),
        )
    ]


def history(name: str) -> str:
    r = rows("select wlbHistory from wellbore_history where wlbName = ?", _name(name))
    return re.sub(r"<[^>]+>", " ", r[0]["wlbHistory"] or "").strip() if r else ""


def documents(name: str) -> list[dict]:
    return [
        clean(r)
        for r in rows(
            "select wlbDocumentType as type, wlbDocumentName as name, wlbDocumentUrl as url, "
            "wlbDocumentFormat as format, wlbDocumentSize as size from wellbore_document where wlbName = ?",
            _name(name),
        )
    ]


def card(name: str) -> dict:
    """Everything above in one dict (the dossier's facts)."""
    return {
        "header": header(name),
        "tops": tops(name),
        "casing": casing(name),
        "mud": mud(name),
        "dst": dst(name),
        "cores": cores(name),
        "history": history(name),
        "documents": documents(name),
    }


# not facts about the well: the UTM zone reads like a block number to a model
HIDE = {"zone", "npdid", "url", "north", "east"}


def facts_text(c: dict, max_mud: int = 12) -> str:
    """The card as compact text for a prompt, each block labelled with its source table."""
    h = c["header"] or {}
    out = [
        "[F:wellbore] " + ", ".join(f"{k}={v}" for k, v in h.items() if v not in (None, "") and k not in HIDE),
    ]
    if c["tops"]:
        out.append("[F:tops] " + "; ".join(f"{t['unit']} {t['top']}-{t['base']} m" for t in c["tops"][:60]))
    if c["casing"]:
        out.append(
            "[F:casing] "
            + "; ".join(
                f"{x['type']} {x['diameter']}in at {x['depth']} m (hole {x['hole']}in to {x['hole_depth']} m"
                + (f", {x['test']} {x['lot_mud_density']} g/cm3" if x["lot_mud_density"] else "")
                + ")"
                for x in c["casing"]
            )
        )
    if c["mud"]:
        step = max(1, len(c["mud"]) // max_mud)
        out.append("[F:mud] " + "; ".join(f"{m['md']} m {m['weight']} g/cm3 {m['type']}" for m in c["mud"][::step]))
    if c["dst"]:
        out.append("[F:dst] " + "; ".join(", ".join(f"{k}={v}" for k, v in d.items() if v not in (None, "", 0)) for d in c["dst"]))
    if c["cores"]:
        out.append("[F:cores] " + "; ".join(f"core {x['core']} {x['top']}-{x['base']} {x['unit']}" for x in c["cores"]))
    if c["history"]:
        out.append("[F:history] " + c["history"][:5000])
    return "\n".join(out)


def search_names(q: str, limit: int = 20) -> list[dict]:
    from common import wellbores

    q = norm(q)
    hits = [w for w in wellbores() if q in norm(w["name"])]
    hits.sort(key=lambda w: (not norm(w["name"]).startswith(q), len(w["name"])))
    return [{"name": w["name"], "kind": w["kind"], "field": w["field"], "content": w["content"]} for w in hits[:limit]]
