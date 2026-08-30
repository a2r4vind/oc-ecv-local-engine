import earthaccess

earthaccess.login()

# Step 1: confirm the collection exists and get its real version string
collections = earthaccess.search_datasets(short_name="AU_SI25")
print(f"Found {len(collections)} matching collection(s)\n")
for c in collections:
    print(c.summary())
    print("---")

# Step 2: try granule search using concept_id directly (most precise) + cloud_hosted
print("\n=== Granule search: concept_id + cloud_hosted=True ===")
results = earthaccess.search_data(
    concept_id="C3243521560-NSIDC_CPRD",
    cloud_hosted=True,
    temporal=("2026-01-01", "2026-01-31"),
    bounding_box=(68, 4, 95, 25),
)
print(f"Granules found: {len(results)}")
if results:
    print(results[0])

# Step 3: isolate - drop bbox entirely, temporal only
print("\n=== Granule search: concept_id + temporal ONLY (no bbox) ===")
results = earthaccess.search_data(
    concept_id="C3243521560-NSIDC_CPRD",
    cloud_hosted=True,
    temporal=("2026-01-01", "2026-01-31"),
)
print(f"Granules found: {len(results)}")
if results:
    print(results[0])

# Step 4a: bare concept_id, no temporal, no bbox, cloud_hosted=True
print("\n=== concept_id ONLY, cloud_hosted=True, count=5 ===")
results = earthaccess.search_data(
    concept_id="C3243521560-NSIDC_CPRD",
    cloud_hosted=True,
    count=5,
)
print(f"Granules found: {len(results)}")
if results:
    print(results[0])

# Step 4b: same, but cloud_hosted=False
print("\n=== concept_id ONLY, cloud_hosted=False, count=5 ===")
results = earthaccess.search_data(
    concept_id="C3243521560-NSIDC_CPRD",
    cloud_hosted=False,
    count=5,
)
print(f"Granules found: {len(results)}")
if results:
    print(results[0])

# Step 4c: same, but cloud_hosted omitted entirely
print("\n=== concept_id ONLY, cloud_hosted OMITTED, count=5 ===")
results = earthaccess.search_data(
    concept_id="C3243521560-NSIDC_CPRD",
    count=5,
)
print(f"Granules found: {len(results)}")
if results:
    print(results[0])

# Step 5: find the actual most recent granule available, sorted descending
print("\n=== Most recent granule available (sorted by end_date descending) ===")
results = earthaccess.search_data(
    concept_id="C3243521560-NSIDC_CPRD",
    count=1,
    sort_key="-end_date",
)
if results:
    print(results[0]["umm"]["TemporalExtent"])
else:
    print("No granules returned even with no filters")

# Step 6: download one real granule from the confirmed-available window
print("\n=== Downloading one real AU_SI25 granule (Aug 2025) ===")
results = earthaccess.search_data(
    concept_id="C3243521560-NSIDC_CPRD",
    temporal=("2025-08-25", "2025-09-01"),
    count=1,
)
print(f"Granules found: {len(results)}")
if results:
    files = earthaccess.download(results, "../tmp/sea_ice_real")
    print(files)
