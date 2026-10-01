import { useEffect, useMemo, useState } from "react";

import { api, ApiError } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorNote, InfoNote } from "../components/SystemNote";
import { PageIntro } from "../components/PageIntro";
import { ResultList } from "../components/ResultList";
import { SummaryMetrics } from "../components/RunSummary";
import { WarningBanner } from "../components/WarningBanner";
import { formatDate } from "../format";
import type { Comparison, RunDetail, RunListItem } from "../types";

export function ComparePage() {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [runA, setRunA] = useState("");
  const [runB, setRunB] = useState("");
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [details, setDetails] = useState<{ a: RunDetail | null; b: RunDetail | null }>({ a: null, b: null });
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isComparing, setIsComparing] = useState(false);
  const [listAttempt, setListAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    void api.listRuns()
      .then((response) => {
        if (!active) return;
        setRuns(response.items);
        setRunA(response.items[0]?.run_id ?? "");
        setRunB(response.items[1]?.run_id ?? "");
      })
      .catch((caught) => {
        if (active) setError(caught instanceof ApiError ? caught.message : "Could not load saved runs.");
      })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, [listAttempt]);

  useEffect(() => {
    if (!runA || !runB || runA === runB) {
      setComparison(null);
      setDetails({ a: null, b: null });
      setIsComparing(false);
      return;
    }
    let active = true;
    setIsComparing(true);
    setError(null);
    void Promise.all([api.compareRuns(runA, runB), api.getRun(runA), api.getRun(runB)])
      .then(([nextComparison, detailA, detailB]) => {
        if (!active) return;
        setComparison(nextComparison);
        setDetails({ a: detailA, b: detailB });
      })
      .catch((caught) => {
        if (active) setError(caught instanceof ApiError ? caught.message : "Could not compare those runs.");
      })
      .finally(() => { if (active) setIsComparing(false); });
    return () => { active = false; };
  }, [runA, runB]);

  const sharedKeys = useMemo(
    () => new Set(comparison?.shared_creators.map((creator) => creator.creator_key) ?? []),
    [comparison],
  );

  function swapRuns() {
    setRunA(runB);
    setRunB(runA);
  }

  if (isLoading) return <div className="loading-panel page-section">Loading saved runs...</div>;
  // A failed list is not an empty list. Rendering the "save two shortlists"
  // state underneath the error told the user to go and do something they had
  // already done, and offered no way back.
  if (error && !runs.length) {
    return (
      <section className="page-section">
        <ErrorNote
          title="Comparison issue"
          action={<button className="btn btn-ghost" type="button" onClick={() => setListAttempt((n) => n + 1)}>Retry</button>}
        >
          {error}
        </ErrorNote>
      </section>
    );
  }
  if (runs.length < 2) {
    return (
      <div className="page-section">
        <EmptyState
          index="COMPARE"
          title="Two runs make a comparison."
          body="Save at least two shortlists to see overlap, quality changes, and rank movement."
        />
      </div>
    );
  }

  return (
    <section className="page-section">
      <PageIntro
        eyebrow="Compare / Analysis"
        title="Put two shortlists side by side."
        description="See what stayed, what changed, and where the quality moved."
      />
      {error && <ErrorNote title="Comparison issue">{error}</ErrorNote>}

      <div className="compare-toolbar">
        <RunSelect label="Run A" value={runA} runs={runs} onChange={setRunA} />
        <button className="btn btn-ghost swap-button" type="button" onClick={swapRuns} aria-label="Swap runs">Swap <span aria-hidden="true">↔</span></button>
        <RunSelect label="Run B" value={runB} runs={runs} onChange={setRunB} />
      </div>

      {runA === runB && <InfoNote title="Choose two different runs">The comparison will appear here.</InfoNote>}
      {isComparing && <div className="compare-loading" aria-live="polite"><span className="loading-bar" />Updating comparison...</div>}

      {comparison && !isComparing && (
        <>
          <ComparisonOverview comparison={comparison} />
          <OverlapList comparison={comparison} details={details} />
          <div className="compare-columns">
            <CompareColumn title="Run A" detail={details.a} summary={comparison.summary_a} sharedKeys={sharedKeys} />
            <CompareColumn title="Run B" detail={details.b} summary={comparison.summary_b} sharedKeys={sharedKeys} />
          </div>
        </>
      )}
    </section>
  );
}

function RunSelect({ label, value, runs, onChange }: { label: string; value: string; runs: RunListItem[]; onChange: (value: string) => void }) {
  return (
    <label className="compare-select">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {runs.map((run) => <option value={run.run_id} key={run.run_id}>{labelFor(run)}</option>)}
      </select>
    </label>
  );
}

function ComparisonOverview({ comparison }: { comparison: Comparison }) {
  return (
    <div className="compare-overview">
      <div className="overview-primary"><span>Shared creators</span><strong>{comparison.shared_creators.length}</strong><small>appear in both shortlists</small></div>
      <Delta label="Strong fits" valueA={comparison.summary_a.n_strong} valueB={comparison.summary_b.n_strong} />
      <Delta label="Avg engagement" valueA={comparison.summary_a.avg_engagement_pct} valueB={comparison.summary_b.avg_engagement_pct} suffix="%" />
      <Delta label="Median reach" valueA={comparison.summary_a.median_followers} valueB={comparison.summary_b.median_followers} />
    </div>
  );
}

function Delta({ label, valueA, valueB, suffix = "" }: { label: string; valueA: number; valueB: number; suffix?: string }) {
  const difference = valueB - valueA;
  const display = `${difference > 0 ? "+" : ""}${Number.isInteger(difference) ? difference : difference.toFixed(1)}${suffix}`;
  return (
    <div className="overview-delta">
      <span>{label}</span>
      <strong className={difference > 0 ? "delta-up" : difference < 0 ? "delta-down" : ""}>{display}</strong>
      <small>B vs A</small>
    </div>
  );
}

function OverlapList({ comparison, details }: { comparison: Comparison; details: { a: RunDetail | null; b: RunDetail | null } }) {
  if (!comparison.shared_creators.length) {
    return <InfoNote title="No overlap">These runs do not share a ranked creator.</InfoNote>;
  }
  return (
    <div className="overlap-list">
      <div className="section-heading compact"><div><p className="eyebrow">Overlap</p><h2>Creators in both runs</h2></div><span className="section-count">{comparison.shared_creators.length} shared</span></div>
      <div className="overlap-items">
        {comparison.shared_creators.map((creator) => (
          <div className="overlap-item" key={creator.creator_key}>
            <strong>{creator.handle}</strong>
            <span>#{rankFor(details.a, creator.id)} <i>/</i> #{rankFor(details.b, creator.id)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CompareColumn({ title, detail, summary, sharedKeys }: { title: string; detail: RunDetail | null; summary: Comparison["summary_a"]; sharedKeys: Set<string> }) {
  return (
    <div className="compare-column">
      <div className="compare-column-heading"><span className="eyebrow">{title}</span>{detail && <span>{detail.brief.goal}</span>}</div>
      {/* These columns were the only place in the app showing a run's quality
       * without its warnings, so a quota fallback on one side of the
       * comparison looked identical to a clean run. */}
      {detail && <WarningBanner warnings={detail.warnings} />}
      <SummaryMetrics summary={summary} compact />
      {detail
        ? <ResultList run={detail} highlightKeys={sharedKeys} className="compare-result-list" />
        : <div className="empty-ledger">No run details loaded.</div>}
    </div>
  );
}

function rankFor(detail: RunDetail | null, creatorId: number) {
  return detail?.ranked.find((entry) => entry.id === creatorId)?.rank ?? "—";
}

function labelFor(run: RunListItem): string {
  return `${formatDate(run.created_at)} · ${run.brief.goal}`;
}
