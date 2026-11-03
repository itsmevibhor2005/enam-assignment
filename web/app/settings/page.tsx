"use client";

import { useEffect, useState } from "react";

import { Slider } from "@/components/shared/Slider";
import { ErrorNote, Loading } from "@/components/shared/Primitives";
import { useCategories, usePreview, useRule, useSaveRule } from "@/lib/hooks/useApi";
import type { AlertRule } from "@/types/api";

/**
 * Alerts — where the investor decides what "unusual" means.
 *
 * This is a first-class screen, not a settings afterthought: the brief's point
 * is that the threshold belongs to the user. The preview line is what makes it
 * usable — tuning a number blind is guesswork, so we show how often these
 * settings would actually have fired against their own portfolio.
 */
export default function SettingsPage() {
  const rule = useRule();
  const categories = useCategories();
  const save = useSaveRule();

  const [draft, setDraft] = useState<AlertRule | null>(null);
  useEffect(() => {
    if (rule.data && !draft) setDraft(rule.data);
  }, [rule.data, draft]);

  const preview = usePreview(draft?.volume_multiple ?? 2, draft?.price_move_pct ?? 4);
  const dirty =
    draft !== null &&
    rule.data !== undefined &&
    JSON.stringify({ ...draft, profile: undefined }) !==
      JSON.stringify({ ...rule.data, profile: undefined });

  if (rule.isLoading || !draft) return <Loading lines={3} />;
  if (rule.isError) {
    return <ErrorNote message="Your alert settings could not load." onRetry={() => rule.refetch()} />;
  }

  const update = (patch: Partial<AlertRule>) => setDraft({ ...draft, ...patch });

  const toggleCategory = (value: string) => {
    const next = draft.watched_categories.includes(value)
      ? draft.watched_categories.filter((item) => item !== value)
      : [...draft.watched_categories, value];
    update({ watched_categories: next });
  };

  return (
    <div>
      <header className="px-5 pb-2 pt-7">
        <h1 className="font-serif text-[1.5rem] text-text">Alerts</h1>
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-faint">
          You decide what counts as unusual. These thresholds run against end-of-day data for
          your holdings.
        </p>
      </header>

      <section className="mt-3 border-y border-line">
        <Slider
          label="Price move"
          value={draft.price_move_pct}
          min={1}
          max={15}
          step={0.5}
          format={(value) => `±${value.toFixed(1)}%`}
          hint="Tell me when a holding closes beyond this, up or down."
          onChange={(value) => update({ price_move_pct: value })}
        />
        <div className="hairline" />
        <Slider
          label="Volume spike"
          value={draft.volume_multiple}
          min={1.5}
          max={8}
          step={0.1}
          format={(value) => `${value.toFixed(1)}x`}
          hint="Against the trailing 20-day average, excluding the day itself."
          onChange={(value) => update({ volume_multiple: value })}
        />
      </section>

      {preview.data && (
        <p className="px-5 py-3.5 text-[0.8125rem] leading-relaxed text-muted">
          Over the last {preview.data.days_observed} trading days these settings would have
          fired{" "}
          <span className="tnum text-text">
            {preview.data.price_alerts + preview.data.volume_alerts}
          </span>{" "}
          times — about {preview.data.per_day} a day.
          {preview.data.per_day > 3 && " That is probably more than you want."}
        </p>
      )}

      <section className="border-t border-line px-5 py-5">
        <h2 className="text-[0.875rem] text-muted">Interrupt me for</h2>
        <p className="mt-1 text-micro leading-relaxed text-faint">
          Everything else still appears in the digest, just without an alert.
        </p>
        {categories.data && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {categories.data
              .filter((category) => category.default_weight >= 0.3)
              .map((category) => {
                const on = draft.watched_categories.includes(category.value);
                return (
                  <button
                    key={category.value}
                    onClick={() => toggleCategory(category.value)}
                    aria-pressed={on}
                    className={`rounded-sm px-2.5 py-1.5 text-[0.8125rem] transition-colors ${
                      on ? "bg-signal/15 text-signal" : "bg-surface text-faint"
                    }`}
                  >
                    {category.label}
                  </button>
                );
              })}
          </div>
        )}
      </section>

      <section className="border-t border-line">
        <Slider
          label="Minimum importance"
          value={draft.min_score}
          min={0}
          max={0.9}
          step={0.05}
          format={(value) => value.toFixed(2)}
          hint="How material a filing must be before it earns an alert, on the same 0-1 scale used to rank your digest."
          onChange={(value) => update({ min_score: value })}
        />
      </section>

      <div className="flex items-center justify-between border-t border-line px-5 py-4">
        <div>
          <p className="text-[0.875rem] text-text">Alerts are {draft.enabled ? "on" : "paused"}</p>
          <p className="mt-0.5 text-micro text-faint">The digest keeps working either way.</p>
        </div>
        <button
          onClick={() => update({ enabled: !draft.enabled })}
          role="switch"
          aria-checked={draft.enabled}
          className={`h-7 w-12 shrink-0 rounded-full p-0.5 transition-colors ${
            draft.enabled ? "bg-signal/40" : "bg-line"
          }`}
        >
          <span
            className={`block h-6 w-6 rounded-full bg-text transition-transform ${
              draft.enabled ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
      </div>

      <div className="px-5 py-5">
        <button
          onClick={() => draft && save.mutate(draft)}
          disabled={!dirty || save.isPending}
          className="h-11 w-full rounded-sm bg-raised text-[0.9375rem] text-text disabled:text-faint"
        >
          {save.isPending ? "Saving…" : dirty ? "Save thresholds" : "Saved"}
        </button>
        {save.isError && (
          <p className="mt-2 text-[0.8125rem] text-down">
            Those thresholds could not be saved. Check the values and try again.
          </p>
        )}
      </div>
    </div>
  );
}
