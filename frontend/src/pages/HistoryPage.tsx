import { useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { ResultCard } from "../components/ResultCard";
import { SummaryMetrics } from "../components/RunSummary";
import { WarningBanner } from "../components/WarningBanner";
import { useRuns } from "../hooks/useRuns";
import type { RunDetail } from "../types";

export function HistoryPage() {
  const { items, isLoading, isLoadingMore, hasMore, error, loadMore, remove, refresh } = useRuns();
  const [selected, setSelected] = useState<RunDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isOpening, setIsOpening] = useState(false);

  async function openRun(runId: string) {
    setDetailError(null);
    setIsOpening(true);
    try {
      setSelected(await api.getRun(runId));
    } catch (caught) {
      setDetailError(caught instanceof ApiError ? caught.message : "Could not load the run.");
    } finally {
      setIsOpening(false);
    }
  }

  async function deleteRun(runId: string) {
    if (!window.confirm("Delete this saved shortlist?")) return;
    try {
      await remove(runId);
      if (selected?.run_id === runId) setSelected(null);
    } catch {
      return;
    }
  }

  return (
    <section className="page-section">
      <div className="page-intro">
        <div>
          <p className="eyebrow">History / Archive</p>
          <h1>Saved shortlists</h1>
          <p className="page-description">A durable record of the briefs you have run and the creators you kept.</p>
        </div>
        <div className="page-intro-meta">
          <span className="page-index">Archive / 02</span>
          <button className="secondary-button" type="button" onClick={() => void refresh()}>Refresh</button>
        </div>
      </div>

      {(error || detailError) && <div className="system-note system-note-error" role="alert"><span className="system-note-signal" aria-hidden="true" /><strong>Archive issue</strong><span>{error ?? detailError}</span></div>}
      {isLoading && <LoadingLedger />}

      <div className="history-layout">
        <aside className="history-ledger">
          <div className="ledger-heading"><span>Saved runs</span><span>{items.length}</span></div>
          <div className="history-list">
            {!isLoading && !items.length && <div className="empty-ledger"><p>No saved shortlists yet.</p><Link to="/search">Run a match <span aria-hidden="true">→</span></Link></div>}
            {items.map((item) => (
              <article className={`history-row ${selected?.run_id === item.run_id ? "history-row-active" : ""}`} key={item.run_id}>
                <button className="history-open" type="button" aria-current={selected?.run_id === item.run_id ? "true" : undefined} onClick={() => void openRun(item.run_id)}>
                  <span className="history-date">{formatDate(item.created_at)}</span>
                  <strong>{item.brief.niche} <span>/</span> {item.brief.platform}</strong>
                  <span className="history-meta">{item.n_results} results <i /> {item.n_strong} strong {item.has_warnings && <b>Notes</b>}</span>
                </button>
                <button className="delete-button" type="button" aria-label={`Delete ${item.brief.niche} run`} onClick={() => void deleteRun(item.run_id)}>Delete</button>
              </article>
            ))}
            {hasMore && <button className="text-button full-width" type="button" disabled={isLoadingMore} onClick={() => void loadMore()}>{isLoadingMore ? "Loading..." : "Load older runs"}</button>}
          </div>
        </aside>

        <div className="history-detail">
          {isOpening && <div className="empty-state"><span className="empty-index">LOADING</span><h2>Opening shortlist</h2></div>}
          {!isOpening && selected && (
            <>
              <div className="run-context">
                <div>
                  <p className="eyebrow">Run detail / {formatDate(selected.created_at)}</p>
                  <h2>{selected.brief.niche} <span>·</span> {selected.brief.platform}</h2>
                  <p className="run-context-line">{selected.brief.audience || "General audience"} <span>/</span> {selected.brief.vibe || "Versatile tone"}</p>
                </div>
                <a className="secondary-button" href={api.exportUrl(selected.run_id)} download>Export CSV</a>
              </div>
              <WarningBanner warnings={selected.warnings} />
              <SummaryMetrics summary={selected.summary} compact />
              <div className="result-list">
                {selected.ranked.map((entry) => {
                  const creator = selected.candidates.find((item) => item.id === entry.id);
                  return creator ? <ResultCard key={entry.id} creator={creator} entry={entry} brief={selected.brief} /> : null;
                })}
              </div>
            </>
          )}
          {!isOpening && !selected && <div className="empty-state"><span className="empty-index">SELECT</span><h2>Choose a saved run</h2><p>Open a shortlist to inspect its ranked creators and export the result.</p></div>}
        </div>
      </div>
    </section>
  );
}

function LoadingLedger() {
  return <div className="skeleton-ledger"><span /><span /><span /></div>;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
