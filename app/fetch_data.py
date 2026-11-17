"""Downloads the open data the sketches use into data/ (or $DATA_DIR):

    uv run python fetch_data.py [sodir] [force2020]

sodir:     Sodir FactPages tables (CSV, NOLD 2.0) -> sodir/*.csv and ncs.duckdb (the copilot's database)
force2020: FORCE 2020 lithology competition well logs (CC BY 4.0, github.com/bolgebrygg/Force-2020-Machine-Learning-competition)
"""

import sys
import zipfile

import duckdb
import httpx

from common import DATA_DIR

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


if __name__ == "__main__":
    which = sys.argv[1:] or ["sodir", "force2020"]
    for w in which:
        {"sodir": sodir, "force2020": force2020}[w]()
