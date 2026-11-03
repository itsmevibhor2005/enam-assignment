"use client";

import { useAcknowledge } from "@/lib/hooks/useApi";
import { since } from "@/lib/format";
import type { Alert } from "@/types/api";

/**
 * Triggered alerts sit above the digest because they are the things the
 * investor asked to be interrupted for. Dismissing one is a single tap and is
 * permanent — an alert the user has seen should not come back.
 */
export function AlertStrip({ alerts }: { alerts: Alert[] }) {
  const acknowledge = useAcknowledge();
  const live = alerts.filter((alert) => !alert.acknowledged).slice(0, 4);
  if (live.length === 0) return null;

  return (
    <section aria-label="Triggered alerts" className="border-b border-line bg-surface">
      {live.map((alert) => (
        <div key={alert.id} className="flex items-start gap-3 px-5 py-3">
          <span
            aria-hidden
            className="mt-[0.4rem] h-1.5 w-1.5 shrink-0 rounded-full bg-signal"
          />
          <div className="min-w-0 flex-1">
            <p className="text-[0.875rem] leading-snug text-text">{alert.headline}</p>
            {alert.detail && (
              <p className="mt-0.5 truncate text-micro text-faint">{alert.detail}</p>
            )}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <span className="text-micro text-faint">{since(alert.triggered_at)}</span>
            <button
              onClick={() => acknowledge.mutate(alert.id)}
              className="text-micro text-faint underline underline-offset-4"
            >
              Dismiss
            </button>
          </div>
        </div>
      ))}
    </section>
  );
}
