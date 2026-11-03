"use client";

import { motion } from "framer-motion";

/** A category chip. Quiet by default; only material items get the accent. */
export function Chip({
  children,
  accent = false,
}: {
  children: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-sm px-1.5 py-0.5 text-micro ${
        accent ? "bg-signal/15 text-signal" : "bg-raised text-muted"
      }`}
    >
      {children}
    </span>
  );
}

/** A price or volume figure, coloured only by direction. */
export function Delta({ value, suffix = "%" }: { value: number | null; suffix?: string }) {
  if (value === null || value === undefined) return null;
  const tone = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted";
  const prefix = value > 0 ? "+" : "";
  return (
    <span className={`tnum text-[0.8125rem] ${tone}`}>
      {prefix}
      {value.toFixed(1)}
      {suffix}
    </span>
  );
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="font-serif text-[1.0625rem] text-text">{children}</h2>;
}

/**
 * Empty states are directions, not apologies: each one says what happened and
 * what the reader can do next.
 */
export function Empty({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="px-5 py-14 text-center">
      <p className="font-serif text-[1.0625rem] leading-relaxed text-muted">{title}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Loading({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-px" aria-busy="true" aria-live="polite">
      {Array.from({ length: lines }).map((_, index) => (
        <div key={index} className="hairline px-5 py-4">
          <div className="h-2.5 w-20 animate-pulse rounded-sm bg-raised" />
          <div className="mt-2.5 h-3 w-full animate-pulse rounded-sm bg-raised" />
          <div className="mt-1.5 h-3 w-3/5 animate-pulse rounded-sm bg-raised" />
        </div>
      ))}
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="mx-5 my-6 border border-line bg-surface px-4 py-3.5">
      <p className="text-[0.875rem] leading-relaxed text-text">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2.5 text-[0.8125rem] text-signal underline underline-offset-4"
        >
          Try again
        </button>
      )}
    </div>
  );
}

/** Expand-in-place: motion answers the tap, it does not decorate the page. */
export function Expand({ open, children }: { open: boolean; children: React.ReactNode }) {
  return (
    <motion.div
      initial={false}
      animate={{ height: open ? "auto" : 0, opacity: open ? 1 : 0 }}
      transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
      className="overflow-hidden"
    >
      {children}
    </motion.div>
  );
}
