# Addendum — Sea Ice Concentration (AU_SI25) Access Investigation

**Date:** August 29, 2026 (post-Phase 4 closure, pre-Phase 5 kickoff)
**Related:** Carried-forward issue #3 (Sea Ice Concentration / TSM-SSC, deferred synthetic-only);
follow-up #2 from the Day 19-21 buffer block ("resolving Sea Ice Concentration's earthaccess
access issue, likely via direct NSIDC tooling")

## Outcome
Real AU_SI25 data access **achieved** — Day 21's "0 granules despite open collection metadata"
was not a genuine access/credentials/query-construction problem. Root-caused via a step-by-step
`earthaccess` parameter isolation (concept_id → cloud_hosted → temporal, tested independently):

- The collection's real concept-id is `C3243521560-NSIDC_CPRD` (cloud-hosted, `NSIDC_CPRD` provider).
- With zero filters, granules ARE returned (earliest available: June 2002).
- Sorting by `-end_date` showed the **most recent available granule ends 2025-09-01** — i.e. this
  collection's real archive currently only extends to ~August/September 2025, not into 2026.
- **Actual root cause:** data-ingestion latency specific to this product, not an access restriction.
  Day 21's `temporal=("2026-01-01", "2026-01-31")` query was simply asking for a period this
  collection hasn't ingested yet. The collection's "open-ended coverage" metadata describes the
  product line's intent, not a guarantee that any specific recent month is already published.
- Successfully downloaded one real granule from the confirmed-available window:
  `AMSR_U2_L3_SeaIce25km_B04_20250824.he5` (HDF-EOS5 format).

## File Structure Findings (new category, not yet integrated)
Inspected via `h5py` (installed via `conda install -c conda-forge h5py` into `oc-ecv-env`,
per Day 1's established pip/conda mixing caution for HDF-adjacent packages).

- **Two independent full grids in one file** — `HDFEOS/GRIDS/NpPolarGrid25km` (Northern
  Hemisphere) and `SpPolarGrid25km` (Southern Hemisphere) — a structural pattern not seen in
  any file this project has ingested so far (all prior files are single-hemisphere/single-swath).
- **New nesting convention:** `HDFEOS/GRIDS/<gridname>/Data Fields/<variable>` — a third distinct
  group-path pattern beyond the existing `geophysical_data`/`navigation_data` grouping and Day 21's
  groupless-swath case.
- **Target ECV variable:** `SI_25km_NH_ICECON_DAY` (and `SI_25km_SH_ICECON_DAY` for the southern
  grid) — daily sea ice concentration. All other fields in the grid (`06H_ASC`, `10V_DSC`, etc.)
  are raw multi-frequency/multi-polarization brightness temperatures per orbit pass — inputs, not
  the ECV itself. `ICEDIFF` is a secondary derived diagnostic, also not the primary target.
- **Georeferencing:** real `lat`/`lon` arrays present per grid (fixed polar-stereographic
  projection) — structurally closest to Day 21's groupless-swath 2D-lat/lon handling, not a
  from-scratch georeferencing problem if this is ever integrated.
- **Classification gap confirmed:** `SI_25km_NH_ICECON_DAY` does not match any existing
  `KNOWN_ECV_PREFIXES` entry — same recurring pattern as OSVW's Day 21 `u`/`v` gap; would need an
  explicit new prefix mapping.

## Decision
Given the September 15 MVP deadline and the non-trivial scope full integration would require
(hemisphere-grid selection UI/logic, new nested-group detection path, new prefix classification),
**deliberately not wiring this into `netcdf_reader.py`/the ingestion pipeline for the MVP.**
Synthetic coverage (established Day 19) remains the officially supported MVP path for Sea Ice
Concentration. This addendum exists so a post-MVP integration effort starts from a known working
access path and a fully mapped file structure, not from Day 21's original "access blocked" dead end.

## Cleanup Note
`check_au_si25_access.py` (diagnostic script) and `tmp/sea_ice_real/` (downloaded real granule)
are local-only artifacts, not committed — consistent with existing `tmp/` `.gitignore` handling.