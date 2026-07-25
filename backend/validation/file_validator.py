#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jul 25 11:17:29 2026

@author: akki2404
"""

"""
OC-ECV Local Engine — File Validation Module (Day 4)

Validates ingested file metadata: spatial bounds, dimension sanity,
and time coordinates. Separated from ingestion (backend/ingestion/)
so parsing and validation are independently testable — ingestion's
job is "can I read this file and what's in it", validation's job is
"is what I read actually usable".

Issues are split into two severities:
  - "error"   -> file is structurally unusable for downstream processing
  - "warning" -> file is usable but has something worth flagging
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str


@dataclass
class ValidationReport:
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [
                {"code": i.code, "message": i.message}
                for i in self.issues if i.severity == "error"
            ],
            "warnings": [
                {"code": i.code, "message": i.message}
                for i in self.issues if i.severity == "warning"
            ],
        }


def validate_spatial_bounds(metadata: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    lat_range = metadata.get("lat_range")
    lon_range = metadata.get("lon_range")

    if lat_range is None:
        issues.append(ValidationIssue("error", "MISSING_LAT_RANGE",
            "Could not determine latitude range from file"))
    else:
        lat_min, lat_max = lat_range
        if not (-90 <= lat_min <= 90 and -90 <= lat_max <= 90):
            issues.append(ValidationIssue("error", "LAT_OUT_OF_RANGE",
                f"Latitude range {lat_range} outside valid [-90, 90]"))
        elif lat_min >= lat_max:
            issues.append(ValidationIssue("error", "LAT_RANGE_INVERTED",
                f"Latitude min ({lat_min}) is not less than max ({lat_max})"))

    if lon_range is None:
        issues.append(ValidationIssue("error", "MISSING_LON_RANGE",
            "Could not determine longitude range from file"))
    else:
        lon_min, lon_max = lon_range
        if not (-180 <= lon_min <= 180 and -180 <= lon_max <= 180):
            issues.append(ValidationIssue("error", "LON_OUT_OF_RANGE",
                f"Longitude range {lon_range} outside valid [-180, 180]"))
        elif lon_min >= lon_max:
            issues.append(ValidationIssue("error", "LON_RANGE_INVERTED",
                f"Longitude min ({lon_min}) is not less than max ({lon_max})"))

    return issues


def validate_dimensions(metadata: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    dimensions = metadata.get("dimensions", {})

    if not dimensions:
        issues.append(ValidationIssue("error", "NO_DIMENSIONS",
            "File has no dimensions — likely empty or unreadable"))
        return issues

    zero_size_dims = [name for name, size in dimensions.items() if size == 0]
    if zero_size_dims:
        issues.append(ValidationIssue("error", "ZERO_SIZE_DIMENSION",
            f"Dimension(s) {zero_size_dims} have size 0 — file contains no actual data"))

    # Sanity ceiling — a single-file dimension over ~50,000 in one axis is
    # unusual for typical Ocean Color products and may indicate a corrupted
    # or misread file rather than genuinely large data.
    huge_dims = [name for name, size in dimensions.items() if isinstance(size, int) and size > 50_000]
    if huge_dims:
        issues.append(ValidationIssue("warning", "UNUSUALLY_LARGE_DIMENSION",
            f"Dimension(s) {huge_dims} are unusually large — verify this is expected"))

    return issues


def validate_time_coordinates(metadata: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    time_steps = metadata.get("time_steps")
    if not time_steps:
        issues.append(ValidationIssue("warning", "NO_TIME_INFO",
            "No time coordinate or time coverage information found in file"))
        return issues

    if len(time_steps) >= 2:
        start, end = time_steps[0], time_steps[-1]
        if start == end:
            issues.append(ValidationIssue("warning", "ZERO_DURATION",
                "Time coverage start and end are identical"))
        elif start > end:
            issues.append(ValidationIssue("error", "TIME_RANGE_INVERTED",
                f"Time coverage start ({start}) is after end ({end})"))

    return issues


def validate_ecv_presence(ecv_variables: dict[str, list[str]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if not any(ecv_variables.values()):
        issues.append(ValidationIssue("error", "NO_ECV_VARIABLES",
            "No recognized Ocean Color ECV variables found in this file"))

    return issues


def run_validation(metadata: dict[str, Any], ecv_variables: dict[str, list[str]]) -> ValidationReport:
    """
    Runs all validation checks and aggregates results. A file is
    considered invalid if any "error"-severity issue is present;
    warnings don't block usability but are surfaced to the user.
    """
    all_issues: list[ValidationIssue] = []
    all_issues += validate_spatial_bounds(metadata)
    all_issues += validate_dimensions(metadata)
    all_issues += validate_time_coordinates(metadata)
    all_issues += validate_ecv_presence(ecv_variables)

    has_errors = any(issue.severity == "error" for issue in all_issues)

    return ValidationReport(valid=not has_errors, issues=all_issues)