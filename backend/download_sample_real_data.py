import earthaccess

auth = earthaccess.login(persist=True)

# Arabian Sea, India's west coast (Gujarat to Kerala)
results = earthaccess.search_data(
    short_name="MODISA_L2_OC",
    temporal=("2026-01-01", "2026-07-20"),
    bounding_box=(66, 8, 77, 24),
    count=1,
)

if not results:
    print("No granules found — try widening the date range or bounding box.")
else:
    files = earthaccess.download(results, "./real_sample_data")
    print(f"Downloaded: {files}")
