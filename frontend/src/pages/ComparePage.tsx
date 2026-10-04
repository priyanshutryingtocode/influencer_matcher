import { useMemo, useState } from "react";

import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorNote, InfoNote, NOTE_TITLES } from "../components/SystemNote";
import { PageIntro } from "../components/PageIntro";
import { ResultList } from "../components/ResultList";
import { formatFollowers } from "../components/RunSummary";
import { WarningBanner } from "../components/WarningBanner";
import { useResource } from "../hooks/useResource";
import { formatDate } from "../format";
import type { Comparison, RunDetail, RunListItem, RunListResponse } from "../types";

export function ComparePage() {
  const [runA, setRunA] = useState("");
  const [runB, setRunB] = useState("");

  const list = useResource<RunListResponse>(
    (signal) => api.listRuns(undefined, { signal }),
    [],
    {
      fallbackError: "Could not load saved runs.",
      onLoad: (response) => {
        setRunA(response.items[0]?.run_id ?? "");
        setRunB(response.items[1]?.run_id ?? "");
      },
    },
  );
  const runs = list.data?.items ?? [];

  // Two errors, not one. The list fetch and the compare fetch shared an `error`
  // slot, so a failed comparison could render the "could not load saved runs"
  // panel, and a failed list could blank the toolbar with a comparison message.
  const ready = Boolean(runA && runB && runA !== runB);
  const compare = useResource<{ comparison: Comparison; details: Details }>(
    async (signal) => {
      const [comparison, detailA, detailB] = await Promise.all([
        api.compareRuns(runA, runB),
        api.getRun(runA, { signal }),
        api.getRun(runB, { signal }),
      ]);
      return { comparison, details: { a: detailA, b: detailB } };
    },
    [runA, runB],
    { enabled: ready, fallbackError: "Could not compare those runs." },
  );
  // Derived rather than reset: an unselectable pair reads as "no comparison"
  // without an effect clearing state the render has already decided is stale.
  const emptyDetails: Details = { a: null, b: null };
  const comparison = ready ? compare.data?.comparison ?? null : null;
  const details = ready ? compare.data?.details ?? emptyDetails : emptyDetails;
  const isComparing = compare.loading;

  const sharedKeys = useMemo(
    () => new Set(comparison?.shared_creators.map((creator) => creator.creator_key) ?? []),
    [comparison],
  );

  function swapRuns() {
    setRunA(runB);
    setRunB(runA);
  }

  if (list.loading) return <div className="loading-panel page-section">Loading saved runs...</div>;
  // A failed list is not an empty list. Rendering the "save two shortlists"
  // state underneath the error told the user to go and do something they had
  // already done, and offered no way back.
  if (list.error && !runs.length) {
    return (
      <section className="page-section">
        <ErrorNote
          title={NOTE_TITLES.archive}
          action={<button className="btn btn-ghost" type="button" onClick={list.retry}>Retry</button>}
        >
          {list.error}
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
      {compare.error && (
        <ErrorNote
          title={NOTE_TITLES.comparison}
          action={<button className="btn btn-ghost" type="button" onClick={compare.retry}>Retry</button>}
        >
          {compare.error}
        </ErrorNote>
      )}

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
            <CompareColumn title="Run A" detail={details.a} sharedKeys={sharedKeys} />
            <CompareColumn title="Run B" detail={details.b} sharedKeys={sharedKeys} />
          </div>
        </>
      )}
    </section>
  );
}

type Details = { a: RunDetail | null; b: RunDetail | null };

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

/** How a metric reads on its own, and how a change between two of them reads.
 *  Both are needed because the units differ: a difference of two percentages is
 *  percentage points, and a difference of two follower counts is not a
 *  percentage at all. The old single `suffix` produced "+5.7%" for engagement
 *  and "+13873" for reach, which were both the wrong unit for a delta. */
interface MetricFormat {
  value: (n: number) => string;
  delta: (difference: number) => string;
}

/** Three-way, because every delta below is rendered from an unsigned magnitude:
 *  a sign helper that only ever added "+" turned a 14K reach decline into "14K",
 *  which reads as a gain. */
function sign(value: number): string {
  return value > 0 ? "+" : value < 0 ? "-" : "";
}

const INTEGER: MetricFormat = {
  value: (n) => String(n),
  delta: (difference) => `${sign(difference)}${Math.abs(difference)}`,
};

const PERCENT: MetricFormat = {
  value: (n) => `${n.toFixed(1)}%`,
  delta: (difference) => `${sign(difference)}${Math.abs(difference).toFixed(1)}pp`,
};

const FOLLOWERS: MetricFormat = {
  value: formatFollowers,
  // formatFollowers drops the sign, so the magnitude has to be unsigned here and
  // the sign reapplied outside it.
  delta: (difference) => `${sign(difference)}${formatFollowers(Math.abs(difference))}`,
};

function ComparisonOverview({ comparison }: { comparison: Comparison }) {
  const a = comparison.summary_a;
  const b = comparison.summary_b;
  return (
    <div className="compare-overview">
      <div className="overview-primary"><span>Shared creators</span><strong>{comparison.shared_creators.length}</strong><small>appear in both shortlists</small></div>
      {/* Every metric either column used to print as an absolute value in its
       * own SummaryMetrics strip. That put 14 cells on the page to carry 7
       * numbers, and put each delta in a different row from the two values it
       * is the difference of. One surface now, showing both ends of the change. */}
      <Delta label="Strong fits" valueA={a.n_strong} valueB={b.n_strong} format={INTEGER} />
      <Delta label="Avg similarity" valueA={a.avg_match_pct} valueB={b.avg_match_pct} format={PERCENT} />
      <Delta label="Avg engagement" valueA={a.avg_engagement_pct} valueB={b.avg_engagement_pct} format={PERCENT} />
      <Delta label="Median reach" valueA={a.median_followers} valueB={b.median_followers} format={FOLLOWERS} />
      <Delta label="Needs review" valueA={a.n_weak} valueB={b.n_weak} format={INTEGER} />
    </div>
  );
}

function Delta({ label, valueA, valueB, format }: { label: string; valueA: number; valueB: number; format: MetricFormat }) {
  const difference = valueB - valueA;
  const direction = difference > 0 ? "delta-up" : difference < 0 ? "delta-down" : "";
  return (
    <div className="overview-delta">
      <span>{label}</span>
      <strong className={direction}>{format.delta(difference)}</strong>
      {/* Replaces a "B vs A" caption that named the direction without giving
       * the reader either number, so a delta could not be interpreted. */}
      <small>{format.value(valueA)} → {format.value(valueB)}</small>
    </div>
  );
}

function OverlapList({ comparison, details }: { comparison: Comparison; details: { a: RunDetail | null; b: RunDetail | null } }) {
  const shared = comparison.shared_creators;
  return (
    <div className="overlap-list">
      <div className="section-heading compact"><div><p className="eyebrow">Overlap</p><h2>Creators in both runs</h2></div><span className="section-count">{shared.length} shared</span></div>
      {/* No overlap is a result, not a system condition, so it reads as muted
       * body text under the heading rather than as a note. It also used to
       * return early, which removed this whole section and left the message
       * floating alone with no heading above it. */}
      {shared.length === 0
        ? <p className="overlap-empty">These two runs do not share a ranked creator.</p>
        : (
          <div className="overlap-items">
            {shared.map((creator) => (
              <div className="overlap-item" key={creator.creator_key}>
                <strong>{creator.handle}</strong>
                <RankShift detailA={details.a} detailB={details.b} creatorId={creator.id} />
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

/** Rank in A against rank in B, with the movement spelled out. The chips used to
 *  print "#3 / #7", which left the reader to work out that the creator dropped
 *  four places -- the single most useful fact on the page, left as arithmetic. */
function RankShift({ detailA, detailB, creatorId }: { detailA: RunDetail | null; detailB: RunDetail | null; creatorId: number }) {
  const rankA = rankFor(detailA, creatorId);
  const rankB = rankFor(detailB, creatorId);
  if (rankA === "—" || rankB === "—") {
    return <span>#{rankA} <i>/</i> #{rankB}</span>;
  }
  // Rank 1 is best, so a lower number in B is an improvement: a - b is positive
  // when B climbed.
  const climb = rankA - rankB;
  return (
    <span>
      #{rankA} <i>→</i> #{rankB}
      {climb !== 0 && (
        <>{" "}<b className={climb > 0 ? "delta-up" : "delta-down"}>{climb > 0 ? "▲" : "▼"}{Math.abs(climb)}</b></>
      )}
    </span>
  );
}

function CompareColumn({ title, detail, sharedKeys }: { title: string; detail: RunDetail | null; sharedKeys: Set<string> }) {
  return (
    <div className="compare-column">
      {/* Date and result count rather than the goal again: the goal is already
       * on screen twice in the selects directly above, and it was a third and
       * fourth time here, in full, one per column. */}
      <div className="compare-column-heading">
        <span className="eyebrow">{title}</span>
        {detail && <span>{formatDate(detail.created_at)} · {detail.ranked.length} results</span>}
      </div>
      {/* These columns were the only place in the app showing a run's quality
       * without its warnings, so a quota fallback on one side of the
       * comparison looked identical to a clean run. */}
      {detail && <WarningBanner warnings={detail.warnings} />}
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
