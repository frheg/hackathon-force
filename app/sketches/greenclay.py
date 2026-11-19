"""Green clay labels from the completion reports: every place a report says that a rock is glauconitic, chloritic,
green clay and so on, with the depth interval it names, the formation near it and how sure we are.

    uv run python -m sketches.greenclay          # all reports, about a minute; writes data/atlas/greenclay/

labels.parquet: one row per mention. wells.parquet: one row per wellbore, with how much description we read (so a well
with plenty of description and no mention is a weak negative) and its position. summary.json: counts.

A mention is not presence at depth. Confidence says how well it is pinned down:
  high    a depth interval on the same line as a lithology word (a cuttings or core description row)
  medium  a single depth on the line, or an interval on a neighbouring line, with a lithology word
  low     no depth, or no lithology word: general text, formation descriptions, reasoning
"""

import os
import re
import time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache

import duckdb
import pandas as pd

from common import DATA_DIR, norm, save_json

OUT = DATA_DIR / "atlas" / os.environ.get("GREENCLAY_OUT", "greenclay")  # another folder to re-run without touching the published tables
WORKERS = int(os.environ.get("WORKERS", "14"))

# the minerals and colours that make a green clay; the first group that matches names the kind
KINDS = [
    ("glauconite", r"glauconit\w*|green[- ]?sand\w*|verdine"),
    ("chlorite", r"chlorit\w*"),
    ("nontronite", r"nontronit\w*"),
    ("celadonite", r"celadonit\w*"),
    ("green clay", r"green[- ]?clay\w*|(?:(?:grey|gray|olive|brown|yellow|bluish)[- ])?green(?:ish)?(?:[- ](?:grey|gray|brown|yellow))?[- ]"
                   r"(?:clay\w*|shale\w*|mudstone\w*|silt\w*|marl\w*)"),
]
MINERAL = re.compile("|".join(f"(?P<k{i}>{p})" for i, (_, p) in enumerate(KINDS)), re.I)
# "Green Clay" as the name of a formation top or marker (Top Green Clay, a row of a tops table), not a description of a rock
MARKER = re.compile(r"top\s+green\s*clay|green\s*clay\s+(?:marker|fm\b|formation|unit|interval|top|member)|^[|\s]*green\s*clay\s*\||\|\s*green\s*clay\s*\|", re.I)
LITH = re.compile(r"\b(?:claystone|clay|shale|mudstone|sandstone|sand|siltstone|silt|limestone|marl|dolomite|chalk|cuttings|core|"
                  r"samples?|cavings|lithology|grains?|cement|laminae|bioturbat\w*|fossils?|tuff|coal)\b", re.I)
NUM = r"\d{2,5}(?:[.,]\d+)?"
UNIT = r"(?:m\b|ft\b|feet\b|mMD|m\s?MD|mRKB|m\s?RKB|mbRT|m\s?BRT)"
INTERVAL = re.compile(rf"(?<![\d.,/])({NUM})\s*(?:-|–|—|to|til)\s*({NUM})(?![\d/])\s*({UNIT})?", re.I)
SINGLE = re.compile(rf"(?<![\d.,/-])({NUM})\s*({UNIT})", re.I)
NOT_DEPTH_AFTER = re.compile(r"\s*(?:%|mm\b|cm\b|µm|um\b|micron|ppg|sg\b|bar\b|psi\b|kg|g/|°|deg|hrs?\b|h\b|api|cp\b|ohm)", re.I)
CUE_BEFORE = re.compile(r"(?:from|interval|between|depth|at|over|section|run|core|sample|top|base)\W*$|^[\s|*\-•]*$", re.I)
# distinctive formation names that are safe to accept without "Fm" or "Group" after them (others need that suffix)
DISTINCT = ["Balder", "Sele", "Lista", "Draupne", "Utsira", "Hordaland", "Rogaland", "Shetland", "Nordland", "Cromer Knoll", "Heather",
            "Hugin", "Skagerrak", "Rødby", "Våle", "Ekofisk", "Frigg", "Grid", "Skade", "Vestland", "Dunlin", "Brent", "Viking", "Lange", "Lysing",
            "Springar", "Tare", "Tang", "Kyrre", "Egga", "Tryggvason", "Spekk", "Åsgard", "Garn", "Tofte", "Tilje", "Fangst", "Båt", "Nise", "Kvitnos"]


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _unit(u: str | None) -> str | None:
    if not u:
        return None
    return "ft" if u.lower().startswith(("ft", "feet")) else "m"


def _depth_ok(a: float, b: float | None, unit: str | None, max_thickness: float = 2500) -> bool:
    top = 30000 if unit and unit.lower().startswith(("ft", "feet")) else 8000
    if b is None:
        return 0 < a <= top
    # two numbers that look like years (1990-2005) with no unit are not depths
    if not unit and 1900 <= a <= 2040 and 1900 <= b <= 2040:
        return False
    return 0 < a < b <= top and (b - a) <= max_thickness


def depths(line: str) -> list:
    """Depth candidates in a line as (position, from, to or None, unit): ranges like 1250-1300 m, single depths like 1250 m, and for
    a table row the first cells (a sample number then a depth, or a from and a to)."""
    out = []
    for m in INTERVAL.finditer(line):
        a, b, u = _num(m.group(1)), _num(m.group(2)), m.group(3)
        tail = line[m.end():m.end() + 10]
        before = line[max(0, m.start() - 25):m.start()]
        if not u and (NOT_DEPTH_AFTER.match(tail) or not CUE_BEFORE.search(before)):
            continue  # 10-20% sand, 0.1-0.5 mm: a range without a unit needs a cue that it is a depth
        if _depth_ok(a, b, u):
            out.append((m.start(), a, b, _unit(u)))
    for m in SINGLE.finditer(line):
        a = _num(m.group(1))
        if _depth_ok(a, None, m.group(2)) and not any(s <= m.start() < s + 30 for s, *_ in out):
            out.append((m.start(), a, None, _unit(m.group(2))))
    if line.startswith("|"):
        cells = [c.strip() for c in line.strip("|").split("|")][:4]
        nums = [_num(c) for c in cells if re.fullmatch(NUM, c)]
        if len(nums) >= 2:
            if nums[0] < 200 and nums[1] > 5 * nums[0] and _depth_ok(nums[1], None, None):
                out.append((0, nums[1], None, None))  # sample number, then the depth
            elif _depth_ok(nums[0], nums[1], None, max_thickness=600):
                out.append((0, nums[0], nums[1], None))
            elif nums[0] >= 200 and nums[1] <= 100 and _depth_ok(nums[0], None, None):
                out.append((0, nums[0], None, None))  # a depth, then the share of the sample (%) of a cuttings description
    return sorted(out)


def nearest_depth(cands: list, pos: int):
    """The depth candidate closest to a mention, preferring one just before it (a description follows its depth)."""
    best = None
    for s, a, b, u in cands:
        d = pos - s if s <= pos else (s - pos) + 1000
        if d <= 900 and (best is None or d < best[0]):
            best = (d, (a, b, u, s))
    return best[1] if best else None


def marker_depth(line: str):
    """The depth in a row of a tops table: the first number after the "Green Clay" cell (the top; the others are other depth references)."""
    cells = [c.strip() for c in line.strip("|").split("|")]
    for i, c in enumerate(cells):
        if re.search(r"green\s*clay", c, re.I):
            for x in cells[i + 1:i + 4]:
                if re.fullmatch(NUM, x) and 100 <= _num(x) <= 8000:
                    return _num(x)
    return None


@lru_cache(1)
def formation_regex():
    con = duckdb.connect(str(DATA_DIR / "ncs.duckdb"), read_only=True)
    names = {n.rsplit(" ", 1)[0].title() for (n,) in con.execute("select distinct lsuName from strat_litho_overview").fetchall() if n and " " in n}
    names |= {"Cromer Knoll", "Rødby"}
    names = sorted((n for n in names if len(n) >= 3 and n.upper() != "NO FORMAL"), key=len, reverse=True)
    esc = "|".join(re.escape(n) for n in names)
    dist = "|".join(re.escape(n) for n in DISTINCT)
    return re.compile(rf"\b((?:{esc})\s+(?:Fm\.?|Formation|Gp\.?|Group|Mb\.?|Member)|(?:{dist}))\b")


def nearest_formation(text: str, pos: int, width: int = 500) -> str | None:
    lo, hi = max(0, pos - width), pos + width
    best = None
    for m in formation_regex().finditer(text[lo:hi]):
        d = abs(lo + m.start() - pos)
        if best is None or d < best[0]:
            best = (d, m.group(1))
    return re.sub(r"\s+", " ", best[1]) if best else None


def extract_page(text: str):
    """(labels, number of description lines) for one page of OCR markdown."""
    lines = text.splitlines()
    out, n_desc, off = [], 0, 0
    starts = []
    for ln in lines:
        starts.append(off)
        off += len(ln) + 1
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        lith = bool(LITH.search(line))
        cands = depths(line)
        if lith and any(b is not None for _, _, b, _ in cands):
            n_desc += 1
        for m in MINERAL.finditer(line):
            kind = next(KINDS[int(k[1:])][0] for k, v in m.groupdict().items() if v)
            d, src = nearest_depth(cands, m.start()), "line"
            marker = kind == "green clay" and bool(MARKER.search(line))
            if marker and line.startswith("|") and (top := marker_depth(line)):
                d = (top, None, None, 0)  # a tops table: the top depth only
            if d is None:  # a depth header on a neighbouring line
                for j in (i - 1, i - 2, i + 1):
                    if 0 <= j < len(lines) and lines[j].strip():
                        c2 = depths(lines[j].strip())
                        if c2:
                            c = c2[-1] if j < i else c2[0]
                            d, src = (c[1], c[2], c[3], -1), "neighbour"
                            break
            from_row = line.startswith("|") and d is not None and d[3] == 0  # the depth is in the row's first cells: a sample or interval row
            context = "marker" if marker and d else "desc" if lith and d else "depth_mention" if d else "text"
            conf = ("high" if (lith and d and src == "line" and (d[1] is not None or from_row)) or (marker and d and from_row)
                    else "medium" if lith and d else "low")
            out.append({"kind": kind, "term": m.group(0).lower(), "depth_from": d[0] if d else None, "depth_to": d[1] if d else None,
                        "depth_unit": (d[2] or None) if d else None, "depth_source": src if d else None,
                        "formation": nearest_formation(text, starts[i] + m.start()), "context": context, "confidence": conf,
                        "marker": marker, "source_kind": "table" if line.startswith("|") else "text", "snippet": re.sub(r"\s+", " ", line.strip("| "))[:400]})
    return out, n_desc


LITH_CLASS = [("clay", re.compile(r"\b(?:claystone|clay|shale|mudstone|marl|clays|shales)\b", re.I)),
              ("sand", re.compile(r"\b(?:sandstone|sand|sands|sst|sandy)\b", re.I)),
              ("carbonate", re.compile(r"\b(?:limestone|dolomite|chalk|lst)\b", re.I))]


def lith_class(line: str) -> str:
    """The first of clay, sand, carbonate that the row names (a row of 'sandy claystone' is clay). Used to separate lithology from mineral."""
    best = min(((m.start(), k) for k, rx in LITH_CLASS if (m := rx.search(line))), default=None)
    return best[1] if best else "other"


def describe_page(text: str) -> list:
    """Every rock description row on a page, green or not: (depth_from, depth_to, has_green, lithology class, line text). This is the coverage: where a
    report described the rock at a depth, so that "no mention" there means something."""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or not LITH.search(line):
            continue
        c = depths(line)
        if not c:
            continue
        _, a, b, _u = c[0]
        out.append((a, b, bool(MINERAL.search(line)), lith_class(line), line[:400]))  # the text is kept so any keyword can be a target (LOG L034)
    return out


def scan(path_str: str):
    from pathlib import Path

    from sketches.atlas import read_report

    f = Path(path_str)
    folder = f.parent.parent.name
    labels, pages, desc, rows = [], 0, 0, []
    for p in read_report(f)["pages"]:
        text = (p.get("OCR") or {}).get("ocr_markdown") or ""
        pages += 1
        rows += [(p.get("page_no"), *r) for r in describe_page(text)]
        got, n = extract_page(text)
        desc += n
        q = (p.get("page_metadata") or {}).get("quality")
        for g in got:
            labels.append({"folder": folder, "file": f.name, "page": p.get("page_no"), "page_quality": q, **g})
    return folder, f.name, pages, desc, labels, rows


def main():
    from sketches.atlas import json_files

    t0 = time.time()
    files = [str(f) for f in json_files()]
    OUT.mkdir(parents=True, exist_ok=True)
    rows, per_file, cover = [], [], []
    with ProcessPoolExecutor(WORKERS) as pool:
        for i, (folder, name, pages, desc, labels, drows) in enumerate(pool.map(scan, files, chunksize=8)):
            rows += labels
            cover += [(folder, name, *r) for r in drows]
            per_file.append({"folder": folder, "file": name, "pages": pages, "desc_lines": desc})
            if i % 500 == 499:
                print(f"{i + 1}/{len(files)} reports, {len(rows)} mentions, {time.time() - t0:.0f} s", flush=True)
    labels = pd.DataFrame(rows)
    labels["wellbore"] = labels["folder"].map(lambda s: norm(s.replace("_", "/", 1).replace("_", " ")))
    # the same sentence in a second copy of a report is one mention
    labels = labels.drop_duplicates(["wellbore", "kind", "depth_from", "depth_to", "snippet"]).reset_index(drop=True)
    pf = pd.DataFrame(per_file)
    pf["wellbore"] = pf["folder"].map(lambda s: norm(s.replace("_", "/", 1).replace("_", " ")))
    wells = pf.groupby("wellbore").agg(reports=("file", "count"), pages=("pages", "sum"), desc_lines=("desc_lines", "sum")).reset_index()
    g = labels.groupby("wellbore")
    wells = wells.merge(g.size().rename("mentions"), on="wellbore", how="left").merge(
        labels[labels.confidence == "high"].groupby("wellbore").size().rename("high"), on="wellbore", how="left").merge(
        g["kind"].agg(lambda s: ",".join(sorted(set(s)))).rename("kinds"), on="wellbore", how="left")
    wells[["mentions", "high"]] = wells[["mentions", "high"]].fillna(0).astype(int)
    con = duckdb.connect(str(DATA_DIR / "ncs.duckdb"), read_only=True)
    pos = con.execute("select wlbWellboreName n, wlbNsDecDeg la, wlbEwDecDeg lo from wellbore_exploration union all "
                      "select wlbWellboreName, wlbNsDecDeg, wlbEwDecDeg from wellbore_development").fetchdf()
    pos["wellbore"] = pos["n"].map(norm)
    wells = wells.merge(pos.drop_duplicates("wellbore")[["wellbore", "la", "lo"]].rename(columns={"la": "lat", "lo": "lon"}), on="wellbore", how="left")
    full = pd.DataFrame(cover, columns=["folder", "file", "page", "depth_from", "depth_to", "has_green", "lith", "text"])
    full["wellbore"] = full["folder"].map(lambda s: norm(s.replace("_", "/", 1).replace("_", " ")))
    full = full.drop_duplicates(["wellbore", "depth_from", "depth_to", "has_green", "lith"]).reset_index(drop=True)
    cov = full.drop(columns=["folder", "file", "page", "text"])  # same table as before the text was kept
    cov.to_parquet(OUT / "descriptions.parquet")
    full[["wellbore", "file", "page", "depth_from", "depth_to", "lith", "has_green", "text"]].to_parquet(OUT / "descriptions_text.parquet")
    labels.to_parquet(OUT / "labels.parquet")
    wells.to_parquet(OUT / "wells.parquet")
    top = labels[labels.confidence != "low"]
    save_json(OUT / "summary.json", {
        "built": time.strftime("%Y-%m-%d %H:%M"), "reports": len(files), "wellbores": len(wells), "pages": int(pf.pages.sum()),
        "description_rows": len(cov), "wells_with_descriptions": int(cov.wellbore.nunique()),
        "mentions": len(labels), "wells_with_mention": int((wells.mentions > 0).sum()),
        "by_kind": labels.kind.value_counts().to_dict(), "by_confidence": labels.confidence.value_counts().to_dict(),
        "markers": int(labels.marker.sum()), "wells_with_marker": int(labels[labels.marker].wellbore.nunique()),
        "weak_negative_wells": int(((wells.mentions == 0) & (wells.desc_lines >= 20)).sum()),
        "wells_with_high": int((wells.high > 0).sum()), "wells_with_medium_or_high": int(top.wellbore.nunique()),
        "top_formations": top.formation.value_counts().head(25).to_dict(), "with_position": int(wells.lat.notna().sum())})
    print(f"done in {time.time() - t0:.0f} s: {len(labels)} mentions in {int((wells.mentions > 0).sum())} of {len(wells)} wellbores")


if __name__ == "__main__":
    main()
