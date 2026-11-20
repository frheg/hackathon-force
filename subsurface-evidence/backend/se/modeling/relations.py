"""Relations admitted into the NCS representation, including non-predictive roles."""

from dataclasses import asdict, dataclass
from typing import Literal

from se.provenance.catalog import DATASETS


@dataclass(frozen=True)
class Relation:
    id: str
    inputs: tuple[str, ...]
    grain: str
    keys: tuple[str, ...]
    state: Literal["implemented", "research_only", "context_only", "benchmark_only", "blocked"]
    use: str
    guard: str


RELATIONS = (
    Relation("factpages-register", ("sodir_csv", "factpages"), "registry record", ("table", "NPDID"), "implemented",
             "One source lineage for CSV and DuckDB copies.", "Do not count snapshots or copies as independent evidence."),
    Relation("stratigraphic-report-interval", ("factpages", "completion", "atlas", "subsurface_derived"), "wellbore interval",
             ("wellbore", "measured depth", "formation/group"), "implemented",
             "Assign each depth-bearing extracted description once; formation first, group fallback.",
             "A keyword hit is a reported mention, not mineralogy. Keep unassigned and conflicting rows."),
    Relation("report-passage", ("completion", "official_text", "diskosqa"), "document page",
             ("document identity", "page", "wellbore"), "implemented",
             "Find traceable passages, with a separate retrieval benchmark.",
             "Deduplicate report versions; do not score geological models against benchmark answer text."),
    Relation("force-log-representations", ("force2020_las", "force2020_csv"), "wireline sample",
             ("wellbore", "measured depth", "curve", "unit"), "context_only",
             "Trace wireline measurements and benchmark representations.",
             "Same wells are not independent; hidden FORCE labels are evaluation only."),
    Relation("logs-core", ("force2020_csv", "realpore"), "core plug linked to a log sample",
             ("wellbore", "measured depth", "depth tolerance"), "research_only",
             "Fit porosity and log permeability on measured plugs; score on whole wells and spatial blocks.",
             "Record depth offset, assay/unit and curve availability. Do not extrapolate to unlogged volumes."),
    Relation("core-context", ("realpore", "factpages"), "core plug within a recorded core interval",
             ("NPDID", "measured depth", "core top/base"), "research_only",
             "Compare lab coverage with registry intervals and identify overlap or unit issues.",
             "Core sampling is selective, and matching a core interval does not establish assay comparability."),
    Relation("rock-physics-core", ("force2020_csv", "realpore", "factpages"), "core plug and measured sonic sample",
             ("NPDID", "measured depth", "curve units", "seabed depth"), "research_only",
             "Test physics transforms against identical raw inputs and fixed density porosity.",
             "No predicted shear or fluid labels; derived variables are not independent evidence."),
    Relation("gn1101-time-depth", ("smeaheia", "factpages"), "well site and horizon pick",
             ("site", "ED50 UTM 31N", "horizon", "TWT", "TVDSS"), "research_only",
             "Tie seabed and picked times to subsea depth with a fitted interval velocity experiment.",
             "Two sites and publisher picks are not independent validation; do not activate the 3D depth transform."),
    Relation("smeaheia-depth-support", ("smeaheia", "factpages", "realpore", "force2020_csv", "subsurface_derived"),
             "survey candidate and source depth span", ("NPDID", "exact borehole label", "MD", "TWT datum"), "implemented",
             "Inventory local controls and source coverage by well; prioritize acquisition.",
             "An MD span is not a time-depth tie; keep parent and T2 distinct."),
    Relation("seismic-wellhead-screen", ("smeaheia", "sleipner", "factpages", "realpore", "force2020_csv", "subsurface_derived"),
             "registry wellhead within a seismic index hull", ("NPDID", "survey XY CRS", "indexed trace geometry"),
             "implemented", "Find candidate wells with source overlap for tie work.",
             "Laterals can enter from outside the hull, holes can lie inside it, and no depth-level alignment is established."),
    Relation("sleipner-time-lapse", ("sleipner", "sleipner_benchmark_2019", "factpages"), "survey vintage and reservoir horizon",
             ("processing family", "trace location", "time/depth reference", "horizon"), "context_only",
             "Compare overlays and use published boundaries and velocity trends as interpretation controls.",
             "Do not treat processing variants as independent, or a reference geomodel as measured truth."),
    Relation("sleipner-porosity-transfer", ("sleipner_benchmark_2019", "realpore", "force2020_csv", "factpages"),
             "interpreted LAS porosity at well MD", ("NPDID", "measured depth", "curve and units"),
             "research_only", "Compare log-to-core estimates with PHIF on complete curve rows outside the fit area.",
             "PHIF may be derived from the same logs; agreement is not a measured porosity validation."),
    Relation("field-outcomes", ("factpages",), "field and month or named well test",
             ("field/field NPDID", "period", "wellbore NPDID", "test interval"), "context_only",
             "Use production, reserves and DSTs for their own targets and as higher-level constraints.",
             "Field totals and completion/test choices are not voxel labels; train at the target's support."),
    Relation("operational-context", ("volve", "factpages"), "drilling activity",
             ("wellbore", "operation interval", "time"), "context_only",
             "Keep operation/drilling history alongside the physical model as a separate outcome stream.",
             "Volve report extracts are not the full Volve seismic/LAS release and do not give independent coverage."),
    Relation("external-seismic", ("f3", "adele", "parihaka", "penobscot"), "survey patch",
             ("survey", "processing domain", "trace/sample index"), "benchmark_only",
             "Benchmark shape/attribute methods and possible pretraining without claiming NCS labels.",
             "Split by survey or spatial block and test on NCS controls before transferring."),
    Relation("synthetic-faults", ("faultseg3d",), "synthetic seismic patch", ("generator case", "patch"),
             "benchmark_only", "Benchmark fault structure methods.",
             "Synthetic domain and non-commercial licence: never use as a measured NCS observation."),
    Relation("surface-remote-sensing", ("ksat",), "surface scene", ("acquisition time", "footprint", "product"),
             "blocked", "Potential surface context if a licensed, interpretable dataset is supplied.",
             "No files available; do not map SAR pixels to subsurface properties without a physical link."),
)


def relation_plan() -> dict:
    catalog_ids = {d["id"] for d in DATASETS}
    covered = {source for r in RELATIONS for source in r.inputs}
    if covered != catalog_ids:
        raise ValueError(f"relation coverage disagrees with catalogue: missing={sorted(catalog_ids - covered)}, unknown={sorted(covered - catalog_ids)}")
    return {
        "schema_version": 1,
        "scope": "Registered roles and join contracts, not an assertion that all bytes are ingested or all relations validated.",
        "catalog_sources": len(catalog_ids),
        "entities": {
            "wellbore_interval": "NPDID/borehole identity and MD bounds; trajectory needed for true 3D location",
            "seismic_observation": "survey, vintage, processing, XY CRS and time/depth datum; amplitude or interpretive pick",
            "regional_volume": "datum-aligned geometry and a separate target field with a valid-domain mask",
            "document_claim": "document version/source hash, page and extracted observation plus uncertainty",
            "field_time_series": "field identifier, time and production/test support; not a voxel measurement",
        },
        "relations": [asdict(r) for r in RELATIONS],
    }
