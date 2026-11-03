"use client";

/**
 * A threshold control.
 *
 * The value is shown large and in the serif because it is the thing the
 * investor is setting, not a label on a track. Native range input, so it is
 * keyboard-accessible and feels right under a thumb.
 */
export function Slider({
  label,
  value,
  min,
  max,
  step,
  format,
  hint,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
  hint?: string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="px-5 py-4">
      <div className="flex items-baseline justify-between">
        <label htmlFor={label} className="text-[0.875rem] text-muted">
          {label}
        </label>
        <span className="tnum font-serif text-[1.125rem] text-text">{format(value)}</span>
      </div>
      <input
        id={label}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-3 h-1 w-full cursor-pointer appearance-none rounded-full bg-line accent-[var(--signal)]"
      />
      {hint && <p className="mt-2 text-micro leading-relaxed text-faint">{hint}</p>}
    </div>
  );
}
