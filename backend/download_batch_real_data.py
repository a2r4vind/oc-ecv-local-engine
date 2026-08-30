import earthaccess
from config.paths import REAL_BATCH_DATA

auth = earthaccess.login(persist=True)

# Wider date range + higher count to accumulate real multi-GB total volume
results = earthaccess.search_data(
    short_name="MODISA_L2_OC",
    temporal=("2026-01-01", "2026-07-20"),
    bounding_box=(66, 8, 77, 24),  # Arabian Sea / India west coast
    count=25,
)

print(f"Found {len(results)} granules")
files = earthaccess.download(results, str(REAL_BATCH_DATA))
print(f"Downloaded {len(files)} files")
