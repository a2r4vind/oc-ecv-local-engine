"""Profiles compute_regional_stats() across realistic multi-variable workloads
to find where time actually goes before parallelizing anything."""
import time
from processing.statistics import compute_regional_stats, compute_regional_stats_multivar

VARIABLES = ["chlor_a", "Rrs_443", "Rrs_555"]  # extend to all bands you support

def profile_single_variable(path, var, bbox):
    t0 = time.perf_counter()
    result = compute_regional_stats(path, var, *bbox)
    return time.perf_counter() - t0, result

def profile_serial_multivar(path, variables, bbox):
    t0 = time.perf_counter()
    for v in variables:
        compute_regional_stats(path, v, *bbox)
    return time.perf_counter() - t0

if __name__ == "__main__":
    path = "large_sample_oceancolor.nc"
    bbox = (33, 37, -124, -119)

    for v in VARIABLES:
        t, _ = profile_single_variable(path, v, bbox)
        print(f"{v}: {t:.4f}s")

    total_serial = profile_serial_multivar(path, VARIABLES, bbox)
    print(f"Serial total ({len(VARIABLES)} vars): {total_serial:.4f}s")

    # Parallel comparison + correctness check
    t0 = time.perf_counter()
    serial_results = {v: compute_regional_stats(path, v, *bbox) for v in VARIABLES}
    t_serial = time.perf_counter() - t0

    t0 = time.perf_counter()
    parallel_results = compute_regional_stats_multivar(path, VARIABLES, *bbox)
    t_parallel = time.perf_counter() - t0

    print(f"Serial: {t_serial:.2f}s | Parallel: {t_parallel:.2f}s | Speedup: {t_serial/t_parallel:.2f}x")
    for v in VARIABLES:
        assert serial_results[v] == parallel_results[v], f"MISMATCH on {v}"
    print("Results match.")