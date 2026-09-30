import type { RunSummary } from "../types";

export const SIMILARITY_EXPLANATION =
  "Mean cosine similarity between the brief's embedding and each shortlisted "
  + "creator's. This is an embedding distance, not a fit score: it is useful for "
  + "comparing one brief against another, but it does not reliably rank creators "
  + "within a single shortlist. Use the strong-fit count for that.";

export function SummaryMetrics({ summary, compact = false }: { summary: RunSummary; compact?: boolean }) {
  return (
    <dl className={`summary-strip ${compact ? "summary-strip-compact" : ""}`}>
      <div className="summary-item summary-item-primary">
        <dt>Quality</dt>
        <dd><strong>{summary.n_strong}/{summary.n_results}</strong><span>strong fits</span></dd>
      </div>
      <div className="summary-item">
        <dt title={SIMILARITY_EXPLANATION}>Avg similarity</dt>
        <dd title={SIMILARITY_EXPLANATION}><strong>{summary.avg_match_pct.toFixed(1)}%</strong><span>cosine vs. brief</span></dd>
      </div>
      <div className="summary-item">
        <dt>Avg engagement</dt>
        <dd><strong>{summary.avg_engagement_pct.toFixed(1)}%</strong><span>reach quality</span></dd>
      </div>
      <div className="summary-item">
        <dt>Median reach</dt>
        <dd><strong>{formatFollowers(summary.median_followers)}</strong><span>followers</span></dd>
      </div>
      <div className="summary-item">
        <dt>Needs review</dt>
        <dd><strong>{summary.n_weak}</strong><span>weak fits</span></dd>
      </div>
    </dl>
  );
}

export function formatFollowers(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}K`;
  return String(value);
}
