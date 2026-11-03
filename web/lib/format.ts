/**
 * Display formatting.
 *
 * One rule runs through all of it: never render a number the data does not
 * support. A missing figure shows an em dash; a percentage the backend
 * refused to compute (sign flip, near-zero base) shows "n.m." — not an
 * invented value.
 */

export const DASH = "—";

/** Indian crore, abbreviated once past a thousand. */
export function crore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH;
  const abs = Math.abs(value);
  if (abs >= 1_00_000) return `${sign(value)}${(abs / 1_00_000).toFixed(2)}L cr`;
  if (abs >= 1_000) return `${sign(value)}${(abs / 1_000).toFixed(2)}k cr`;
  if (abs >= 100) return `${sign(value)}${Math.round(abs).toLocaleString("en-IN")}`;
  return `${sign(value)}${abs.toFixed(1)}`;
}

function sign(value: number): string {
  return value < 0 ? "-" : "";
}

/** A change figure. null means the comparison is not meaningful. */
export function pct(value: number | null | undefined, opts?: { signed?: boolean }): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH;
  const prefix = opts?.signed !== false && value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(1)}%`;
}

export function notMeaningful(value: number | null, signFlip: boolean): boolean {
  return value === null && signFlip;
}

export function multiple(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  return `${value.toFixed(1)}x`;
}

/** Compact relative time: filings are read against "when did this land?" */
export function since(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function metricLabel(metric: string): string {
  const map: Record<string, string> = {
    revenue: "Revenue",
    ebitda: "EBITDA",
    pbt: "PBT",
    pat: "PAT",
  };
  return map[metric] ?? metric.toUpperCase();
}

export function toneFor(value: number | null | undefined): "up" | "down" | "flat" {
  if (value === null || value === undefined) return "flat";
  if (value > 0.05) return "up";
  if (value < -0.05) return "down";
  return "flat";
}

/** Materiality tier, which drives the left rule weight. */
export function tier(score: number): "high" | "mid" | "low" {
  if (score >= 0.45) return "high";
  if (score >= 0.3) return "mid";
  return "low";
}
