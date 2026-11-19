"""Index every Sleipner 4D vintage in data/seismic/sleipner/*.zip (the full stack of each), then delete the extracted SEG-Y.

File names: YYpPP = survey year YY, processing year PP (94p01 = 1994 survey, processed 2001). Only vintages with the same processing (PP) share
amplitudes that can be subtracted, so the time-lapse views offer those as baselines. Run: uv run python -m se.seismic.sleipner
"""
import re
import shutil
import zipfile

from se.config import DATA
from se.seismic.index import SEIS, build

ZIPS = DATA / "seismic" / "sleipner"


def year(yy: str) -> int:
    return 1900 + int(yy) if int(yy) > 50 else 2000 + int(yy)


def run() -> list:
    done = []
    tmp = ZIPS / "_tmp"
    for z in sorted(ZIPS.glob("*.zip")):
        m = re.fullmatch(r"(\d\d)p(\d\d)", z.stem)
        if not m:
            continue
        sid = f"sleipner_{z.stem}"
        if (SEIS / sid / "meta.json").exists():
            print(sid, "indexed already", flush=True)
            continue
        with zipfile.ZipFile(z) as zf:
            names = [n for n in zf.namelist() if re.search(r"ful(\.sgy|\.segy)?$", n.lower())]  # the 2010 vintage has no extension
            if not names:
                print(sid, "has no full stack, skipped", [n for n in zf.namelist() if n.endswith(".sgy")][:3], flush=True)
                continue
            zf.extract(names[0], tmp)
        f = tmp / names[0]
        meta = build(f, sid, f"Sleipner {year(m.group(1))} (processed {year(m.group(2))})", "sleipner", extra={"survey_year": year(m.group(1)), "processing": m.group(2)})
        print(sid, meta["traces_kept"], "traces,", meta["samples"], "samples, dt", meta["dt_ms"], "ms", flush=True)
        shutil.rmtree(tmp, ignore_errors=True)
        done.append(sid)
    return done


if __name__ == "__main__":
    run()
