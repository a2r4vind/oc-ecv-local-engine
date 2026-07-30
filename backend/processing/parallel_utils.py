#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 29 09:28:57 2026

@author: akki2404
"""

"""Thread-pool helpers for running independent per-variable / per-file
processing concurrently. NumPy releases the GIL during large elementwise
C-level ops (nanmean, nanmin, nanmax, nanstd, boolean masking), so threads
give real wall-clock benefit here despite Python's GIL — no multiprocessing
overhead (no pickling arrays across processes) is needed."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Any

def get_worker_count(requested: int | None = None) -> int:
    """Caps threads at CPU count; avoids oversubscription if BLAS is also
    spinning up its own threads underneath (unlikely here, but cheap to guard)."""
    cpu_count = os.cpu_count() or 4
    if requested is None:
        return min(cpu_count, 8)  # 8 is a sane ceiling regardless of core count
    return min(requested, cpu_count)

def run_parallel(
    fn: Callable[[Any], Any],
    items: Iterable[Any],
    max_workers: int | None = None,
) -> list[tuple[Any, Any, Exception | None]]:
    """Runs fn(item) across items concurrently. Returns (item, result, error)
    tuples in completion order — never raises, so one bad file/variable
    doesn't kill the whole batch (consistent with your existing
    IngestionError/SubsettingError clean-failure pattern)."""
    workers = get_worker_count(max_workers)
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, item): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                results.append((item, future.result(), None))
            except Exception as e:
                results.append((item, None, e))
    return results