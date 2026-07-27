#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 27 10:20:54 2026

@author: akki2404
"""

"""
OC-ECV Local Engine — Quality Flag Masking Module (Day 10)

Masks cloud/land/etc. pixels using the l2_flags bitmask variable present
in real NASA Ocean Color L2 files. Reads flag definitions (flag_masks,
flag_meanings) directly from each file's own attributes rather than
hardcoding bit positions — different products/versions can define these
differently, and the file itself is always the authoritative source.
"""

import sys
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.netcdf_reader import open_dataset, _find_data_and_nav_groups, IngestionError

# Sensible default for "cloud/land" masking per Day 10's scope. Callers
# can override with any subset of whatever flag names a given file
# actually defines in its own flag_meanings attribute.
DEFAULT_MASK_FLAGS = ["LAND", "CLDICE"]


class QualityMaskError(Exception):
    """Raised when a file has no l2_flags variable, or requested flags don't exist."""
    pass


def get_flag_definitions(l2_flags: xr.DataArray) -> dict[str, int]:
    """
    Builds a {flag_name: bitmask_value} lookup from the variable's own
    flag_meanings / flag_masks attributes, per CF conventions.
    """
    if "flag_meanings" not in l2_flags.attrs or "flag_masks" not in l2_flags.attrs:
        raise QualityMaskError(
            "l2_flags variable is missing 'flag_meanings' or 'flag_masks' attributes — "
            "cannot determine flag bit definitions from this file"
        )

    names = l2_flags.attrs["flag_meanings"].split()
    masks = l2_flags.attrs["flag_masks"]

    if len(names) != len(masks):
        raise QualityMaskError(
            f"flag_meanings ({len(names)} names) and flag_masks ({len(masks)} values) "
            f"length mismatch — cannot reliably pair them"
        )

    return {name: int(mask) for name, mask in zip(names, masks)}


def build_quality_mask(
    l2_flags_values: np.ndarray, flag_definitions: dict[str, int], flags_to_mask: list[str]
) -> np.ndarray:
    """
    Returns a boolean array (same shape as l2_flags_values) that is True
    wherever the pixel should be MASKED OUT (i.e. any of the requested
    flags is set), using bitwise AND against each flag's bitmask value.
    """
    unknown = [f for f in flags_to_mask if f not in flag_definitions]
    if unknown:
        available = ", ".join(sorted(flag_definitions.keys()))
        raise QualityMaskError(
            f"Unknown flag name(s) {unknown} — available flags in this file: {available}"
        )

    # int32 flag values with the sign bit set (e.g. the last flag_masks
    # entry, -2147483648) require viewing as uint32 for correct bitwise
    # AND behavior against unsigned bit positions.
    flags_uint = l2_flags_values.astype(np.uint32)

    combined_mask_bits = 0
    for name in flags_to_mask:
        combined_mask_bits |= (flag_definitions[name] & 0xFFFFFFFF)

    mask_out = (flags_uint & combined_mask_bits) != 0
    return mask_out


def apply_quality_mask(
    file_path: str, variable: str, flags_to_mask: list[str] | None = None
) -> dict[str, Any]:
    """
    Main entrypoint — opens the file's geophysical_data group, applies
    the requested quality-flag mask on top of the variable's existing
    NaN/fill-value mask, and returns before/after valid-pixel stats so
    the effect of masking is immediately visible.
    """
    if flags_to_mask is None:
        flags_to_mask = DEFAULT_MASK_FLAGS

    data_group, _ = _find_data_and_nav_groups(file_path)
    if not data_group:
        raise QualityMaskError(
            "Quality-flag masking currently supports grouped/swath files "
            "(where l2_flags lives in geophysical_data) — flat-grid files "
            "in this project don't carry l2_flags"
        )

    ds = open_dataset(file_path, group=data_group)
    try:
        if "l2_flags" not in ds.data_vars:
            raise QualityMaskError("File has no 'l2_flags' variable")
        if variable not in ds.data_vars:
            raise QualityMaskError(f"Variable '{variable}' not found in dataset")

        l2_flags = ds["l2_flags"]
        flag_defs = get_flag_definitions(l2_flags)

        data_values = ds[variable].values
        before_valid = int(np.count_nonzero(~np.isnan(data_values)))

        quality_mask_out = build_quality_mask(l2_flags.values, flag_defs, flags_to_mask)
        masked_values = np.where(quality_mask_out, np.nan, data_values)
        after_valid = int(np.count_nonzero(~np.isnan(masked_values)))

        total = int(data_values.size)

        return {
            "variable": variable,
            "flags_masked": flags_to_mask,
            "total_pixels": total,
            "valid_before_quality_mask": before_valid,
            "valid_after_quality_mask": after_valid,
            "pixels_removed_by_quality_mask": before_valid - after_valid,
            "valid_fraction_before": round(before_valid / total, 4) if total else 0.0,
            "valid_fraction_after": round(after_valid / total, 4) if total else 0.0,
        }
    finally:
        ds.close()


if __name__ == "__main__":
    import json

    if len(sys.argv) < 3:
        print("Usage: python quality_mask.py <file> <variable> [flag_name ...]")
        print(f"       If no flag names given, defaults to: {DEFAULT_MASK_FLAGS}")
        sys.exit(1)

    file_path, variable = sys.argv[1], sys.argv[2]
    flags = sys.argv[3:] if len(sys.argv) > 3 else None

    try:
        result = apply_quality_mask(file_path, variable, flags)
        print(json.dumps(result, indent=2, default=str))
    except (QualityMaskError, IngestionError) as e:
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)