"use client";

import { useState } from "react";

import { AlertStrip } from "@/components/digest/AlertStrip";
import { AnnouncementRow } from "@/components/digest/AnnouncementRow";
import { RoutineDrawer } from "@/components/digest/RoutineDrawer";
import { WindowPicker } from "@/components/digest/WindowPicker";
import { Empty, ErrorNote, Loading } from "@/components/shared/Primitives";
import { useAlerts, useDigest } from "@/lib/hooks/useApi";

/**
 * Today — the home screen.
 *
 * The hero is a sentence, not a number. "4 things matter since yesterday" is
 * the product's entire claim, and on a quiet day it says so plainly rather
 * than filling the screen to look busy.
 */
export default function TodayPage() {
  const [hours, setHours] = useState(24);
  const digest = useDigest(hours);
  const alerts = useAlerts();

  return (
    <div>
      <header className="px-5 pb-3 pt-7">
        <h1 className="font-serif text-[1.5rem] leading-snug text-text">
          {digest.data?.headline ?? "Reading your portfolio…"}
        </h1>
        {digest.data && digest.data.companies_affected > 0 && (
          <p className="mt-1 text-[0.8125rem] text-faint">
            Across {digest.data.companies_affected}{" "}
            {digest.data.companies_affected === 1 ? "company" : "companies"}
          </p>
        )}
      </header>

      <WindowPicker value={hours} onChange={setHours} />

      {alerts.data && <AlertStrip alerts={alerts.data} />}

      {digest.isLoading && <Loading lines={4} />}

      {digest.isError && (
        <ErrorNote
          message="The digest could not load. The backend may still be starting up."
          onRetry={() => digest.refetch()}
        />
      )}

      {digest.data && (
        <>
          {digest.data.material.length === 0 && digest.data.routine.length === 0 ? (
            <Empty title="Nothing has been filed in this window. Try a longer period." />
          ) : (
            <section aria-label="Filings that matter">
              {digest.data.material.map((item) => (
                <AnnouncementRow key={item.id} item={item} />
              ))}
            </section>
          )}

          <RoutineDrawer items={digest.data.routine} />

          <p className="px-5 py-6 text-micro leading-relaxed text-faint">
            Ranked by category, how material the filing is, how recent it is, and whether the
            market moved on it the same day.
          </p>
        </>
      )}
    </div>
  );
}
