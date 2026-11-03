"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { AlertRule } from "@/types/api";

export function useDigest(hours: number) {
  return useQuery({
    queryKey: ["digest", hours],
    queryFn: () => api.digest(hours),
    // Filings land through the day; a stale digest is worse than a refetch.
    staleTime: 60_000,
  });
}

export function useAlerts() {
  return useQuery({ queryKey: ["alerts"], queryFn: api.alerts, staleTime: 60_000 });
}

export function useAcknowledge() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.acknowledge,
    onSuccess: () => client.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useRule() {
  return useQuery({ queryKey: ["rule"], queryFn: api.rule, staleTime: Infinity });
}

export function useCategories() {
  return useQuery({ queryKey: ["categories"], queryFn: api.categories, staleTime: Infinity });
}

export function useSaveRule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: AlertRule) => api.saveRule(payload),
    onSuccess: () => {
      // Thresholds changed, so both the rule and anything it fired are stale.
      client.invalidateQueries({ queryKey: ["rule"] });
      client.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function usePreview(volume: number, price: number) {
  return useQuery({
    queryKey: ["preview", volume, price],
    queryFn: () => api.preview(volume, price),
    staleTime: 30_000,
  });
}

export function useCompanies() {
  return useQuery({ queryKey: ["companies"], queryFn: api.companies, staleTime: Infinity });
}

export function useResearch(symbol: string | null) {
  return useQuery({
    queryKey: ["research", symbol],
    queryFn: () => api.research(symbol as string),
    enabled: Boolean(symbol),
    // A full pipeline run is expensive; never refetch it behind the user.
    staleTime: Infinity,
    retry: false,
  });
}
