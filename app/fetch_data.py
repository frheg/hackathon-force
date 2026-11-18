"""Downloads the open data the sketches use into data/ (or $DATA_DIR):

    uv run python fetch_data.py [sodir] [force2020] [diskosqa] [volve] [seismic]

sodir:     Sodir FactPages tables (CSV, NOLD 2.0) -> sodir/*.csv and ncs.duckdb (most apps' database)
force2020: FORCE 2020 lithology competition well logs (CC BY 4.0, github.com/bolgebrygg/Force-2020-Machine-Learning-competition)
diskosqa:  DISKOS-QA benchmark (NLOD 2.0); then `python -m sketches.reports` builds the passage index
volve:     Volve daily drilling reports (CC BY 4.0, Hugging Face)
seismic:   F3 seismic with facies labels (CC BY 4.0, Zenodo), about 1 GB
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
    steps = {"sodir": sodir, "force2020": force2020, "diskosqa": diskosqa, "volve": volve, "seismic": seismic}
    for w in sys.argv[1:] or list(steps):
        steps[w]()
