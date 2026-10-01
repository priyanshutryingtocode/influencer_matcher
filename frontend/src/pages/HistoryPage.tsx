import { useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorNote } from "../components/SystemNote";
import { PageIntro } from "../components/PageIntro";
import { ResultList } from "../components/ResultList";
import { RunContext } from "../components/RunContext";
import { SummaryMetrics } from "../components/RunSummary";
import { WarningBanner } from "../components/WarningBanner";
import { useRuns } from "../hooks/useRuns";
import { formatDate } from "../format";
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
      <PageIntro
        eyebrow="History / Archive"
        title="Saved shortlists"
        description="A durable record of the briefs you have run and the creators you kept."
        meta={(
          <button className="btn btn-secondary" type="button" disabled={isLoading} onClick={() => void refresh()}>
            {isLoading ? "Refreshing..." : "Refresh"}
          </button>
        )}
      />

      {(error || detailError) && <ErrorNote title="Archive issue">{error ?? detailError}</ErrorNote>}
      {isLoading && <LoadingLedger />}

      <div className="history-layout">
        <aside className="history-ledger">
          <div className="ledger-heading"><span>Saved runs</span></div>
          <div className="history-list">
            {!isLoading && !items.length && <div className="empty-ledger"><p>No saved shortlists yet.</p><Link to="/search">Run a match <span aria-hidden="true">→</span></Link></div>}
            {items.map((item) => (
              <article className={`history-row ${selected?.run_id === item.run_id ? "history-row-active" : ""}`} key={item.run_id}>
                <button className="history-open" type="button" aria-current={selected?.run_id === item.run_id ? "true" : undefined} onClick={() => void openRun(item.run_id)}>
                  <span className="history-date">{formatDate(item.created_at)}</span>
                  <strong className="history-goal">{item.brief.goal}</strong>
                  <span className="history-meta">{item.n_results} results <i /> {item.n_strong} strong {item.has_warnings && <b>Notes</b>}</span>
                </button>
                <button className="btn btn-ghost btn-danger-ghost delete-button" type="button" aria-label={`Delete run: ${item.brief.goal}`} onClick={() => void deleteRun(item.run_id)}>Delete</button>
              </article>
            ))}
            {hasMore && <button className="btn btn-ghost full-width" type="button" disabled={isLoadingMore} onClick={() => void loadMore()}>{isLoadingMore ? "Loading..." : "Load older runs"}</button>}
          </div>
        </aside>

        <div className="history-detail">
          {/* aria-busy/live: this replaced the detail pane with a heading, so a
           * sighted user saw progress while a screen-reader user heard nothing
           * and focus stayed on the ledger button they had just pressed. */}
          {isOpening && <EmptyState title="Opening shortlist" busy />}
          {!isOpening && selected && (
            <>
              <RunContext
                brief={selected.brief}
                createdAt={selected.created_at}
                label="Run detail"
                onExport={() => void api.downloadRun(selected.run_id).catch((caught) => setDetailError(caught instanceof ApiError ? caught.message : "Could not export the run."))}
              />
              <WarningBanner warnings={selected.warnings} />
              <SummaryMetrics summary={selected.summary} compact />
              <ResultList run={selected} />
            </>
          )}
          {!isOpening && !selected && (
            <EmptyState
              index="SELECT"
              title="Choose a saved run"
              body="Open a shortlist to inspect its ranked creators and export the result."
            />
          )}
        </div>
      </div>
    </section>
  );
}

function LoadingLedger() {
  return <div className="skeleton-ledger"><span /><span /><span /></div>;
}
