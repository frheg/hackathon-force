"""Build the earth model for one region, P1-P6 in order (PLAN P8, LOG L074). Run: EARTH_REGION=<name> uv run --frozen python -m se.earth.run

Each step's outcome (done, skipped with the reason, or failed with the error) goes to <EARTH>/run_report.json, so a region with less data
says what it could not build instead of stopping silently.
"""
import json
import time
import traceback

from se.config import EARTH, PILOT, REGION

STEPS = [
    ("frame", "se.earth.frame"), ("tops", "se.earth.tops"), ("column", "se.earth.column"), ("surfaces", "se.earth.surfaces"), ("grid", "se.earth.grid"),
    ("pressure", "se.earth.pressure"), ("temperature", "se.earth.temperature"), ("lithology", "se.earth.lithology"), ("poroperm", "se.earth.poroperm"),
    ("fluids", "se.earth.fluids"), ("rpt", "se.earth.rpt"), ("factors", "se.earth.factors"), ("targets", "se.earth.targets"), ("volumes", "se.earth.volumes"), ("rules", "se.earth.rules"), ("export", "se.earth.export"), ("gamma", "se.earth.gamma"),
]


class Skip(Exception):
    """A step that cannot run for lack of data in this region (not an error)."""


def main(only=None):
    import importlib

    EARTH.mkdir(parents=True, exist_ok=True)
    rp = EARTH / "run_report.json"
    rep = json.loads(rp.read_text()) if rp.exists() else {}
    rep.update({"region": REGION, "box": PILOT})
    for name, mod in STEPS:
        if only and name not in only:
            continue
        t0 = time.time(); print(f"[{REGION}] {name} ...", flush=True)
        try:
            out = importlib.import_module(mod).build()
            rep[name] = {"status": "done", "seconds": round(time.time() - t0, 1), "summary": _short(out)}
        except Exception as e:
            if type(e).__name__ == "Skip":  # by name: under "python -m" this module is __main__, so the class a step raises is another copy
                rep[name] = {"status": "skipped", "why": str(e)}; print(f"[{REGION}] {name}: skipped {e}", flush=True); rp.write_text(json.dumps(rep, indent=1, default=str)); continue
            rep[name] = {"status": "failed", "error": f"{type(e).__name__}: {e}"[:400], "trace": traceback.format_exc()[-1500:]}
        print(f"[{REGION}] {name}: {rep[name]['status']} {rep[name].get('why') or rep[name].get('error') or ''}", flush=True)
        rp.write_text(json.dumps(rep, indent=1, default=str))
    return rep


def _short(o):
    if isinstance(o, tuple):
        o = o[0]
    if isinstance(o, dict):
        return {k: v for k, v in o.items() if isinstance(v, (int, float, str, bool)) or k in ("cv",) and False}
    if isinstance(o, list):
        return {"items": len(o)}
    return str(type(o).__name__)


if __name__ == "__main__":
    import sys

    main(sys.argv[1:] or None)
