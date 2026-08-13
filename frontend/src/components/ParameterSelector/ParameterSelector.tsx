import { useState } from "react";
import DatePickerField from "../DatePickerField/DatePickerField";
import "./ParameterSelector.css";

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

export interface QueryParams {
  filePath: string;
  variable: string;
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
  startDate?: string;
  endDate?: string;
}

interface ParameterSelectorProps {
  filePath: string;
  availableVariables: string[];
  supportsTemporalFilter: boolean; // false for single-granule swath files (Day 9's rule)
  onSubmit: (params: QueryParams) => void;
  onBboxChange?: (
    bbox: { latMin: number; latMax: number; lonMin: number; lonMax: number } | null
  ) => void;
  // Phase B: this file's own valid date coverage, shown next to the
  // date fields so the user knows what range is actually queryable.
  validDateRange?: { min: string; max: string } | null;
}

export default function ParameterSelector({
  filePath,
  availableVariables,
  supportsTemporalFilter,
  onSubmit,
  onBboxChange,
  validDateRange,
}: ParameterSelectorProps) {
  const [variable, setVariable] = useState(availableVariables[0] || "");
  const [latMin, setLatMin] = useState("");
  const [latMax, setLatMax] = useState("");
  const [lonMin, setLonMin] = useState("");
  const [lonMax, setLonMax] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  function emitBboxChange(next: {
    latMin?: string;
    latMax?: string;
    lonMin?: string;
    lonMax?: string;
  }) {
    if (!onBboxChange) return;
    const values = {
      latMin: next.latMin ?? latMin,
      latMax: next.latMax ?? latMax,
      lonMin: next.lonMin ?? lonMin,
      lonMax: next.lonMax ?? lonMax,
    };
    const parsed = {
      latMin: parseFloat(values.latMin),
      latMax: parseFloat(values.latMax),
      lonMin: parseFloat(values.lonMin),
      lonMax: parseFloat(values.lonMax),
    };
    const allValid = Object.values(parsed).every((v) => !Number.isNaN(v));
    onBboxChange(allValid ? parsed : null);
  }
  
  function validate(): string | null {
    if (!variable) return "Select a variable to query.";

    const lm = parseFloat(latMin);
    const lx = parseFloat(latMax);
    const om = parseFloat(lonMin);
    const ox = parseFloat(lonMax);

    if ([lm, lx, om, ox].some((v) => Number.isNaN(v))) {
      return "All four bounding-box fields are required.";
    }
    if (lm < -90 || lm > 90 || lx < -90 || lx > 90) {
      return "Latitude values must be between -90 and 90.";
    }
    if (om < -180 || om > 180 || ox < -180 || ox > 180) {
      return "Longitude values must be between -180 and 180.";
    }
    if (lm >= lx) return "lat_min must be less than lat_max.";
    if (om >= ox) return "lon_min must be less than lon_max.";

    if (supportsTemporalFilter && (startDate || endDate)) {
      if (!startDate || !endDate) {
        return "Provide both a start and end date, or leave both blank.";
      }
      if (!DATE_PATTERN.test(startDate) || !DATE_PATTERN.test(endDate)) {
        return "Dates must be in YYYY-MM-DD format.";
      }
      if (startDate > endDate) {
        return "Start date must not be after end date.";
      }
    }

    return null;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const error = validate();
    if (error) {
      setValidationError(error);
      return;
    }
    setValidationError(null);

    onSubmit({
      filePath,
      variable,
      latMin: parseFloat(latMin),
      latMax: parseFloat(latMax),
      lonMin: parseFloat(lonMin),
      lonMax: parseFloat(lonMax),
      ...(supportsTemporalFilter && startDate && endDate
        ? { startDate, endDate }
        : {}),
    });
  }

  return (
    <form className="parameter-selector" onSubmit={handleSubmit}>
      <div className="field-group">
        <label htmlFor="variable-select">Variable (ECV)</label>
        <select
          id="variable-select"
          value={variable}
          onChange={(e) => setVariable(e.target.value)}
        >
          {availableVariables.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </div>

      <fieldset className="bbox-fieldset">
        <legend>Bounding Box</legend>
        <div className="bbox-grid">
          <label>
            Lat min
            <input
              type="number"
              step="any"
              value={latMin}
              onChange={(e) => {
                setLatMin(e.target.value);
                emitBboxChange({ latMin: e.target.value });
              }}
              placeholder="-90 to 90"
            />
          </label>
          <label>
            Lat max
            <input
              type="number"
              step="any"
              value={latMax}
              onChange={(e) => {
                setLatMax(e.target.value);
                emitBboxChange({ latMax: e.target.value });
              }}
              placeholder="-90 to 90"
            />
          </label>
          <label>
            Lon min
            <input
              type="number"
              step="any"
              value={lonMin}
              onChange={(e) => {
                setLonMin(e.target.value);
                emitBboxChange({ lonMin: e.target.value });
              }}
              placeholder="-180 to 180"
            />
          </label>
          <label>
            Lon max
            <input
              type="number"
              step="any"
              value={lonMax}
              onChange={(e) => {
                setLonMax(e.target.value);
                emitBboxChange({ lonMax: e.target.value });
              }}
              placeholder="-180 to 180"
            />
          </label>
        </div>
      </fieldset>

      {supportsTemporalFilter ? (
        <fieldset className="date-fieldset">
          <legend>Date Range (optional)</legend>
          {validDateRange && (
            <p className="valid-range-note">
              Valid range: {validDateRange.min} to {validDateRange.max}
            </p>
          )}
          <div className="date-grid">
            <DatePickerField label="Start date" value={startDate} onChange={setStartDate} />
            <DatePickerField label="End date" value={endDate} onChange={setEndDate} />
          </div>
        </fieldset>
      ) : (
        <p className="temporal-note">
          Date filtering isn't applicable — this file is a single satellite
          pass covering one short time window.
        </p>
      )}

      {validationError && <div className="validation-error">⚠ {validationError}</div>}

      <button type="submit">Run Query</button>
    </form>
  );
}