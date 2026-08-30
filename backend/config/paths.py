"""
Centralized test-data path resolution. All scripts import from here instead
of hardcoding relative string paths — avoids the recurring risk (flagged
since Day 5/curl-testing) where relative paths silently resolve against
whatever the current working directory happens to be, rather than a fixed
project-relative location.
"""
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
TEST_DATA_ROOT = PROJECT_ROOT / "test_data"

SYNTHETIC_DIR = TEST_DATA_ROOT / "synthetic"
REAL_DIR = TEST_DATA_ROOT / "real"

# Individual dataset paths — one source of truth
SAMPLE_OCEANCOLOR = SYNTHETIC_DIR / "sample_oceancolor.nc"
SAMPLE_ALL_ECV = SYNTHETIC_DIR / "sample_all_ecv.nc"
LARGE_SAMPLE_OCEANCOLOR = SYNTHETIC_DIR / "large_sample_oceancolor.nc"
TEST_SWATH = SYNTHETIC_DIR / "test_swath.nc"

REAL_BATCH_DATA = REAL_DIR / "real_batch_data"
REAL_IOP_DATA = REAL_DIR / "real_iop_data"
REAL_OSVW_DATA = REAL_DIR / "real_osvw_data"
REAL_SSH_DATA = REAL_DIR / "real_ssh_data"
REAL_SSS_DATA = REAL_DIR / "real_sss_data"
REAL_SST_DATA = REAL_DIR / "real_sst_data"
