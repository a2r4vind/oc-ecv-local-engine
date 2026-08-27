import xarray as xr
import numpy as np
from pathlib import Path

def verify_netcdf_swath_write():
    lat2d = np.random.uniform(8, 16, (5, 5))
    lon2d = np.random.uniform(82, 90, (5, 5))
    values = np.random.rand(5, 5).astype(np.float32)

    ds = xr.Dataset(
        data_vars={
            "chlor_a": (("y", "x"), values, {
                "long_name": "Chlorophyll Concentration",
                "units": "mg m^-3",
                "coordinates": "lat lon",
                "grid_mapping": "crs",
            }),
        },
        coords={
            "lat": (("y", "x"), lat2d, {"units": "degrees_north", "standard_name": "latitude"}),
            "lon": (("y", "x"), lon2d, {"units": "degrees_east", "standard_name": "longitude"}),
        },
    )
    ds["crs"] = xr.DataArray(0, attrs={
        "grid_mapping_name": "latitude_longitude",
        "longitude_of_prime_meridian": 0.0,
        "semi_major_axis": 6378137.0,
        "inverse_flattening": 298.257223563,
    })
    ds.attrs["Conventions"] = "CF-1.8"
    
    path = str(Path.home() / "oc_ecv_local_engine" / "tmp" / "verify_day38_swath.nc")
    ds.to_netcdf(path)
    reopened = xr.open_dataset(path)
    print(reopened)
    print("✅ NetCDF swath write verified")

if __name__ == "__main__":
    verify_netcdf_swath_write()

