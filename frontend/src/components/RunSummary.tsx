import { useId, useState } from "react";

import type { RunSummary } from "../types";

export const SIMILARITY_EXPLANATION =
  "Mean cosine similarity between the brief's embedding and each shortlisted "
  + "creator's. This is an embedding distance, not a fit score: it is useful for "
  + "comparing one brief against another, but it does not reliably rank creators "
  + "within a single shortlist. Use the strong-fit count for that.";

interface MetricCell {
  label: string;
  value: string;
  caption: string;
  /** The cell's value is the headline; rendered in the signal colour. */
  primary?: boolean;
  /** A caveat worth reaching on demand. The similarity number is the one
   *  metric here that can be misread as a fit score, so it carries the
   *  explanation rather than leaving it to a hover-only tooltip. */
  explanation?: string;
}

function metricCells(summary: RunSummary): MetricCell[] {
  return [
    { label: "Quality", value: `${summary.n_strong}/${summary.n_results}`, caption: "strong fits", primary: true },
    { label: "Avg similarity", value: `${summary.avg_match_pct.toFixed(1)}%`, caption: "cosine vs. brief", explanation: SIMILARITY_EXPLANATION },
    { label: "Avg engagement", value: `${summary.avg_engagement_pct.toFixed(1)}%`, caption: "reach quality" },
    { label: "Median reach", value: formatFollowers(summary.median_followers), caption: "followers" },
    { label: "Needs review", value: String(summary.n_weak), caption: "weak fits" },
  ];
}

export function SummaryMetrics({ summary, compact = false }: { summary: RunSummary; compact?: boolean }) {
  const [explained, setExplained] = useState(false);
  const explanationId = useId();

  return (
    <dl className={`summary-strip ${compact ? "summary-strip-compact" : ""}`}>
      {metricCells(summary).map((cell) => {
        const body = (
          <>
            <strong>{cell.value}</strong>
            <span>{cell.caption}</span>
            {cell.explanation && explained && (
              <span className="summary-explain-body" id={explanationId}>{cell.explanation}</span>
            )}
          </>
        );
        return (
          <div className={`summary-item ${cell.primary ? "summary-item-primary" : ""}`} key={cell.label}>
            {cell.explanation
              ? (
                /* A disclosure, not a title= attribute: a <dt> is not focusable,
                 * so the caveat used to be reachable by mouse only. */
                <dt>
                  <button
                    className="summary-explain-toggle"
                    type="button"
                    aria-expanded={explained}
                    aria-controls={explained ? explanationId : undefined}
                    onClick={() => setExplained((open) => !open)}
                  >
                    {cell.label}
                    <span className="summary-explain-icon" aria-hidden="true">?</span>
                  </button>
                </dt>
              )
              : <dt>{cell.label}</dt>}
            <dd>{body}</dd>
          </div>
        );
      })}
    </dl>
  );
}

export function formatFollowers(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}K`;
  return String(value);
}
