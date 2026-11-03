"use client";

import type { PersonEnrichment } from "@/types/api";

/**
 * A management change is only useful if you know who the person is. Where the
 * filing carries a background we show it; where it does not, we say so rather
 * than letting a model supply one from memory.
 */
export function PersonPanel({ data }: { data: PersonEnrichment }) {
  const verb =
    data.direction === "joining" ? "Joining" : data.direction === "leaving" ? "Leaving" : "Change";

  return (
    <div className="px-5 pb-4 pt-1">
      <div className="border-l border-line pl-3.5">
        <div className="flex items-baseline gap-2">
          <span className="font-serif text-[1.0625rem] text-text">{data.name}</span>
          <span className="text-micro text-faint">{verb}</span>
        </div>
        {data.role && <p className="mt-0.5 text-[0.8125rem] text-muted">{data.role}</p>}

        {data.background ? (
          <p className="mt-2 text-[0.875rem] leading-relaxed text-text/90">{data.background}</p>
        ) : (
          <p className="mt-2 text-[0.8125rem] leading-relaxed text-faint">
            The filing gives no background on this person.
          </p>
        )}

        <div className="mt-2 flex flex-wrap gap-x-4 text-micro text-faint">
          {data.effective && <span>Effective {data.effective}</span>}
          {data.tenure_note && <span>{data.tenure_note}</span>}
        </div>
      </div>
    </div>
  );
}
