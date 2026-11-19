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

More public seismic, found by us (not from the organisers), in seismic/ (or $DATA_DIR/seismic):
penobscot:     Penobscot 3D (Nova Scotia, Canada): stack with 7 reinterpreted horizons and 2 wells, HDF5, 2.3 GB, CC BY 4.0
parihaka:      Parihaka 3D (Taranaki Basin, New Zealand) with 6-class facies labels, 1.7 GB (Mendeley Data 10.17632/gnvyh3msrj.1,
               CC BY 4.0); the seismic is from NZ Petroleum and Minerals, who must be acknowledged, the labels are Chevron's
faultseg3d:    FaultSeg3D: 200 + 20 synthetic 128^3 seismic cubes with fault labels (Wu et al. 2019), from the authors'
               Google Drive; CC BY-NC 4.0 (non-commercial)

volve_databricks: Volve seismic, logs and more, from your own Databricks workspace (see the function); Equinor Open Data Licence

Not here, because they need your own acceptance of a licence: Smeaheia and
Sleipner 4D (co2datashare.org licence click-through). See docs/seismic-data.md.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
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


def _piece(url: str, fd: int, i: int, size: int, extra: dict | None = None) -> int:
    lo, hi = i * PIECE, min(size, (i + 1) * PIECE) - 1
    for attempt in range(30):
        try:
            with httpx.stream("GET", url, headers={**UA, **(extra or {}), "Range": f"bytes={lo}-{hi}"}, follow_redirects=True,
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


def _ranged(url: str, tmp, log, size: int, workers: int, label: str, extra: dict | None = None) -> None:
    """Fill tmp with url in 64 MB pieces over parallel connections; finished pieces are logged, so an interrupted run resumes."""
    done = {int(x) for x in log.read_text().split()} if log.exists() and tmp.exists() else set()
    todo = [i for i in range(-(-size // PIECE)) if i not in done]
    t0, got = time.time(), 0
    fd = os.open(tmp, os.O_RDWR | os.O_CREAT)
    os.ftruncate(fd, size)
    try:
        with ThreadPoolExecutor(workers) as pool, open(log, "a") as lg:
            for n, i in enumerate(as_completed(pool.submit(_piece, url, fd, i, size, extra) for i in todo)):
                lg.write(f"{i.result()}\n")
                lg.flush()
                got += PIECE
                if n % 20 == 19:
                    print(f"{label}: {len(done) + n + 1}/{len(done) + len(todo)} pieces, "
                          f"{got / (time.time() - t0) / 1e6:.1f} MB/s", flush=True)
    finally:
        os.close(fd)


def digest(path, algo: str = "md5") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while b := f.read(1 << 24):
            h.update(b)
    return h.hexdigest()


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
        _ranged(url, tmp, log, size, workers, path.name)
        if md5(tmp) != want:
            tmp.unlink()
            log.unlink()
            raise RuntimeError(f"{path.name}: md5 mismatch, deleted; run again")
        tmp.rename(path)
        log.unlink()
        print(f"{path.name}: {size / 1e6:.1f} MB, md5 ok", flush=True)
    return out


def mendeley(dataset: str, dest, only=(), workers: int = 6) -> list:
    """Files of a public Mendeley Data record into dest (all, or the names in only), resumable, sha256 checked."""
    files = httpx.get(f"https://data.mendeley.com/public-api/datasets/{dataset}/files?folder_id=root&version=1", headers=UA, timeout=60).json()
    out = []
    for f in files:
        name, size = f["filename"], f["size"]
        if only and name not in only:
            continue
        path = dest / name
        out.append(path)
        if path.exists() and path.stat().st_size == size:
            print(f"{name}: already here")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp, log = path.with_name(path.name + ".part"), path.with_name(path.name + ".pieces")
        _ranged(f["content_details"]["download_url"], tmp, log, size, workers, name)
        if digest(tmp, "sha256") != f["content_details"]["sha256_hash"]:
            tmp.unlink()
            log.unlink()
            raise RuntimeError(f"{name}: sha256 mismatch, deleted; run again")
        tmp.rename(path)
        log.unlink(missing_ok=True)
        print(f"{name}: {size / 1e6:.1f} MB, sha256 ok", flush=True)
    return out


def huggingface(repo: str, dest, workers: int = 6) -> list:
    """Every file of a Hugging Face dataset repo into dest, resumable, sha256 checked against the LFS id."""
    meta = httpx.get(f"https://huggingface.co/api/datasets/{repo}?blobs=true", headers=UA, timeout=60).json()
    out = []
    for f in meta["siblings"]:
        name = f["rfilename"]
        if name.startswith("."):
            continue
        path, size = dest / name, f["size"]
        out.append(path)
        if path.exists() and path.stat().st_size == size:
            print(f"{name}: already here")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/datasets/{repo}/resolve/main/{quote(name)}"
        tmp, log = path.with_name(path.name + ".part"), path.with_name(path.name + ".pieces")
        _ranged(url, tmp, log, size, workers, name)
        want = (f.get("lfs") or {}).get("sha256")
        if want and digest(tmp, "sha256") != want:
            tmp.unlink()
            log.unlink()
            raise RuntimeError(f"{name}: sha256 mismatch, deleted; run again")
        tmp.rename(path)
        log.unlink(missing_ok=True)
        print(f"{name}: {size / 1e6:.1f} MB{', sha256 ok' if want else ''}", flush=True)
    return out


def co2datashare(slug: str, dest, only=(), country: str = "Norway", affiliation: str = "Student (MSc thesis)") -> list:
    """Every resource of a co2datashare.org dataset. The site asks you to accept its licence (CC BY based: credit Equinor and Gassnova, no
    reselling), then a country and an affiliation, before each download; the owner of this repo accepted and gave both (LOG L035). Flow per
    resource: POST the page (CSRF) -> modal with a second CSRF token -> POST /multiple_download -> 302 to the file. Existing files are skipped."""
    import re

    base = "https://co2datashare.org"
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    got = []
    with httpx.Client(follow_redirects=False, timeout=httpx.Timeout(60, read=600)) as c:
        ids = sorted(set(re.findall(rf"/dataset/{slug}/resource/([0-9a-f-]{{36}})", c.get(f"{base}/dataset/{slug}").text)))
        for rid in ids:
            if only and not any(o in rid for o in only):
                continue
            page_url = f"{base}/dataset/{slug}/resource/{rid}"
            for attempt in range(3):
                try:
                    t1 = re.search(r'name="_csrf_token" value="([^"]+)"', c.get(page_url).text).group(1)
                    modal = c.post(page_url, data={"_csrf_token": t1}).text  # the licence step; answers with the download form
                    t2 = re.search(r'id="resource-download".*?name="_csrf_token" value="([^"]+)"', modal, re.S).group(1)
                    r = c.post(f"{base}/multiple_download", data={"_csrf_token": t2, "res_id": rid, "affiliation": affiliation, "country": country, "download": "Download"})
                    url = r.headers["location"]
                    name = url.split("?")[0].rsplit("/", 1)[-1]
                    f = dest / name
                    if f.exists() and f.stat().st_size > 0:
                        print(f"{name}: have it", flush=True)
                        break
                    tmp = f.with_suffix(f.suffix + ".part")
                    n, t0 = 0, time.time()
                    with c.stream("GET", url, follow_redirects=True) as d, open(tmp, "wb") as out:
                        d.raise_for_status()
                        for chunk in d.iter_bytes(1 << 22):
                            out.write(chunk)
                            n += len(chunk)
                    if not zipfile.is_zipfile(tmp):
                        raise httpx.HTTPError("the answer is not a zip")
                    tmp.rename(f)
                    print(f"{name}: {n / 1e6:.0f} MB, {n / 1e6 / (time.time() - t0):.1f} MB/s", flush=True)
                    got.append(f)
                    break
                except (httpx.HTTPError, AttributeError, KeyError) as e:
                    print(f"{rid[:8]}: attempt {attempt + 1} failed: {e}", flush=True)
                    time.sleep(5)
    (dest / "LICENCE.txt").write_text(
        f"co2datashare.org/dataset/{slug}\nLicence: CC BY 4.0 based (Gassnova and Equinor): credit Equinor and Gassnova, link to the terms, no reselling, covers all data in the set.\n"
        "Terms: https://co2datashare.org/smeaheia-dataset/static/SMEAHEIA DATASET LICENSE_Gassnova and Equinor.pdf (Smeaheia); see the dataset page for Sleipner.\n"
        "Accepted for this repo on 2026-11-19 by its owner.\n")
    return got


def smeaheia() -> None:
    co2datashare("smeaheia-dataset", DATA_DIR / "seismic" / "smeaheia")


def sleipner() -> None:
    co2datashare("sleipner-4d-seismic-dataset", DATA_DIR / "seismic" / "sleipner")


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


SEISMIC = DATA_DIR / "seismic"


def penobscot() -> None:
    zenodo(3924682, SEISMIC / "penobscot")


def parihaka() -> None:
    # the full training volume and its labels, redistributed on Mendeley Data (CC BY 4.0); a Hugging Face mirror
    # of the same survey holds only 196 of the 782 inlines
    mendeley("gnvyh3msrj", SEISMIC / "parihaka", only=("parihaka_data_train.npz", "parihaka_labels_train.npz"))


def faultseg3d() -> None:
    """The authors' Google Drive folder (gdown, run through uvx so nothing is added to the app's dependencies)."""
    subprocess.run(["uvx", "gdown", "--folder", "https://drive.google.com/drive/folders/1FcykAxpqiy2NpLP1icdatrrSQgLRXLP8",
                    "-O", str(SEISMIC / "faultseg3d")], check=True)


def volve_databricks() -> None:
    """Volve (Equinor, Equinor Open Data Licence) from a Unity Catalog volume in your own Databricks workspace.

    Equinor shares Volve through the Databricks Marketplace; the share's token does not give file access, so: in your
    workspace, Marketplace > Equinor > Volve > Get access, then put this JSON in .databricks next to this repo's README
    (it is git-ignored):  {"host": "https://adb-....azuredatabricks.net", "token": "dapi...", "volume": "/Volumes/<catalog>/public/volve"}
    With no VOLVE_GET it only lists the volume (sizes per folder); VOLVE_GET="seismic,Well_logs" downloads the files whose
    path contains any of those words, into seismic/volve/.
    """
    cfg = json.loads((Path(__file__).resolve().parent.parent / ".databricks").read_text())
    host, auth, root = cfg["host"].rstrip("/"), {"Authorization": f"Bearer {cfg['token']}"}, cfg["volume"].rstrip("/")

    def walk(path: str):
        token = None
        while True:
            r = httpx.get(f"{host}/api/2.0/fs/directories{quote(path)}", headers=auth, params={"page_size": 1000, **({"page_token": token} if token else {})}, timeout=120)
            r.raise_for_status()
            body = r.json()
            for e in body.get("contents", []):
                if e.get("is_directory"):
                    yield from walk(e["path"])
                else:
                    yield e["path"], int(e.get("file_size", 0))
            token = body.get("next_page_token")
            if not token:
                return

    files = list(walk(root))
    by_dir: dict = {}
    for path, size in files:
        top = "/".join(path[len(root):].lstrip("/").split("/")[:2])
        by_dir[top] = by_dir.get(top, 0) + size
    for d, n in sorted(by_dir.items(), key=lambda x: -x[1]):
        print(f"{n / 1e9:9.2f} GB  {d}")
    print(f"{sum(by_dir.values()) / 1e9:.1f} GB in {len(files)} files")
    want = [w for w in os.environ.get("VOLVE_GET", "").split(",") if w]
    for path, size in files:
        if not want or not any(w.lower() in path.lower() for w in want):
            continue
        dest = SEISMIC / "volve" / path[len(root):].lstrip("/")
        if dest.exists() and dest.stat().st_size == size:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp, log = dest.with_name(dest.name + ".part"), dest.with_name(dest.name + ".pieces")
        _ranged(f"{host}/api/2.0/fs/files{quote(path)}", tmp, log, size, 6, dest.name, auth)
        tmp.rename(dest)
        log.unlink(missing_ok=True)
        print(f"{dest.name}: {size / 1e6:.1f} MB", flush=True)


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
    # these three are extra public seismic and are not part of the default run: name them to fetch
    extra = {"penobscot": penobscot, "parihaka": parihaka, "faultseg3d": faultseg3d, "volve_databricks": volve_databricks, "smeaheia": smeaheia, "sleipner": sleipner}
    steps.update(extra)
    for w in sys.argv[1:] or [k for k in steps if k not in extra]:
        steps[w]()
