"""Downloads the open data the sketches use into data/ (or $DATA_DIR):

    uv run python fetch_data.py [sodir] [force2020] [diskosqa] [volve] [seismic] [realpore] [force2020_las]
                                [text] [adele] [completion]

sodir:     Sodir FactPages tables (CSV, NOLD 2.0) -> sodir/*.csv and ncs.duckdb (most apps' database)
force2020: FORCE 2020 lithology competition well logs (CC BY 4.0, github.com/bolgebrygg/Force-2020-Machine-Learning-competition)
diskosqa:  DISKOS-QA benchmark (NLOD 2.0); then `python -m sketches.reports` builds the passage index
volve:     Volve daily drilling reports (CC BY 4.0, Hugging Face)
seismic:   F3 seismic with facies labels (CC BY 4.0, Zenodo), about 1 GB

The datasets the organisers sent by mail go in official/ (or $DATA_DIR/official), apart from the ones found earlier
(all CC BY 4.0, Zenodo; each file's md5 is checked, broken downloads resume):
realpore:      core porosity, permeability and rock type, 1,240 wells (credit GeoProvider, http://geoprovider.no/)
force2020_las: the FORCE 2020 wells as LAS files (official/force2020), plus Sodir casing depths and lithostratigraphy sheets
text:          OCR text of public Norwegian (Diskos, relinquishment), UK and Dutch reports, 5.8 GB
adele:         Adele 3D seismic (NW Australia, SEG-Y, 3.3 GB), the FORCE 2020 fault competition cube
completion:    4,462 NCS wellbore completion reports as PDF and JSON, 112 GB in four tar parts, unpacked to
               official/completion_reports/ (the parts are deleted after a clean unpack)
"""

import hashlib
import os
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import duckdb
import httpx

from common import DATA_DIR

OFFICIAL = DATA_DIR / "official"

UA = {"User-Agent": "hackathon-prototype/0.1 (FORCE VibeCode)"}
FACTPAGES = (
    "https://factpages.sodir.no/public?/Factpages/external/tableview/{t}"
    "&rs:Command=Render&rc:Toolbar=false&rc:Parameters=f&IpAddress=not_used&CultureCode=en&rs:Format=CSV&Top100=false"
)
# FactPages table -> table name in ncs.duckdb
TABLES = {
    "field": "field",
    "field_description": "field_description",
    "field_reserves": "field_reserves",
    "field_production_monthly": "field_production_monthly",
    "wellbore_exploration_all": "wellbore_exploration",
    "wellbore_development_all": "wellbore_development",
    "discovery": "discovery",
    "licence": "licence",
    "company": "company",
    # well detail: tops, casing and leak-off tests, mud weights, drill-stem tests, cores, the drilling history text,
    # and links to the published well reports (PDF)
    "wellbore_formation_top": "wellbore_formation_top",
    "wellbore_casing_and_lot": "wellbore_casing_and_lot",
    "wellbore_mud": "wellbore_mud",
    "wellbore_dst": "wellbore_dst",
    "wellbore_core": "wellbore_core",
    "wellbore_history": "wellbore_history",
    "wellbore_document": "wellbore_document",
    # infrastructure and the undeveloped resource base
    "facility_fixed": "facility_fixed",
    "discovery_reserves": "discovery_reserves",
    "discovery_description": "discovery_description",
    "field_investment_yearly": "field_investment_yearly",
    "field_operator_hst": "field_operator_hst",
    "strat_litho_overview": "strat_litho_overview",
}
FORCE = "https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition/raw/master/lithology_competition/data/"


def download(url: str, dest) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, headers=UA, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    print(f"{dest}: {dest.stat().st_size / 1e6:.1f} MB")


def md5(path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while b := f.read(1 << 24):
            h.update(b)
    return h.hexdigest()


PIECE = 64 << 20  # large files come in 64 MB pieces over parallel connections: Zenodo gives each one 2 to 3 MB/s


def _piece(url: str, fd: int, i: int, size: int) -> int:
    lo, hi = i * PIECE, min(size, (i + 1) * PIECE) - 1
    for attempt in range(30):
        try:
            with httpx.stream("GET", url, headers={**UA, "Range": f"bytes={lo}-{hi}"}, follow_redirects=True,
                              timeout=120) as r:
                r.raise_for_status()
                if r.status_code != 206:
                    raise httpx.HTTPError("no range support")
                pos = lo
                for chunk in r.iter_bytes(1 << 20):
                    os.pwrite(fd, chunk, pos)
                    pos += len(chunk)
            if pos == hi + 1:
                return i
            raise httpx.HTTPError(f"short piece {pos - lo} of {hi - lo + 1}")
        except httpx.HTTPError as e:
            if attempt == 29:
                raise
            time.sleep(min(60, 3 * (attempt + 1)))
    return i


def zenodo(record: int, dest, skip=(), workers: int = 10) -> list:
    """Every file of a Zenodo record into dest, checked by md5. Files download as 64 MB pieces in parallel; finished
    pieces are logged next to the file, so an interrupted run resumes. Returns the paths."""
    meta = httpx.get(f"https://zenodo.org/api/records/{record}", headers=UA, timeout=60).json()
    out = []
    for f in meta["files"]:
        if f["key"] in skip:
            continue
        path, size = dest / f["key"], f["size"]
        want = f["checksum"].removeprefix("md5:")
        out.append(path)
        if path.exists() and path.stat().st_size == size:
            print(f"{path.name}: already here")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://zenodo.org/records/{record}/files/{quote(f['key'])}?download=1"
        tmp, log = path.with_name(path.name + ".part"), path.with_name(path.name + ".pieces")
        done = {int(x) for x in log.read_text().split()} if log.exists() and tmp.exists() else set()
        todo = [i for i in range(-(-size // PIECE)) if i not in done]
        t0, got = time.time(), 0
        fd = os.open(tmp, os.O_RDWR | os.O_CREAT)
        os.ftruncate(fd, size)
        try:
            with ThreadPoolExecutor(workers) as pool, open(log, "a") as lg:
                for n, i in enumerate(as_completed(pool.submit(_piece, url, fd, i, size) for i in todo)):
                    lg.write(f"{i.result()}\n")
                    lg.flush()
                    got += PIECE
                    if n % 20 == 19:
                        print(f"{path.name}: {len(done) + n + 1}/{len(done) + len(todo)} pieces, "
                              f"{got / (time.time() - t0) / 1e6:.1f} MB/s", flush=True)
        finally:
            os.close(fd)
        if md5(tmp) != want:
            tmp.unlink()
            log.unlink()
            raise RuntimeError(f"{path.name}: md5 mismatch, deleted; run again")
        tmp.rename(path)
        log.unlink()
        print(f"{path.name}: {size / 1e6:.1f} MB, md5 ok", flush=True)
    return out


def realpore() -> None:
    zenodo(4723018, OFFICIAL / "realpore")


def force2020_las() -> None:
    d = OFFICIAL / "force2020"
    for p in zenodo(4351156, d):
        if p.suffix == ".zip":
            with zipfile.ZipFile(p) as z:
                z.extractall(d)
            p.unlink()


def text() -> None:
    zenodo(10775273, OFFICIAL / "text")


def adele() -> None:
    zenodo(4299758, OFFICIAL / "adele")


def completion() -> None:
    d = OFFICIAL / "completion_reports"
    parts = sorted(p for p in zenodo(24320092, d) if ".tar.part" in p.name)
    if parts:  # the tar is split in plain byte ranges: concatenate and unpack, then drop the parts
        subprocess.run(f"cat {' '.join(repr(str(p)) for p in parts)} | tar -x -C {str(d)!r}", shell=True, check=True)
        for p in parts:
            p.unlink()
        print("unpacked to", d)


def sodir() -> None:
    for t in TABLES:
        download(FACTPAGES.format(t=t), DATA_DIR / "sodir" / f"{t}.csv")
    # build next to the old one and swap, so the copilot never reads a half-built file
    tmp = DATA_DIR / "ncs.duckdb.new"
    tmp.unlink(missing_ok=True)
    db = duckdb.connect(str(tmp))
    for t, name in TABLES.items():
        db.execute(
            f"create table {name} as select * "
            f"from read_csv('{DATA_DIR / 'sodir' / t}.csv', header=true, dateformat='%d.%m.%Y', sample_size=-1)"
        )
        db.execute(f"alter table {name} drop column if exists DatesyncNPD")
        print(name, db.execute(f"select count(*) from {name}").fetchone()[0], "rows")
    db.close()
    tmp.rename(DATA_DIR / "ncs.duckdb")


def force2020() -> None:
    d = DATA_DIR / "force2020"
    download(FORCE + "train.zip", d / "train.zip")  # train.csv: 98 wells with lithology labels
    with zipfile.ZipFile(d / "train.zip") as z:
        z.extractall(d)
    (d / "train.zip").unlink()
    # hidden_test.csv: 10 more wells with labels, kept out of training; penalty_matrix.npy: the competition's score
    for f in ("hidden_test.csv", "penalty_matrix.npy"):
        download(FORCE + f, d / f)


def diskosqa() -> None:
    """DISKOS-QA: 1,027 question-answer pairs over Diskos well reports, with their source passages (NLOD 2.0)."""
    download(
        "https://raw.githubusercontent.com/georgeghon/DISKOS-QA/main/benchmark/dataset/FORCE_QA_public_final.csv",
        DATA_DIR / "diskosqa" / "diskos_qa.csv",
    )


def volve() -> None:
    """Volve's 1,759 daily drilling reports as structured WITSML (CC BY 4.0 copy by bengsoon on Hugging Face)."""
    download(
        "https://huggingface.co/datasets/bengsoon/volve_daily_drilling_report/resolve/main/data/all-00000-of-00001.parquet",
        DATA_DIR / "volve" / "ddr.parquet",
    )


def seismic() -> None:
    """F3 Netherlands seismic with facies labels (Alaudah et al., Zenodo 3755060; 1 GB, CC BY 4.0): a public stand-in
    for the event's seismic."""
    d = DATA_DIR / "seismic" / "f3"
    download("https://zenodo.org/api/records/3755060/files/data.zip/content", d / "data.zip")
    with zipfile.ZipFile(d / "data.zip") as z:
        z.extractall(d)
    (d / "data.zip").unlink()


if __name__ == "__main__":
    steps = {"sodir": sodir, "force2020": force2020, "diskosqa": diskosqa, "volve": volve, "seismic": seismic,
             "realpore": realpore, "force2020_las": force2020_las, "text": text, "adele": adele,
             "completion": completion}
    for w in sys.argv[1:] or list(steps):
        steps[w]()
