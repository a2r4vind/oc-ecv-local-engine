# Development & Testing Scripts

The Python files listed below live in `backend/`'s root directory alongside
the actual application package (`api/`, `processing/`, `ingestion/`,
`caching/`, `validation/`, `config/`). They are **not part of the shipped
application** — none are imported by `api/server.py`, and none are bundled
into the PyInstaller sidecar binary. They are one-off development, testing,
and benchmarking tools used to build and validate the application across
this project's 56-day development cycle, kept for provenance and
reproducibility rather than deleted.

For the story behind any given script — why it was built, what it found —
see the corresponding `docs/Day_N_Summary_Report___OC-ECV_Local_Engine.md`.

## Sample data generators
| Script | Purpose | Reference |
|---|---|---|
| `generate_sample_data.py` | Synthetic flat-grid Ocean Color NetCDF fixture (chlor_a, Rrs_443, Rrs_555) | Day 3 |
| `generate_sample_data_all_ecv.py` | Synthetic fixture covering all 13 ECV categories | Days 19-21 |
| `generate_large_sample_data.py` | 1.8GB synthetic large-grid fixture for stress testing | Days 6-7 |

## Real satellite data acquisition (via `earthaccess`)
| Script | Purpose | Reference |
|---|---|---|
| `download_batch_real_data.py` | Downloads a 25-granule real MODIS-Aqua L2 OC batch | Days 6-7 |
| `download_sst_sample.py` | Downloads real SST granule | Day 20 |
| `download_iop_sample.py` | Downloads real CDOM/IOP granule | Days 19-21 |
| `download_ssh_sample.py` | Downloads real SSH (SWOT) granule | Days 19-21 |
| `download_sss_sample.py` | Downloads real SSS (SMAP) granule | Days 19-21 |
| `download_osvw_sample.py` | Downloads real OSVW (CCMP wind) granule | Days 19-21 |
| `check_au_si25_access.py` | Diagnostic script investigating Sea Ice Concentration data access (AU_SI25) — documents the deferred-ECV investigation | Days 19-21 |

## Benchmarking & performance
| Script | Purpose | Reference |
|---|---|---|
| `benchmark_ingestion.py` | Per-stage ingestion timing/memory profiling | Days 6-7 |
| `batch_benchmark.py` | Directory-level batch ingestion timing/throughput | Days 6-7 |
| `benchmark_day16.py` | Single-file multi-variable threading benchmark | Day 16 |
| `benchmark_day17.py` | Cross-file concurrency safety/performance benchmark | Day 17 |
| `day44_memory_leak_session.py` | WebGL/RSS memory monitoring harness (UI-driven and backend-stress modes) | Days 44-45 |

## Regression & verification
| Script | Purpose | Reference |
|---|---|---|
| `day19_full_ecv_regression.py` | Full 13-ECV pipeline regression | Days 19-21 |
| `day43_full_stack_regression.py` | Full-stack endpoint regression (ingest → stats → raster → timeseries → histogram → scatter → export → history) | Day 43 |
| `verify_day38_geotiff_writer.py` | GeoTIFF export round-trip verification | Day 38 |
| `verify_day38_netcdf_writer.py` | NetCDF export round-trip verification | Day 38 |

## Note on running these scripts
Most of these scripts import sibling packages (`processing`, `config`, etc.)
and rely on Python's default behavior of adding a directly-executed script's
own directory to `sys.path`. They must be run from `backend/`'s root
(`python <script_name>.py`), not via a relative or absolute path from
another working directory, and not after being moved to a different folder
without adjusting imports — consistent with the sibling-import path
convention established since Day 4.