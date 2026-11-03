"use client";

import { crore, DASH, metricLabel, pct } from "@/lib/format";
import type { ResultsEnrichment } from "@/types/api";

/**
 * The four headline numbers, QoQ and YoY.
 *
 * Honesty rules rendered into the component: a figure the extractor could not
 * find shows an em dash, and a comparison the backend refused to compute
 * (profit crossing zero, near-zero base) shows "n.m." rather than a
 * percentage that would read as information.
 */
export function ResultsPanel({ data }: { data: ResultsEnrichment }) {
  return (
    <div className="px-5 pb-4 pt-1">
      <div className="mb-2.5 flex items-baseline justify-between">
        <span className="font-serif text-[0.9375rem] text-text">{data.period}</span>
        <span className="text-micro text-faint">
          {data.basis} · {data.unit}
        </span>
      </div>

      <div className="scroll-x">
        <table className="w-full min-w-[19rem] border-collapse">
          <thead>
            <tr className="text-micro text-faint">
              <th className="pb-1.5 text-left font-normal">&nbsp;</th>
              <th className="pb-1.5 pl-2 text-right font-normal">Value</th>
              <th className="pb-1.5 pl-3 text-right font-normal">QoQ</th>
              <th className="pb-1.5 pl-3 text-right font-normal">YoY</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.metric} className="border-t border-line/60">
                <td className="py-2 text-[0.8125rem] text-muted">
                  {metricLabel(row.metric)}
                  {row.metric === "ebitda" && data.ebitda_derived && (
                    <span className="ml-1 text-faint" title="Derived from the P&L, not stated">
                      *
                    </span>
                  )}
                </td>
                <td className="tnum py-2 pl-2 text-right text-[0.9375rem] text-text">
                  {crore(row.value)}
                </td>
                <ChangeCell value={row.qoq_pct} signFlip={row.sign_flip} />
                <ChangeCell value={row.yoy_pct} signFlip={row.sign_flip} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-micro text-faint">
        {data.ebitda_margin_pct !== null && (
          <span>EBITDA margin {data.ebitda_margin_pct.toFixed(1)}%</span>
        )}
        {data.pat_margin_pct !== null && <span>PAT margin {data.pat_margin_pct.toFixed(1)}%</span>}
        {data.ebitda_derived && <span>* EBITDA derived from the P&amp;L</span>}
        {data.confidence < 0.5 && (
          <span className="text-signal">Table structure was ambiguous — check the filing</span>
        )}
      </div>
    </div>
  );
}

function ChangeCell({ value, signFlip }: { value: number | null; signFlip: boolean }) {
  if (value === null) {
    return (
      <td className="tnum py-2 pl-3 text-right text-[0.8125rem] text-faint">
        {signFlip ? "n.m." : DASH}
      </td>
    );
  }
  const tone = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted";
  return <td className={`tnum py-2 pl-3 text-right text-[0.8125rem] ${tone}`}>{pct(value)}</td>;
}
