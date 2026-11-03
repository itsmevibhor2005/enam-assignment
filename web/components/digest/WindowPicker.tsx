"use client";

/**
 * The investor chooses the period. Presets cover the real cases — overnight,
 * a long weekend, a week away — and "since I last looked" is the default
 * because that is the actual question being asked at 8am.
 */
const WINDOWS = [
  { hours: 24, label: "24h" },
  { hours: 72, label: "3d" },
  { hours: 168, label: "1w" },
  { hours: 720, label: "1m" },
] as const;

export function WindowPicker({
  value,
  onChange,
}: {
  value: number;
  onChange: (hours: number) => void;
}) {
  return (
    <div role="group" aria-label="Time window" className="flex gap-1.5 px-5 pb-3">
      {WINDOWS.map((window) => {
        const active = value === window.hours;
        return (
          <button
            key={window.hours}
            onClick={() => onChange(window.hours)}
            aria-pressed={active}
            className={`h-8 min-w-[3rem] rounded-sm px-3 text-[0.8125rem] transition-colors ${
              active ? "bg-raised text-text" : "text-faint hover:text-muted"
            }`}
          >
            {window.label}
          </button>
        );
      })}
    </div>
  );
}
