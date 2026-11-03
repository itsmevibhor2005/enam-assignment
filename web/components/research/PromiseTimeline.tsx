"use client";

import { useState } from "react";

import { Expand } from "@/components/shared/Primitives";
import type { GuidanceItem, GuidanceStatus, Scorecard } from "@/types/api";

/**
 * Promised vs delivered.
 *
 * The difference between summarising management and analysing them. Every row
 * is a commitment management made on a call, paired with the number that
 * settled it. Verdicts are stated flatly — the component never editorialises
 * about the company, it just shows what was said and what happened.
 */

const STATUS_COPY: Record<GuidanceStatus, { label: string; className: string }> = {
  met: { label: "Delivered", className: "text-up" },
  missed: { label: "Missed", className: "text-down" },
  partial: { label: "Part way", className: "text-signal" },
  too_early: { label: "Not due yet", className: "text-faint" },
  unverifiable: { label: "Can't check", className: "text-faint" },
};

export function PromiseTimeline({
  items,
  scorecard,
  quarters,
  note,
}: {
  items: GuidanceItem[];
  scorecard: Scorecard;
  quarters: string[];
  note: string | null;
}) {
  if (items.length === 0) {
    return (
      <section className="px-5 py-6">
        <h2 className="font-serif text-[1.0625rem] text-text">Promised vs delivered</h2>
        <p className="mt-2 text-[0.875rem] leading-relaxed text-muted">
          {note ?? "No checkable commitments were found in the available transcripts."}
        </p>
      </section>
    );
  }

  const judged = scorecard.met + scorecard.missed + scorecard.partial;

  return (
    <section className="pt-6">
      <div className="px-5">
        <h2 className="font-serif text-[1.0625rem] text-text">Promised vs delivered</h2>
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-faint">
          {judged > 0 ? (
            <>
              {scorecard.met} of {judged} settled commitments were delivered
              {scorecard.missed > 0 && `, ${scorecard.missed} missed`}
              {scorecard.partial > 0 && `, ${scorecard.partial} part way`}.
            </>
          ) : (
            <>None of these commitments have reached their horizon yet.</>
          )}
          {quarters.length > 0 && ` From ${quarters.join(", ")}.`}
        </p>
      </div>

      <ol className="mt-4">
        {items.map((item) => (
          <PromiseRow key={item.claim_id} item={item} />
        ))}
      </ol>
    </section>
  );
}

function PromiseRow({ item }: { item: GuidanceItem }) {
  const [open, setOpen] = useState(false);
  const status = STATUS_COPY[item.status];
  const settled = item.status === "met" || item.status === "missed" || item.status === "partial";

  return (
    <li className={`hairline ${settled ? "rule-mid" : "rule-low"}`}>
      <button
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="block w-full px-5 py-3.5 text-left"
      >
        <div className="flex items-baseline gap-2">
          <span className="text-micro text-faint">Said in {item.said_in}</span>
          {item.horizon && <span className="text-micro text-faint">· for {item.horizon}</span>}
          <span className={`ml-auto shrink-0 text-micro ${status.className}`}>{status.label}</span>
        </div>

        <p className="mt-1.5 font-serif text-[0.9375rem] leading-snug text-text">{item.promise}</p>

        {item.reasoning && (
          <p className="mt-1 text-[0.8125rem] leading-snug text-muted">{item.reasoning}</p>
        )}
      </button>

      <Expand open={open}>
        <div className="px-5 pb-4">
          <blockquote className="border-l border-line pl-3.5 text-[0.875rem] leading-relaxed text-text/85">
            {item.quote}
          </blockquote>
          <p className="mt-1.5 text-micro text-faint">
            {item.speaker ?? "Management"} · {item.said_in} earnings call
          </p>
        </div>
      </Expand>
    </li>
  );
}
