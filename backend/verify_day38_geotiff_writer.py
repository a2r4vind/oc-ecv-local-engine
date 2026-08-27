# backend/verify_day38_writers.py
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from pathlib import Path

def verify_geotiff_write():
    arr = np.random.rand(10, 10).astype(np.float32)
    arr[0, 0] = np.nan  # confirm NaN/nodata round-trips correctly

    transform = from_bounds(-124, 33, -119, 37, width=10, height=10)  # lon_min, lat_min, lon_max, lat_max

    path = str(Path.home() / "oc_ecv_local_engine" / "tmp" / "verify_day38.tif")
    with rasterio.open(
        path, "w",
        driver="GTiff",
        height=10, width=10, count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=np.nan,
    ) as dst:
        dst.write(arr, 1)

    # Read back and confirm bounds/CRS/nodata survive the round-trip
    with rasterio.open(path) as src:
        print("CRS:", src.crs)
        print("Bounds:", src.bounds)
        print("Nodata:", src.nodata)
        readback = src.read(1)
        assert np.isnan(readback[0, 0]), "NaN did not round-trip"
        print("✅ GeoTIFF write/read verified")

if __name__ == "__main__":
    verify_geotiff_write()

