/** Mirrors the Pydantic schemas in backend/app/schemas. */

export type GuidanceStatus = "met" | "missed" | "partial" | "too_early" | "unverifiable";

export interface ResultsRow {
  metric: string;
  value: number | null;
  qoq_pct: number | null;
  yoy_pct: number | null;
  prev_quarter: number | null;
  year_ago: number | null;
  sign_flip: boolean;
}

export interface ResultsEnrichment {
  type: "results";
  period: string;
  basis: string;
  unit: string;
  ebitda_derived: boolean;
  confidence: number;
  rows: ResultsRow[];
  ebitda_margin_pct: number | null;
  pat_margin_pct: number | null;
}

export interface PersonEnrichment {
  type: "person";
  name: string;
  role: string | null;
  direction: string;
  effective: string | null;
  background: string | null;
  tenure_note: string | null;
}

export type Enrichment = ResultsEnrichment | PersonEnrichment;

export interface Announcement {
  id: number;
  symbol: string;
  company_name: string;
  filed_at: string;
  subject: string;
  summary: string | null;
  category: string;
  category_label: string;
  score: number;
  is_routine: boolean;
  attachment_url: string | null;
  source: string;
  pct_change: number | null;
  volume_ratio: number | null;
  enrichment: Enrichment | null;
}

export interface Digest {
  window_hours: number;
  from_ts: string;
  to_ts: string;
  headline: string;
  material: Announcement[];
  routine: Announcement[];
  routine_count: number;
  companies_affected: number;
}

export interface Alert {
  id: number;
  symbol: string;
  company_name: string;
  kind: "price" | "volume" | "category";
  headline: string;
  detail: string | null;
  severity: number;
  triggered_at: string;
  acknowledged: boolean;
  announcement_id: number | null;
}

export interface AlertRule {
  profile?: string;
  volume_multiple: number;
  price_move_pct: number;
  watched_categories: string[];
  min_score: number;
  enabled: boolean;
}

export interface CategoryOption {
  value: string;
  label: string;
  default_weight: number;
}

export interface RulePreview {
  days_observed: number;
  price_alerts: number;
  volume_alerts: number;
  per_day: number;
}

export interface GuidanceItem {
  claim_id: number;
  said_in: string;
  metric: string;
  promise: string;
  horizon: string | null;
  speaker: string | null;
  quote: string;
  status: GuidanceStatus;
  actual_value: number | null;
  reasoning: string | null;
  confidence: number;
}

export interface Scorecard {
  met: number;
  missed: number;
  partial: number;
  too_early: number;
  unverifiable: number;
}

export interface Snapshot {
  what_it_does: string | null;
  segments: { name: string; share_pct: number | null; note: string | null }[];
  revenue_mix_note: string | null;
  trajectory: string | null;
  balance_sheet: Record<string, string | null>;
  cash_quality: string | null;
  watch_items: string[];
}

export interface Research {
  symbol: string;
  name: string;
  in_portfolio: boolean;
  snapshot: Snapshot | null;
  bull: string[];
  bear: string[];
  guidance: GuidanceItem[];
  scorecard: Scorecard;
  quarters_covered: string[];
  sources: { title: string; url: string; kind: string }[];
  warnings: string[];
  guidance_note: string | null;
}

export interface CompanyRef {
  symbol: string;
  name: string;
  sector: string | null;
  in_portfolio: boolean;
}
