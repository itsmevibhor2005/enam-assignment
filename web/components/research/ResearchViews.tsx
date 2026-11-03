"use client";

import type { Research } from "@/types/api";

/** Business and financial context, sized to about forty seconds of reading. */
export function SnapshotView({ data }: { data: Research }) {
  const snapshot = data.snapshot;
  if (!snapshot) return null;

  const balanceNotes = Object.values(snapshot.balance_sheet ?? {}).filter(Boolean) as string[];

  return (
    <section className="px-5 pt-6">
      {snapshot.what_it_does && (
        <p className="font-serif text-[1.0625rem] leading-relaxed text-text">
          {snapshot.what_it_does}
        </p>
      )}

      {snapshot.segments.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {snapshot.segments.map((segment) => (
            <li key={segment.name} className="flex items-baseline gap-3 text-[0.875rem]">
              <span className="text-muted">{segment.name}</span>
              {segment.share_pct !== null && (
                <span className="tnum ml-auto text-text">{segment.share_pct.toFixed(0)}%</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {snapshot.trajectory && (
        <Block title="Trajectory" body={snapshot.trajectory} />
      )}
      {balanceNotes.length > 0 && (
        <Block title="Balance sheet" body={balanceNotes.join(" ")} />
      )}
      {snapshot.cash_quality && <Block title="Cash quality" body={snapshot.cash_quality} />}

      {snapshot.watch_items.length > 0 && (
        <div className="mt-5">
          <h3 className="text-micro text-faint">Worth a second look</h3>
          <ul className="mt-1.5 space-y-1">
            {snapshot.watch_items.map((watch) => (
              <li key={watch} className="text-[0.875rem] leading-relaxed text-muted">
                {watch}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function Block({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-5">
      <h3 className="text-micro text-faint">{title}</h3>
      <p className="mt-1 text-[0.875rem] leading-relaxed text-text/90">{body}</p>
    </div>
  );
}

/** Both cases built from the same filings, placed side by side deliberately. */
export function CasesView({ bull, bear }: { bull: string[]; bear: string[] }) {
  if (bull.length === 0 && bear.length === 0) return null;

  return (
    <section className="px-5 pt-7">
      <h2 className="font-serif text-[1.0625rem] text-text">The case either way</h2>
      <div className="mt-3 space-y-5">
        <Case label="For" points={bull} tone="text-up" />
        <Case label="Against" points={bear} tone="text-down" />
      </div>
    </section>
  );
}

function Case({ label, points, tone }: { label: string; points: string[]; tone: string }) {
  if (points.length === 0) return null;
  return (
    <div>
      <h3 className={`text-micro ${tone}`}>{label}</h3>
      <ul className="mt-1.5 space-y-1.5">
        {points.map((point) => (
          <li key={point} className="text-[0.875rem] leading-relaxed text-text/90">
            {point}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Provenance. Every claim above traces back to one of these documents. */
export function SourcesView({ data }: { data: Research }) {
  if (data.sources.length === 0) return null;
  return (
    <section className="px-5 pb-8 pt-7">
      <h2 className="text-micro text-faint">Read from</h2>
      <ul className="mt-1.5 space-y-1">
        {data.sources.map((source) => (
          <li key={source.url} className="text-[0.8125rem] leading-relaxed">
            {source.url.startsWith("http") ? (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted underline underline-offset-4"
              >
                {source.title}
              </a>
            ) : (
              <span className="text-muted">{source.title}</span>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-micro leading-relaxed text-faint">
        Annual reports and earnings-call transcripts only. No broker notes, no news.
      </p>
    </section>
  );
}
