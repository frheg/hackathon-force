# Public seismic beyond the event data

What we fetched on 19 November 2026 to go with the two cubes in `docs/seismic-guide.md` (Adele, F3), what is blocked
behind a sign-in or a licence, and where each one is useful. All of it lives under `data/seismic/` (git-ignored);
`uv run python fetch_data.py <name>` fetches it again.

## Downloaded

| Name | Where | Size | Licence | What it is |
|---|---|---|---|---|
| Parihaka 3D | `data/seismic/parihaka/` | 1.7 GB | CC BY 4.0 (Mendeley Data 10.17632/gnvyh3msrj.1); the survey is public-domain New Zealand government data, the labels come from Chevron | Taranaki Basin, New Zealand. 1,006 samples x 782 x 590 float32 (order: time, then the two map directions) and six facies labels per sample |
| Penobscot 3D | `data/seismic/penobscot/` | 2.3 GB | CC BY 4.0 (Zenodo 3924682) | Scotian Shelf, Nova Scotia. HDF5: 601 inlines x 1,501 samples x 481 crosslines, 4 ms, 0 to 6,000 ms, with dense labels between 7 interpreted horizons; `horizons.zip` holds the horizon picks |
| FaultSeg3D | `data/seismic/faultseg3d/` | 2.1 GB; 200 training cubes (`train/seis`, `train/fault`) and 20 validation, 128^3 float32 each | CC BY-NC 4.0 (non-commercial) | Wu, Liang, Shi and Fomel 2019: 200 training and 20 validation synthetic 128 x 128 x 128 cubes with binary fault labels, raw float32 `.dat` files in `seis/` and `fault/` |

Parihaka labels (rebased by the publisher from 1 to 6): 1 basement and other, 2 slope mudstone A, 3 mass transport deposit,
4 slope mudstone B, 5 slope valley, 6 submarine canyon system. Shares of the samples: 15, 42, 4, 29, 1, 9 %. Unlike
F3's labels (Dutch stratigraphic groups) these are seismic-geomorphology units, which is why they are the better
candidate for ideas that carry over to another basin.

A Hugging Face copy of Parihaka (`SRaha23/parihaka-taranaki`) claims 782 inlines but holds only 196; we use the full
Mendeley volume instead.

## Needs you (a sign-in or a licence you accept)

| Name | Why it is not fetched | How |
|---|---|---|
| Volve (Equinor) | Tried on 19 November 2026 and closed: the share token (`Volve_Data_Village.share`, from the Marketplace "Get credentials" button) lists two volumes (`volve`, `volvezipfiles`) but no file endpoint answers, and importing the share into a workspace as a catalog (`volve_catalogue`) gives no `public` schema (`SCHEMA_NOT_FOUND`). Microsoft's docs say volumes are not supported for token recipients. The full Volve release is about 5 TB in 40,000 files, so only slices would ever have been fetched | Ask Equinor's data contact (named on equinor.com/energy/volve-data-sharing), or look for other Volve listings on Equinor's Marketplace provider page. `fetch_data.py volve_databricks` (reads a git-ignored `.databricks` with host, token and volume path) is kept for a workspace that does expose the volume, but it was never run against real data |
| Smeaheia (Gassnova, CO2 storage, Hordaland Platform, Norway) | co2datashare.org click-through licence: 3D seismic (1.9 GB), 2D lines (2.7 GB), horizons, fault sticks, well logs for 32/2-1 and 32/4-1, velocity maps, simulation models | Read and accept the licence at co2datashare.org/dataset/smeaheia-dataset (DOI 10.11582/2021.00012) |
| Sleipner 4D (Equinor, CO2 storage, Norway) | Same portal and kind of licence: ten 3D vintages from 1994 to 2010, 1.5 to 2.2 GB each | co2datashare.org/dataset/sleipner-4d-seismic-dataset |

## Not fetched

- Kerry-3D and other New Zealand surveys: the SEG wiki that lists the links sits behind a bot challenge, which we do not bypass.
- CRACKS (fault labels on 400 F3 inlines) and Thebe (Exmouth Plateau, NW Australia): found in searches, not checked.
- FORCE 2020 competition sets (synthetics, the Ichthys training cube): on TerraNubis in OpendTect format, not checked.

## Acknowledgements the licences ask for

New Zealand Petroleum and Minerals for Parihaka and Kerry; Geoscience Australia for Adele; dGB Earth Sciences and
TNO for F3; the Penobscot Interpretation Dataset authors (Baroni et al.); the FaultSeg3D authors (Wu et al., GEOPHYSICS 84(3)).

## Downloaded 2026-11-19: open seismic over the Norwegian North Sea (co2datashare.org)

| Dataset | Where | What | Licence and credit |
|---|---|---|---|
| Smeaheia (Gassnova, Equinor) | `data/seismic/smeaheia/` | 3D surveys GN1101 and TNE01 (SEG-Y, ED50 UTM 31N), 2D lines, horizons, surfaces, interval velocity maps, fault sticks, well logs 32/2-1 and 32/4-1, reports, simulation models. DOI 10.11582/2021.00012 | CC BY 4.0 based: credit Equinor and Gassnova, no reselling. Credit shown in the app. |
| Sleipner 4D (Equinor) | `data/seismic/sleipner/` | Ten 3D vintages 1994 to 2010 over the Utsira Formation CO2 injection | Same portal and licence family; see the dataset page. |

Fetch: `app/fetch_data.py smeaheia` and `sleipner`. The site asks for acceptance, a country and an affiliation per download; the repo owner accepted and gave them (LOG L035).

## Next Norwegian-shelf acquisitions (2026-11-19)

| Candidate | Verified contents / access | Role and limits |
|---|---|---|
| [MSM98/2 Norwegian Sea](https://doi.org/10.1594/PANGAEA.973650) | 23 high-resolution 2D multichannel profiles, stacked and post-stack migrated SEG-Y. [File list](https://doi.pangaea.de/10.1594/PANGAEA.973650?format=html) includes individual files, sizes and checksums; PANGAEA says an account is required for downloading. | Best new source for a processed 2D section in the Norwegian Sea. Inspect one line first (e.g. `MSM98-2_P5008_mig.sgy`, 37 MB). Targets shallow margin/landslide structures, not petroleum reservoir or clay labels. Check CRS, time datum, and well overlap before placement or correlation. |
| [UiT mid-Norway / Lofoten–Vesterålen](https://doi.org/10.18710/DWOUPL) | 62 single-channel 2D lines from five surveys across 64–69°N. CC0 1.0; DataverseNO lists unrestricted SEG-Y files, e.g. [00-001 part 1](https://dataverse.no/api/access/datafile/172935), about 7.5 MB. Published unprocessed and unmigrated. | Immediate small pilot for 2D trace ingest and regional coverage in 3D. Not comparable amplitude to migrated surveys without processing, and no validated tie demonstrated. |
| [Diskos released 3D](https://www.sodir.no/en/facts/data-and-analyses/release-of-data/access-to-released-data/) | Members download; non-members order through Diskos Public Portal. Public inventory is not amplitude access. [Sodir names FIN13](https://www.sodir.no/aktuelt/nyheter/generelle-nyheter/2024/stort-areal-med-nye-frigitte-datasett-i-barentshavet/) as released Barents 3D. | Best route to additional NCS **3D**, but screen released post-stack products against target wells and checkshots first. Request one survey/subvolume with navigation, CRS, processing and vertical-domain metadata. Do not select FIN13 solely because it is listed. |
| [SINTEF Johansen](https://www.sintef.no/projectweb/matmora/downloads/johansen/) | Downloadable model grids, faults, porosity/permeability properties and simulation inputs (ODbL/DbCL). No amplitude volume on this page. | Interpreted regional context and comparison model only; model properties are not new independent observations. |

Acquisition gate: **target formation overlap → tied wells with directional surveys and depth/time controls → known datum, CRS and processing → disk/licence check → one small product first**. For 2D use a georeferenced curtain with along-line distance, not a 3D cube. Display new surveys as context; enable prediction only after an ablation on held-out wells or survey areas. No new binaries were downloaded for this shortlist.

### Depth controls to request first

The [Diskos wells catalogue](https://www.sodir.no/diskos/wells/) lists original well-path survey points and well seismic (VSP and velocity). Catalogue presence is not confirmed file access. Prioritize:

- **GN1101:** Checkshots or VSP and directional survey for **32/2-1** (NPDID 5839); resolve the **32/4-1 T2** borehole and survey separately from parent site ID 2918. Request GN1101's final processing datum and workbook horizon version. These controls can test the existing time-reference conflict, not provide a new independent held-out well by themselves.
- **TNE01:** Request the independent raw control underlying the documented **31/3-1** tie (NPDID 20). **31/3-3** (NPDID 447) is a separate candidate for a test using logs and core. Its wellhead overlaps the indexed survey, but that is not an established tie.

For each package ask for shot times and corrections, receiver MD/TVD, MD and vertical reference elevations, units, datums, survey/vintage and file identifiers. Keep independent control wells out of fitting. Do not treat already depth-converted horizons, velocity maps derived from the same control wells, or releases of the same survey as external validation.
