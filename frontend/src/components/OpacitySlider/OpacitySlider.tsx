import { useCallback, useRef } from "react";
import "./OpacitySlider.css";

interface OpacitySliderProps {
  value: number; // 0-100
  onChange: (value: number) => void;
}

export default function OpacitySlider({ value, onChange }: OpacitySliderProps) {
  const trackRef = useRef<HTMLDivElement | null>(null);

  const valueFromClientX = useCallback((clientX: number): number => {
    const track = trackRef.current;
    if (!track) return value;
    const rect = track.getBoundingClientRect();
    const fraction = (clientX - rect.left) / rect.width;
    return Math.round(Math.min(1, Math.max(0, fraction)) * 100);
  }, [value]);

  function handlePointerDown(e: React.PointerEvent<HTMLDivElement>) {
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    onChange(valueFromClientX(e.clientX));
  }

  function handlePointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (e.buttons !== 1) return; // only while actively dragging
    onChange(valueFromClientX(e.clientX));
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
      onChange(Math.max(0, value - 1));
    } else if (e.key === "ArrowRight" || e.key === "ArrowUp") {
      onChange(Math.min(100, value + 1));
    }
  }

  return (
    <div
      ref={trackRef}
      className="opacity-slider-track"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      role="slider"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      <div className="opacity-slider-fill" style={{ width: `${value}%` }} />
      <div className="opacity-slider-thumb" style={{ left: `${value}%` }} />
    </div>
  );
}