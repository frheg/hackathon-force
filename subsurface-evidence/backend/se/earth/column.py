"""Stratigraphic column of the pilot (PLAN P2.1, LOG L056).

FactPages gives each unit's level, parent group, description and FactPage URL, but no age order. The order is taken from the wells:
for every pair of units met in one well, which top is shallower. Units are ordered by those votes (Copeland: wins minus losses),
groups first, then formations inside their group. Disagreements (faults, repeated sections, misnamed picks) are counted, not hidden.
Horizons modelled as surfaces: groups and formations met in at least MIN_WELLS pilot wells.
"""
import json
from collections import defaultdict
from itertools import combinations

import duckdb
import numpy as np
import pandas as pd

from se.config import DATA, EARTH
from se.earth import manifest

MIN_WELLS = 30  # a surface needs data from at least this many wells (about one per 1,000 km2 of the pilot)
SKIP = {"NO FORMAL NAME", "UNDIFFERENTIATED", "UNDEFINED GP", "NO GROUP DEFINED"}  # placeholders, not units


def lexicon() -> pd.DataFrame:
    c = duckdb.connect(str(DATA / "ncs.duckdb"), read_only=True)
    return c.execute("select lsuName name, lsuLevel level, lsuNameParent parent, lsuDescription description, IsuFactPageUrl url from strat_litho_overview").df()


def order_units(t: pd.DataFrame) -> tuple[list, dict]:
    """Copeland order of the units in `t` (columns wellbore, name, top_tvdss), shallow to deep, and pairwise agreement."""
    wins = defaultdict(int)
    pairs = defaultdict(lambda: [0, 0])  # (a above b count, b above a count) for sorted (a, b)
    for _, g in t.groupby("wellbore"):
        g = g.groupby("name").top_tvdss.min()
        for a, b in combinations(sorted(g.index), 2):
            if g[a] == g[b]:
                continue
            if g[a] < g[b]:
                pairs[(a, b)][0] += 1
            else:
                pairs[(a, b)][1] += 1
    units = sorted(set(t.name))
    score = {u: 0 for u in units}
    agree = tot = 0
    for (a, b), (ab, ba) in pairs.items():
        if ab > ba:
            score[a] += 1; score[b] -= 1
        elif ba > ab:
            score[b] += 1; score[a] -= 1
        agree += max(ab, ba); tot += ab + ba
    order = sorted(units, key=lambda u: -score[u])
    conflicts = sorted(((a, b, ab, ba) for (a, b), (ab, ba) in pairs.items() if min(ab, ba) > 0), key=lambda r: -min(r[2], r[3]))[:15]
    return order, {"pair_observations": tot, "agreeing_share": round(agree / tot, 4) if tot else None, "worst_conflicts": [{"a": a, "b": b, "a_above_b": ab, "b_above_a": ba} for a, b, ab, ba in conflicts]}


def build() -> dict:
    tops = pd.read_parquet(EARTH / "tops.parquet")
    tops = tops[~tops.name.isin(SKIP) & tops.top_tvdss.notna()]
    lex = lexicon().set_index("name")
    groups = tops[tops.level == "GROUP"]
    gorder, gstat = order_units(groups)
    cols = []
    fstats = {}
    for gname in gorder:
        f = tops[(tops.level == "FORMATION") & tops.name.map(lambda n: lex.parent.get(n) == gname)]
        forder, fstat = order_units(f) if len(f) else ([], {})
        fstats[gname] = fstat
        gw = groups[groups.name == gname].wellbore.nunique()
        cols.append({"group": gname, "wells": int(gw), "model": bool(gw >= MIN_WELLS), "url": lex.url.get(gname),
                     "formations": [{"name": fn, "wells": int(f[f.name == fn].wellbore.nunique()), "model": bool(f[f.name == fn].wellbore.nunique() >= MIN_WELLS),
                                     "url": lex.url.get(fn)} for fn in forder]})
    orphan = sorted(set(tops[(tops.level == "FORMATION")].name) - {fm["name"] for c in cols for fm in c["formations"]})
    out = {"min_wells": MIN_WELLS, "groups": cols, "group_order_check": gstat, "formation_order_checks": fstats,
           "formations_without_group_in_pilot": orphan,
           "horizons": [h for c in cols if c["model"] for h in [{"name": c["group"], "level": "GROUP"}] + [{"name": fm["name"], "level": "FORMATION", "group": c["group"]} for fm in c["formations"] if fm["model"]]],
           "source": "order from pilot well tops (TVDSS); names, parents, descriptions and URLs from FactPages strat_litho_overview"}
    (EARTH / "column.json").write_text(json.dumps(out, indent=1))
    manifest.write(EARTH / "column.json", [EARTH / "tops.parquet", DATA / "ncs.duckdb"], {"min_wells": MIN_WELLS, "skip": sorted(SKIP)})
    return out


if __name__ == "__main__":
    o = build()
    print("group order:", [f"{c['group']} ({c['wells']})" for c in o["groups"]])
    print("group pairs agreeing:", o["group_order_check"]["agreeing_share"], "| worst:", o["group_order_check"]["worst_conflicts"][:3])
    print("horizons to model:", len(o["horizons"]), [h["name"] for h in o["horizons"]])
    print("formations without a group in the lexicon:", o["formations_without_group_in_pilot"][:10])
