"use client";

import { useState } from "react";

import { PersonPanel } from "@/components/digest/PersonPanel";
import { ResultsPanel } from "@/components/digest/ResultsPanel";
import { Chip, Delta, Expand } from "@/components/shared/Primitives";
import { multiple, since, tier } from "@/lib/format";
import type { Announcement } from "@/types/api";

/**
 * One filing.
 *
 * A row, not a card: cards impose equal visual weight on unequal things. The
 * left rule and the text contrast carry materiality, so a glance down the
 * column reads as a priority order before a single word is read.
 */
export function AnnouncementRow({ item, dim = false }: { item: Announcement; dim?: boolean }) {
  const [open, setOpen] = useState(false);
  const level = tier(item.score);
  const hasDetail = Boolean(item.enrichment) || Boolean(item.attachment_url);
  const unusualVolume = item.volume_ratio !== null && item.volume_ratio >= 2;

  return (
    <article className={`hairline rule-${level} ${dim ? "opacity-60" : ""}`}>
      <button
        onClick={() => hasDetail && setOpen((value) => !value)}
        aria-expanded={hasDetail ? open : undefined}
        disabled={!hasDetail}
        className="block w-full px-5 py-3.5 text-left disabled:cursor-default"
      >
        <div className="flex items-center gap-2">
          <span className="font-serif text-[0.9375rem] text-text">{item.symbol}</span>
          <Chip accent={level === "high"}>{item.category_label}</Chip>
          <span className="ml-auto shrink-0 text-micro text-faint">{since(item.filed_at)}</span>
        </div>

        <p
          className={`mt-1.5 text-[0.9375rem] leading-snug ${
            level === "low" ? "text-muted" : "text-text"
          }`}
        >
          {item.summary || item.subject}
        </p>

        {(item.pct_change !== null || unusualVolume) && (
          <div className="mt-1.5 flex items-center gap-3">
            <Delta value={item.pct_change} />
            {unusualVolume && (
              <span className="tnum text-micro text-signal">
                {multiple(item.volume_ratio)} volume
              </span>
            )}
          </div>
        )}

        {hasDetail && (
          <span className="mt-1.5 inline-block text-micro text-faint">
            {open ? "Hide detail" : item.enrichment ? "Show numbers" : "Open filing"}
          </span>
        )}
      </button>

      {item.enrichment && (
        <Expand open={open}>
          {item.enrichment.type === "results" ? (
            <ResultsPanel data={item.enrichment} />
          ) : (
            <PersonPanel data={item.enrichment} />
          )}
          <Footer item={item} />
        </Expand>
      )}

      {!item.enrichment && item.attachment_url && (
        <Expand open={open}>
          <div className="px-5 pb-4">
            <p className="text-[0.875rem] leading-relaxed text-muted">{item.subject}</p>
            <Footer item={item} />
          </div>
        </Expand>
      )}
    </article>
  );
}

function Footer({ item }: { item: Announcement }) {
  return (
    <div className="flex items-center gap-3 px-5 pb-4 pt-1 text-micro text-faint">
      <span>{item.source}</span>
      {item.attachment_url && (
        <a
          href={item.attachment_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-signal underline underline-offset-4"
        >
          Read the filing
        </a>
      )}
    </div>
  );
}
