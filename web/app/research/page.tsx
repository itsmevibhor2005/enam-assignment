"use client";

import { useEffect, useState } from "react";

import { PromiseTimeline } from "@/components/research/PromiseTimeline";
import { CasesView, SnapshotView, SourcesView } from "@/components/research/ResearchViews";
import { Empty, ErrorNote } from "@/components/shared/Primitives";
import { useCompanies, useResearch } from "@/lib/hooks/useApi";

/**
 * Research — the pull side.
 *
 * Any NSE symbol works, not just the portfolio. A cold ticker runs the whole
 * pipeline live, which takes real time, so the wait is narrated as the actual
 * steps rather than hidden behind a spinner: the investor should understand
 * that documents are being read, because that is what makes the output
 * trustworthy.
 */
const STEPS = [
  "Finding this company's filings",
  "Reading the annual report",
  "Reading four quarters of earnings calls",
  "Checking what management promised against what they reported",
];

export default function ResearchPage() {
  const [symbol, setSymbol] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const companies = useCompanies();
  const research = useResearch(symbol);

  const submit = (value: string) => {
    const next = value.trim().toUpperCase();
    if (next) {
      setSymbol(next);
      setInput(next);
    }
  };

  return (
    <div>
      <header className="px-5 pb-4 pt-7">
        <h1 className="font-serif text-[1.5rem] text-text">Research</h1>
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-faint">
          Any NSE ticker. Grounded only in the company&apos;s own filings.
        </p>
      </header>

      <div className="px-5 pb-4">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit(input);
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="RELIANCE"
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            aria-label="NSE ticker"
            className="h-11 min-w-0 flex-1 rounded-sm border border-line bg-surface px-3 font-serif text-[0.9375rem] text-text placeholder:text-faint focus:border-muted focus:outline-none"
          />
          <button
            type="submit"
            disabled={!input.trim()}
            className="h-11 shrink-0 rounded-sm bg-raised px-4 text-[0.875rem] text-text disabled:text-faint"
          >
            Analyse
          </button>
        </form>
      </div>

      {!symbol && companies.data && (
        <TickerShortcuts
          companies={companies.data}
          onPick={(value) => submit(value)}
        />
      )}

      {research.isLoading && <Pipeline symbol={symbol ?? ""} />}

      {research.isError && (
        <ErrorNote
          message={(research.error as Error)?.message ?? "That analysis could not be completed."}
          onRetry={() => research.refetch()}
        />
      )}

      {research.data && <ResearchResult data={research.data} />}
    </div>
  );
}

function TickerShortcuts({
  companies,
  onPick,
}: {
  companies: { symbol: string; name: string; in_portfolio: boolean }[];
  onPick: (symbol: string) => void;
}) {
  const outside = companies.filter((company) => !company.in_portfolio);
  const inside = companies.filter((company) => company.in_portfolio).slice(0, 8);

  return (
    <div className="px-5 pb-6">
      {outside.length > 0 && (
        <Group title="Outside your portfolio" items={outside} onPick={onPick} />
      )}
      <Group title="Your holdings" items={inside} onPick={onPick} />
    </div>
  );
}

function Group({
  title,
  items,
  onPick,
}: {
  title: string;
  items: { symbol: string; name: string }[];
  onPick: (symbol: string) => void;
}) {
  return (
    <div className="mt-4 first:mt-0">
      <h2 className="text-micro text-faint">{title}</h2>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {items.map((item) => (
          <button
            key={item.symbol}
            onClick={() => onPick(item.symbol)}
            className="rounded-sm bg-surface px-2.5 py-1.5 font-serif text-[0.8125rem] text-muted"
          >
            {item.symbol}
          </button>
        ))}
      </div>
    </div>
  );
}

function Pipeline({ symbol }: { symbol: string }) {
  const [step, setStep] = useState(0);

  // Advancing on a timer is honest here: these steps genuinely run in this
  // order, and the alternative is an unexplained two-minute spinner.
  useEffect(() => {
    setStep(0);
    const timer = setInterval(() => setStep((value) => Math.min(value + 1, STEPS.length - 1)), 9000);
    return () => clearInterval(timer);
  }, [symbol]);

  return (
    <div className="px-5 py-8">
      <p className="font-serif text-[1.0625rem] text-text">Working through {symbol}</p>
      <ol className="mt-4 space-y-2.5">
        {STEPS.map((label, index) => (
          <li
            key={label}
            className={`flex items-start gap-3 text-[0.875rem] leading-snug ${
              index <= step ? "text-text" : "text-faint"
            }`}
          >
            <span
              aria-hidden
              className={`mt-[0.45rem] h-1.5 w-1.5 shrink-0 rounded-full ${
                index < step ? "bg-muted" : index === step ? "animate-pulse bg-signal" : "bg-line"
              }`}
            />
            {label}
          </li>
        ))}
      </ol>
      <p className="mt-5 text-micro leading-relaxed text-faint">
        First look at a company takes a minute or two. After that it is instant.
      </p>
    </div>
  );
}

function ResearchResult({ data }: { data: Parameters<typeof SnapshotView>[0]["data"] }) {
  const nothing =
    !data.snapshot && data.guidance.length === 0 && data.bull.length === 0;

  return (
    <div>
      <div className="hairline px-5 pb-4">
        <div className="flex items-baseline gap-2">
          <h2 className="font-serif text-[1.25rem] text-text">{data.symbol}</h2>
          {data.in_portfolio && <span className="text-micro text-faint">In your portfolio</span>}
        </div>
        <p className="text-[0.8125rem] text-muted">{data.name}</p>
      </div>

      {data.warnings.length > 0 && (
        <div className="border-b border-line bg-surface px-5 py-3">
          {data.warnings.map((warning) => (
            <p key={warning} className="text-[0.8125rem] leading-relaxed text-muted">
              {warning}
            </p>
          ))}
        </div>
      )}

      {nothing ? (
        <Empty title="There were no annual reports or transcripts to read for this ticker. Try one with published filings." />
      ) : (
        <>
          <SnapshotView data={data} />
          <PromiseTimeline
            items={data.guidance}
            scorecard={data.scorecard}
            quarters={data.quarters_covered}
            note={data.guidance_note}
          />
          <CasesView bull={data.bull} bear={data.bear} />
          <SourcesView data={data} />
        </>
      )}
    </div>
  );
}
