import { useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorNote, NOTE_TITLES } from "../components/SystemNote";
import { PageIntro } from "../components/PageIntro";
import { ResultList } from "../components/ResultList";
import { Skeleton } from "../components/Skeleton";
import { RunContext } from "../components/RunContext";
import { SummaryMetrics } from "../components/RunSummary";
import { WarningBanner } from "../components/WarningBanner";
import { useResource } from "../hooks/useResource";
import { useRuns } from "../hooks/useRuns";
import { formatDate } from "../format";
import type { RunDetail } from "../types";

export function HistoryPage() {
  const { items, isLoading, isLoadingMore, hasMore, error, loadMore, remove, refresh } = useRuns();
  // Which run is open, not the run itself. Keying the fetch off an id means a
  // second click supersedes the first -- the old `setSelected(await getRun(a))`
  // had no such guard, so opening A then B quickly could land A's slower
  // response on top of B.
  const [openRunId, setOpenRunId] = useState<string | null>(null);
  const detail = useResource<RunDetail>(
    (signal) => api.getRun(openRunId!, { signal }),
    [openRunId],
    { enabled: openRunId !== null, fallbackError: "Could not load the run." },
  );
  const selected = detail.data;
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  // Delete had no in-flight state, so a double-click sent two DELETEs and the
  // second one raced the row out of the list it had already filtered.
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function deleteRun(runId: string) {
    if (deletingId) return;
    if (!window.confirm("Delete this saved shortlist?")) return;
    setDeletingId(runId);
    try {
      // `remove` re-throws after recording the message in the shared error slot,
      // so the failure is already on screen; this only has to not reject.
      await remove(runId);
      if (openRunId === runId) setOpenRunId(null);
    } catch {
      return;
    } finally {
      setDeletingId(null);
    }
  }

  function exportRun() {
    if (exporting) return;
    setExporting(true);
    setExportError(null);
    void api.downloadRun(selected!.run_id)
      .catch((caught) => setExportError(caught instanceof ApiError ? caught.message : "Could not export the run."))
      .finally(() => setExporting(false));
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

      {(error || detail.error) && <ErrorNote title={NOTE_TITLES.archive}>{error ?? detail.error}</ErrorNote>}
      {exportError && <ErrorNote title={NOTE_TITLES.export}>{exportError}</ErrorNote>}
      {isLoading && <Skeleton variant="ledger" />}

      <div className="history-layout">
        <aside className="history-ledger">
          <div className="ledger-heading"><span>Saved runs</span></div>
          <div className="history-list">
            {!isLoading && !items.length && <div className="empty-ledger"><p>No saved shortlists yet.</p><Link to="/search">Run a match <span aria-hidden="true">→</span></Link></div>}
            {items.map((item) => (
              <article className={`history-row ${selected?.run_id === item.run_id ? "history-row-active" : ""}`} key={item.run_id}>
                <button className="history-open" type="button" aria-current={openRunId === item.run_id ? "true" : undefined} onClick={() => setOpenRunId(item.run_id)}>
                  <span className="history-date">{formatDate(item.created_at)}</span>
                  <strong className="history-goal">{item.brief.goal}</strong>
                  <span className="history-meta">{item.n_results} results <i /> {item.n_strong} strong {item.has_warnings && <b>Notes</b>}</span>
                </button>
                <button
                  className="btn btn-ghost btn-danger-ghost delete-button"
                  type="button"
                  disabled={deletingId === item.run_id}
                  aria-busy={deletingId === item.run_id}
                  aria-label={`Delete run: ${item.brief.goal}`}
                  onClick={() => void deleteRun(item.run_id)}
                >
                  Delete
                </button>
              </article>
            ))}
            {hasMore && <button className="btn btn-ghost full-width" type="button" disabled={isLoadingMore} onClick={() => void loadMore()}>{isLoadingMore ? "Loading..." : "Load older runs"}</button>}
          </div>
        </aside>

        <div className="history-detail">
          {/* aria-busy/live: this replaced the detail pane with a heading, so a
           * sighted user saw progress while a screen-reader user heard nothing
           * and focus stayed on the ledger button they had just pressed. */}
          {detail.loading && <EmptyState title="Opening shortlist" busy />}
          {!detail.loading && selected && (
            <>
              <RunContext
                run={selected}
                label="Run detail"
                exporting={exporting}
                onExport={exportRun}
              />
              <WarningBanner warnings={selected.warnings} />
              <SummaryMetrics summary={selected.summary} compact />
              <ResultList run={selected} />
            </>
          )}
          {!detail.loading && !selected && (
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
