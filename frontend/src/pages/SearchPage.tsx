import { useState } from "react";
import type { FormEvent } from "react";

import { api, ApiError } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { EmptyWorkspace } from "../components/EmptyWorkspace";
import { ErrorNote, NOTE_TITLES } from "../components/SystemNote";
import { PageIntro } from "../components/PageIntro";
import { RangeControl } from "../components/RangeControl";
import { ResultList } from "../components/ResultList";
import { RunContext } from "../components/RunContext";
import { RunStatus } from "../components/RunStatus";
import { SummaryMetrics } from "../components/RunSummary";
import { WarningBanner } from "../components/WarningBanner";
import { useMatchJob } from "../hooks/useMatchJob";
import { Skeleton } from "../components/Skeleton";
import { useResource } from "../hooks/useResource";
import type { Brief, Meta, RunDetail } from "../types";

const emptyBrief: Brief = {
  goal: "",
  platform: "Any",
  audience: "",
  vibe: "",
};

const goalSuggestions = [
  "a thrifted-vintage clothing label for Gen Z who care about slow fashion",
  "budget-friendly travel planning for solo backpackers",
  "skincare routines for sensitive skin, taught inclusively",
  "data-driven investing basics for first-time buyers",
];


const FALLBACK_LIMITS: Meta["limits"] = {
  goal_min_length: 20,
  goal_max_length: 1000,
  audience_max_length: 300,
  vibe_max_length: 500,
  top_k_min: 1,
  top_k_max: 50,
  top_n_min: 1,
  top_n_max: 10,
};

function resolveLimits(meta: Meta | null): Meta["limits"] {
  if (!meta?.limits) return FALLBACK_LIMITS;
  return { ...FALLBACK_LIMITS, ...meta.limits };
}

export function SearchPage() {
  const [brief, setBrief] = useState<Brief>(emptyBrief);
  const [topK, setTopK] = useState(10);
  const [topN, setTopN] = useState(5);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const { job, error, isRunning, start } = useMatchJob();
  const [hasStarted, setHasStarted] = useState(false);

  const meta = useResource<Meta>(
    (signal) => api.getMeta({ signal }),
    [],
    {
      fallbackError: "Could not load API metadata.",
      onLoad: (value) => {
        setBrief((current) => ({

          goal: current.goal || value.defaults?.goal || "",
          platform: value.platforms.includes(current.platform) ? current.platform : value.platforms[0] ?? current.platform,
          audience: value.defaults?.audience ?? "",
          vibe: value.defaults?.vibe ?? "",
        }));
        setTopK(value.defaults?.top_k ?? 10);
        setTopN(value.defaults?.top_n ?? 5);
      },
    },
  );

  const run = useResource<RunDetail>(
    (signal) => api.getRun(job!.run_id!, { signal }),
    [job?.run_id],
    {
      // The job reports success before the shortlist is readable. 
      enabled: job?.status === "succeeded" && Boolean(job.run_id) && job.outcome !== "no_results",
      fallbackError: "Could not load the completed run.",
    },
  );

  function updateBrief(field: keyof Brief, value: string) {
    setBrief((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setHasStarted(true);
    run.setData(null);
    run.setError(null);
    await start(brief, { top_k: topK, top_n: topN });
  }

  const metaValue = meta.data;
  const runDetail = run.data;
  const needsReindex = metaValue?.index.status === "reindex_required";
  const disabled = metaValue ? metaValue.index.status !== "ready" : false;
  const limits = resolveLimits(metaValue);
  // Read through a local rather than off the state object, so a brief missing
  // a field cannot throw on a later render.
  const goal = brief.goal ?? "";
  const goalLength = goal.trim().length;
  const goalTooShort = goalLength > 0 && goalLength < limits.goal_min_length;
  const awaitingRun = job?.status === "succeeded"
    && !runDetail
    && (run.loading || !run.error)
    && job.outcome !== "no_results";

  return (
    <section className="page-section">
      <PageIntro
        eyebrow="New match"
        title="Search"
        description="Look up creators based on your requirements."
        meta={metaValue && (
          <span className={`readiness ${disabled ? "readiness-off" : "readiness-on"}`}>
            <span className="readiness-dot" />
            {needsReindex
              ? "Index needs re-embedding"
              : disabled
                ? "Index unavailable"
                : `${metaValue.index.count.toLocaleString()} creators indexed`}
          </span>
        )}
      />

      {meta.error && (
        <ErrorNote
          title={NOTE_TITLES.connection}
          action={<button className="btn btn-ghost" type="button" onClick={meta.retry}>Retry</button>}
        >
          {meta.error}
        </ErrorNote>
      )}
      {!metaValue && !meta.error && <Skeleton variant="form" />}

      {metaValue && (
        <div className="match-workspace">
          <aside className="brief-rail">
            <div className="rail-heading"><span>Brief</span></div>
            <form className="brief-form" onSubmit={submit}>
              <div className="brief-fields">
                <label className="brief-field" htmlFor="goal">
                  <span id="goal-label">What are you promoting?</span>
                  <textarea
                    id="goal"
                    value={goal}
                    maxLength={limits.goal_max_length}
                    placeholder="Describe the product or campaign in your own words."
                    onChange={(event) => updateBrief("goal", event.target.value)}
                    rows={5}
                    aria-labelledby="goal-label"
                    aria-describedby="goal-count"
                  />
                  <span className="field-count" id="goal-count">{goalLength}/{limits.goal_max_length}</span>
                </label>
                {!goal.trim() && (
                  <div className="suggestion-chips" role="group" aria-label="Example briefs">
                    {goalSuggestions.map((suggestion) => (
                      <button key={suggestion} className="chip" type="button" onClick={() => updateBrief("goal", suggestion)}>
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
                <label className="brief-field" htmlFor="platform">
                  <span>Platform</span>
                  <select id="platform" value={brief.platform} onChange={(event) => updateBrief("platform", event.target.value)}>
                    {metaValue.platforms.map((platform) => <option key={platform}>{platform}</option>)}
                  </select>
                </label>
                <label className="brief-field" htmlFor="audience">
                  <span>Target audience <em>optional</em></span>
                  <input id="audience" value={brief.audience} maxLength={limits.audience_max_length} placeholder="e.g. GenZ, first-time buyers" onChange={(event) => updateBrief("audience", event.target.value)} />
                </label>
                <label className="brief-field" htmlFor="vibe">
                  <span>Vibe or tone <em>optional</em></span>
                  <textarea id="vibe" value={brief.vibe} maxLength={limits.vibe_max_length} placeholder="e.g. warm, practical" onChange={(event) => updateBrief("vibe", event.target.value)} rows={2} />
                </label>
              </div>
              <div className="rail-divider" />
              <div className="retrieval-controls">
                <div className="control-heading"><span>Search depth</span><span className="control-value">{topK} → {topN}</span></div>
                <RangeControl id="top-k" label="Candidates retrieved" value={topK} min={limits.top_k_min} max={limits.top_k_max} onChange={(next) => { setTopK(next); if (topN > next) setTopN(next); }} />
                {/* The shortlist cannot exceed what was retrieved, and the API
                  * also publishes its own ceiling. This used to read the
                  * backend's top_n_max nowhere. */}
                <RangeControl id="top-n" label="Final shortlist" value={topN} min={limits.top_n_min} max={Math.min(topK, limits.top_n_max)} onChange={setTopN} />
              </div>
              <div className="brief-footer">
                <button className="btn btn-primary btn-block" type="submit" disabled={disabled || isRunning || goalTooShort}>
                  {isRunning ? "Working..." : "Run match"}
                </button>
                {goalTooShort
                  ? <span className="form-help">Add a little more detail so there is something to match against.</span>
                  : needsReindex
                    ? <span className="form-help">The index was built with a different embedding model. Re-embed it with the backend CLI.</span>
                    : disabled && <span className="form-help">Index creators from the backend CLI first.</span>}
              </div>
            </form>
          </aside>

          <div className="run-workspace">
            {job && <RunStatus job={job} isRunning={isRunning} />}
            {(error || run.error) && (
              <ErrorNote
                title={NOTE_TITLES.request}
                action={run.error
                  ? <button className="btn btn-ghost" type="button" onClick={run.retry}>Retry</button>
                  : undefined}
              >
                {error ?? run.error}
              </ErrorNote>
            )}
            {exportError && (
              <ErrorNote title={NOTE_TITLES.export}>
                {exportError}
              </ErrorNote>
            )}
            {/* `hasStarted` records that a submit happened, which survives the
              * hook clearing `job` on failure. The `!job` clause covers a job
              * restored without a local submit. */}
            {!hasStarted && !job && !runDetail && <EmptyWorkspace />}
            {job?.outcome === "no_results" && (
              <EmptyState
                index="NO MATCH"
                title="Try a wider platform."
                body="No creators came back for this filter. Switch to Any or adjust the brief."
              />
            )}
            {awaitingRun && <Skeleton variant="results" label="Loading your shortlist" />}
            {runDetail && (
              <div className="run-results">
                <RunContext
                  run={runDetail}
                  label="Shortlist"
                  exporting={exporting}
                  onExport={() => {
                    if (exporting) return;
                    setExporting(true);
                    setExportError(null);
                    void api.downloadRun(runDetail.run_id)
                      .catch((caught) => setExportError(caught instanceof ApiError ? caught.message : "Could not export the run."))
                      .finally(() => setExporting(false));
                  }}
                />
                <WarningBanner warnings={runDetail.warnings} />
                <SummaryMetrics summary={runDetail.summary} />
                <ResultList run={runDetail} />
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
