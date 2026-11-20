"""Where the model may say anything: the offshore Norwegian continental shelf (owner question, LOG L078: Garn Formation predicted under
mainland Norway and Sweden). The region boxes are latitude-longitude rectangles that also cover land, foreign shelves and the deep ocean;
kriged surfaces extrapolate there without any data. The mask is the union of Sodir's licence blocks (FactMaps layer 802, 1,827 blocks),
which tile the offshore NCS and stop at the coast and the national borders. A lattice column is on the shelf if its centre is inside a
block.
"""
import json
from functools import lru_cache

import numpy as np

from se.config import DATA

BLOCKS = DATA / "sodir" / "factmaps" / "blocks.geojson"


@lru_cache(maxsize=1)
def _polys():
    from se.evidence.spatial import project

    out = []
    for f in json.loads(BLOCKS.read_text())["features"]:
        g = f["geometry"]
        if not g:
            continue
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            r = np.asarray(poly[0], float); p = project(r[:, 0], r[:, 1])
            holes = [project(np.asarray(h, float)[:, 0], np.asarray(h, float)[:, 1]) for h in poly[1:]]
            out.append((p, holes, p[:, 0].min(), p[:, 0].max(), p[:, 1].min(), p[:, 1].max()))
    return out


def mask(x_km, y_km) -> np.ndarray:
    """(ny, nx) True where the lattice column (EPSG:3035 km centres x, y) lies on the offshore NCS."""
    from se.earth.factors import _inside

    X, Y = np.meshgrid(np.asarray(x_km, float), np.asarray(y_km, float)); px, py = X.ravel(), Y.ravel(); out = np.zeros(px.size, bool)
    for p, holes, x0, x1, y0, y1 in _polys():
        bb = (px >= x0) & (px <= x1) & (py >= y0) & (py <= y1) & ~out
        if bb.any():
            ins = _inside(px[bb], py[bb], p)
            for h in holes:
                ins &= ~_inside(px[bb], py[bb], h)
            out[np.where(bb)[0][ins]] = True
    return out.reshape(X.shape)
