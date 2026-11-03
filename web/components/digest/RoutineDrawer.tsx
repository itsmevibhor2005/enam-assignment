"use client";

import { useState } from "react";

import { AnnouncementRow } from "@/components/digest/AnnouncementRow";
import { Expand } from "@/components/shared/Primitives";
import type { Announcement } from "@/types/api";

/**
 * Routine filings are collapsed, never hidden. The count is the point: it
 * tells the investor how much was filtered out on their behalf, which is what
 * makes the filtering trustworthy rather than opaque.
 */
export function RoutineDrawer({ items }: { items: Announcement[] }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;

  return (
    <section>
      <button
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="hairline flex w-full items-center justify-between px-5 py-3.5 text-left"
      >
        <span className="text-[0.875rem] text-muted">
          {items.length} routine {items.length === 1 ? "filing" : "filings"}
        </span>
        <span className="text-micro text-faint">{open ? "Hide" : "Show"}</span>
      </button>
      <Expand open={open}>
        <div>
          {items.map((item) => (
            <AnnouncementRow key={item.id} item={item} dim />
          ))}
        </div>
      </Expand>
    </section>
  );
}
