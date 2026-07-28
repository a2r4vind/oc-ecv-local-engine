import { useState, useRef, useEffect } from "react";
import "./DatePickerField.css";

interface DatePickerFieldProps {
  label: string;
  value: string; // "YYYY-MM-DD" or ""
  onChange: (value: string) => void;
}

function pad(n: number): string {
  return n.toString().padStart(2, "0");
}

function formatDate(year: number, month: number, day: number): string {
  return `${year}-${pad(month + 1)}-${pad(day)}`;
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

export default function DatePickerField({ label, value, onChange }: DatePickerFieldProps) {
  const [isOpen, setIsOpen] = useState(false);
  const today = new Date();
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(value) : today;
  const [viewYear, setViewYear] = useState(parsed.getFullYear());
  const [viewMonth, setViewMonth] = useState(parsed.getMonth());

  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function goToPrevMonth() {
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear(viewYear - 1);
    } else {
      setViewMonth(viewMonth - 1);
    }
  }

  function goToNextMonth() {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear(viewYear + 1);
    } else {
      setViewMonth(viewMonth + 1);
    }
  }

  function selectDay(day: number) {
    onChange(formatDate(viewYear, viewMonth, day));
    setIsOpen(false);
  }

  const firstWeekday = new Date(viewYear, viewMonth, 1).getDay();
  const totalDays = daysInMonth(viewYear, viewMonth);
  const monthLabel = new Date(viewYear, viewMonth, 1).toLocaleString("default", {
    month: "long",
    year: "numeric",
  });

  const cells: (number | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: totalDays }, (_, i) => i + 1),
  ];

  return (
    <div className="date-picker-field" ref={containerRef}>
      <label>{label}</label>
      <div className="date-picker-input-row">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="YYYY-MM-DD"
          maxLength={10}
        />
        <button
          type="button"
          className="calendar-toggle-btn"
          onClick={() => setIsOpen((v) => !v)}
          aria-label="Open calendar"
        >
          📅
        </button>
      </div>

      {isOpen && (
        <div className="calendar-popup">
          <div className="calendar-header">
            <button type="button" onClick={goToPrevMonth}>‹</button>
            <span>{monthLabel}</span>
            <button type="button" onClick={goToNextMonth}>›</button>
          </div>
          <div className="calendar-weekdays">
            {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
              <span key={i}>{d}</span>
            ))}
          </div>
          <div className="calendar-grid">
            {cells.map((day, i) =>
              day === null ? (
                <span key={i} className="calendar-cell empty" />
              ) : (
                <button
                  type="button"
                  key={i}
                  className={
                    "calendar-cell" +
                    (value === formatDate(viewYear, viewMonth, day) ? " selected" : "")
                  }
                  onClick={() => selectDay(day)}
                >
                  {day}
                </button>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}