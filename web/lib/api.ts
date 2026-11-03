/**
 * Typed API client.
 *
 * Every call goes through one fetch wrapper so error shape, timeout and base
 * URL are handled once. Requests are same-origin: next.config.mjs proxies
 * /api to the backend, which keeps CORS and host configuration out of the
 * browser entirely.
 */
import type {
  Alert,
  AlertRule,
  CategoryOption,
  CompanyRef,
  Digest,
  Research,
  RulePreview,
} from "@/types/api";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

const DEFAULT_TIMEOUT_MS = 20_000;
/** Research can run a live pipeline on an unknown ticker; it needs room. */
const RESEARCH_TIMEOUT_MS = 180_000;

async function request<T>(path: string, init: RequestInit & { timeoutMs?: number } = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(path, {
      ...rest,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
    });

    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try {
        const body = await response.json();
        if (body?.detail) detail = body.detail;
      } catch {
        /* a non-JSON error body is still an error; keep the default text */
      }
      throw new ApiError(detail, response.status);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("That took too long. The data source may be slow right now.", 408);
    }
    throw new ApiError("Could not reach the server.", 0);
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  digest: (hours: number) => request<Digest>(`/api/digest?hours=${hours}`),
  alerts: () => request<Alert[]>("/api/digest/alerts"),
  acknowledge: (id: number) =>
    request<{ ok: boolean }>(`/api/digest/alerts/${id}/ack`, { method: "POST" }),

  rule: () => request<AlertRule>("/api/alert-rules"),
  saveRule: (payload: AlertRule) =>
    request<AlertRule>("/api/alert-rules", { method: "PUT", body: JSON.stringify(payload) }),
  categories: () => request<CategoryOption[]>("/api/alert-rules/categories"),
  preview: (volume: number, price: number) =>
    request<RulePreview>(
      `/api/alert-rules/preview?volume_multiple=${volume}&price_move_pct=${price}`,
    ),

  companies: () => request<CompanyRef[]>("/api/research"),
  research: (symbol: string) =>
    request<Research>(`/api/research/${encodeURIComponent(symbol)}`, {
      timeoutMs: RESEARCH_TIMEOUT_MS,
    }),
};
