#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug  2 16:35:15 2026

@author: akki2404
"""

"""
OC-ECV Local Engine — Query Cache Module (Day 18)

SQLite-backed cache for compute_regional_stats()/compute_batch_timeseries()
outputs. Keyed on all query parameters plus the file's mtime, so edits to
the underlying .nc file automatically invalidate stale cache entries rather
than requiring manual cache clearing.

Designed to double as the data source for Day 39's processing-history
panel — same table, just needs a read/browse endpoint later.
"""

import sqlite3
import json
import hashlib
import os
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "cache" / "query_cache.db"

# Bump this whenever compute_regional_stats()/_get_subsetted_data()/any
# downstream computation logic changes in a way that could change a
# result for previously-cached query parameters. Folded into the cache
# key so a code change automatically invalidates old entries instead of
# silently serving stale results — the exact gap identified in Days
# 19-21 (the valid_min/valid_max fix was masked by stale cache hits
# until manually cleared). This is a blunt instrument (any bump
# invalidates the entire cache, not just affected queries) but that's
# the correct tradeoff here: a missed bump silently serves wrong data,
# while an over-cautious bump just costs some avoidable recomputation.
CACHE_VERSION = 2

def _ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_cache (
            cache_key TEXT PRIMARY KEY,
            cache_version INTEGER NOT NULL DEFAULT 1,
            file_path TEXT NOT NULL,
            file_mtime REAL NOT NULL,
            variable TEXT NOT NULL,
            lat_min REAL, lat_max REAL, lon_min REAL, lon_max REAL,
            start_date TEXT, end_date TEXT, quality_flags TEXT,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            hit_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def _compute_cache_key(
    file_path: str, file_mtime: float, variable: str,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    start_date: str | None, end_date: str | None, quality_flags: list[str] | None,
) -> str:
    raw = json.dumps({
        "cache_version": CACHE_VERSION,
        "file_path": os.path.abspath(file_path),
        "file_mtime": file_mtime,
        "variable": variable,
        "bbox": [lat_min, lat_max, lon_min, lon_max],
        "start_date": start_date,
        "end_date": end_date,
        "quality_flags": sorted(quality_flags) if quality_flags else None,
    }, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cached_result(
    file_path: str, variable: str,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    start_date: str | None = None, end_date: str | None = None,
    quality_flags: list[str] | None = None,
) -> dict[str, Any] | None:
    """Returns the cached result dict if present and the file hasn't changed
    since it was cached, else None (cache miss)."""
    _ensure_db()
    file_mtime = os.path.getmtime(file_path)
    key = _compute_cache_key(
        file_path, file_mtime, variable,
        lat_min, lat_max, lon_min, lon_max, start_date, end_date, quality_flags,
    )
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT result_json FROM query_cache WHERE cache_key = ?", (key,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE query_cache SET hit_count = hit_count + 1 WHERE cache_key = ?", (key,)
        )
        conn.commit()
    conn.close()
    return json.loads(row[0]) if row else None


def store_result(
    file_path: str, variable: str,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    result: dict[str, Any],
    start_date: str | None = None, end_date: str | None = None,
    quality_flags: list[str] | None = None,
) -> None:
    """Stores a computed result, keyed to the file's current mtime."""
    _ensure_db()
    file_mtime = os.path.getmtime(file_path)
    key = _compute_cache_key(
        file_path, file_mtime, variable,
        lat_min, lat_max, lon_min, lon_max, start_date, end_date, quality_flags,
    )
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO query_cache
        (cache_key, cache_version, file_path, file_mtime, variable, lat_min, lat_max, lon_min, lon_max,
         start_date, end_date, quality_flags, result_json, created_at, hit_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                COALESCE((SELECT hit_count FROM query_cache WHERE cache_key = ?), 0))
    """, (
        key, CACHE_VERSION, os.path.abspath(file_path), file_mtime, variable,
        lat_min, lat_max, lon_min, lon_max, start_date, end_date,
        json.dumps(quality_flags) if quality_flags else None,
        json.dumps(result, default=str),
        datetime.now(timezone.utc).isoformat(),
        key,
    ))
    conn.commit()
    conn.close()