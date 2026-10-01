import { useState } from "react";
import type { FormEvent } from "react";

import { api, ApiError } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorNote } from "../components/SystemNote";
import { PageIntro } from "../components/PageIntro";
import { ResultList } from "../components/ResultList";
import { RunContext } from "../components/RunContext";
import { SummaryMetrics } from "../components/RunSummary";
import { WarningBanner } from "../components/WarningBanner";
import { useMatchJob } from "../hooks/useMatchJob";
import { useResource } from "../hooks/useResource";
import type { Brief, MatchJob, Meta, RunDetail } from "../types";

const emptyBrief: Brief = {
  goal: "",
  platform: "Any",
  audience: "",
  vibe: "",
};

// Starter prompts, not a closed taxonomy: they exist to show that briefs are
// written in plain language and to save a first-time user from a blank box.
const goalSuggestions = [
  "a thrifted-vintage clothing label for Gen Z who care about slow fashion",
  "high-energy at-home strength training for busy millennials",
  "sourdough baking tips for people starting out at home",
  "budget-friendly travel planning for solo backpackers",
  "skincare routines for sensitive skin, taught inclusively",
  "data-driven investing basics for first-time buyers",
];

const pipelineStages = [
  { key: "embedding", label: "Prepare" },
  { key: "retrieval", label: "Retrieve" },
  { key: "ranking", label: "Rank" },
  { key: "persisting", label: "Save" },
];

/** Used only when the deployed API is an older build that does not publish
 *  limits. Applied once, in `resolveLimits`, rather than as a `??` at each of
 *  the seven call sites that read them -- a scattered fallback is a limit the
 *  UI can silently disagree with the backend about. */
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
  // An export failure used to be written into the run-fetch error slot, so the
  // Retry button next to it refetched the run instead of retrying the download.
  const [exportError, setExportError] = useState<string | null>(null);
  const { job, error, isRunning, start } = useMatchJob();
  /* True once the user has submitted anything, whatever the outcome. The
   * workspace distinguishes "nothing here yet" from "your run failed" -- the
   * hook nulls `job` on failure, so keying off `job` alone made the first-run
   * empty state reappear over the error. */
  const [hasStarted, setHasStarted] = useState(false);

  const meta = useResource<Meta>(
    (signal) => api.getMeta({ signal }),
    [],
    {
      fallbackError: "Could not load API metadata.",
      onLoad: (value) => {
        setBrief((current) => ({
          // Every read is defaulted. The deployed API can be an older build than
          // this frontend -- a missing `defaults.goal` once threw
          // "Cannot read properties of undefined" and blanked the page, so a
          // skewed backend must degrade to an empty form, not a crash.
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
      // The job reports success before the shortlist is readable. Fetching only
      // once a run_id exists keeps the "run exists but the fetch failed" case
      // retryable, which was the whole point: re-reading a record we already
      // have must not mean spending embedding and ranking quota on a new match.
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
  // The job reports success before its shortlist has been fetched. Without this
  // the workspace rendered nothing at all in that window -- the empty state is
  // for "no job yet" and the results are for "run loaded", so neither applied.
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
          title="Connection issue"
          action={<button className="btn btn-ghost" type="button" onClick={meta.retry}>Retry</button>}
        >
          {meta.error}
        </ErrorNote>
      )}
      {!metaValue && !meta.error && <LoadingForm />}

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
                    /* The label element also wraps the live character counter, so
                     * without this the field's accessible name was "What are you
                     * promoting? 12/1000" and changed on every keystroke. Name it
                     * from the caption, describe it with the count. */
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
                  <input id="audience" value={brief.audience} maxLength={limits.audience_max_length} placeholder="e.g. first-time buyers" onChange={(event) => updateBrief("audience", event.target.value)} />
                </label>
                <label className="brief-field" htmlFor="vibe">
                  <span>Vibe or tone <em>optional</em></span>
                  <textarea id="vibe" value={brief.vibe} maxLength={limits.vibe_max_length} placeholder="e.g. warm, practical, no-nonsense" onChange={(event) => updateBrief("vibe", event.target.value)} rows={2} />
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
                title="Request issue"
                action={run.error
                  ? <button className="btn btn-ghost" type="button" onClick={run.retry}>Retry</button>
                  : undefined}
              >
                {error ?? run.error}
              </ErrorNote>
            )}
            {exportError && (
              <ErrorNote title="Export issue">
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
            {awaitingRun && <LoadingResults />}
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

function RangeControl({
  id,
  label,
  value,
  min,
  max,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  const labelId = `${id}-label`;
  return (
    <label className="range-control" htmlFor={id}>
      {/* The caption and the live value share a flex row, so wrapping both in
       * the <label> made the input's accessible name "Candidates retrieved10" and
       * changed it while dragging. Name from the caption, spell the value out in
       * aria-valuetext. */}
      <span><span id={labelId}>{label}</span><strong>{value}</strong></span>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        value={value}
        aria-labelledby={labelId}
        aria-valuetext={`${value} creators`}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

function RunStatus({ job, isRunning }: { job: MatchJob; isRunning: boolean }) {
  const isTerminal = job.status === "succeeded" || job.status === "failed" || job.status === "cancelled";
  const activeIndex = activeStepIndex(job.stage, isTerminal);
  /* The live region covers only the heading line. It used to wrap the whole
   * block including the four pipeline steps, which re-render on every 1.2s poll
   * -- a screen reader was re-announcing the entire pipeline roughly 50 times a
   * run. The steps are static once a stage settles, so only the changing line
   * is live. */
  return (
    <div className={`run-status run-status-${job.status}`}>
      <div className="run-status-heading">
        <div>
          <p className="eyebrow">{job.status === "succeeded" ? "Completed run" : isTerminal ? "Run status" : "Live run"}</p>
          {/* No aria-busy here. On a live region it tells AT to hold back the
            * update, which is the opposite of the intent: the stage label is
            * the one line that should be announced as it changes. */}
          <h2 aria-live="polite">{stageLabel(job.stage)}</h2>
        </div>
        <span className="status-text">{isRunning ? "In progress" : job.status === "succeeded" ? "Complete" : job.status}</span>
      </div>
      <ol className="pipeline">
        {pipelineStages.map((stage, index) => {
          const state = stepState(index, activeIndex, isTerminal, job.status === "succeeded");
          return (
            <li className={`pipeline-step pipeline-step-${state}`} aria-current={state === "active" ? "step" : undefined} key={stage.key}>
              <span className="pipeline-index">{String(index + 1).padStart(2, "0")}</span>
              <span>{stage.label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** Which pipeline step is current, or the last one for a terminal failure.
 *
 *  The API creates every job as `queued` and only advances to `embedding` once a
 *  worker picks it up, so on a free tier that gap is where every user's first
 *  poll lands -- often tens of seconds, while the instance wakes.
 *
 *  This used to be `findIndex(stage => stage.key === job.stage)` inline, which
 *  returns -1 for anything not in the list -- `queued` on every single run, and
 *  any stage a newer backend introduces. The nested ternary that consumed it had
 *  no branch for a negative index, so the whole pipeline rendered `pending`:
 *  four grey bars under a heading that said "Waiting to start". */
function activeStepIndex(stage: string, isTerminal: boolean): number {
  if (isTerminal) return pipelineStages.length - 1;
  const found = pipelineStages.findIndex((step) => step.key === stage);
  if (found >= 0) return found;
  /* A stage this build has never heard of. Returning `last` here would mark
   * every earlier step complete, asserting work we have no evidence finished;
   * 0 asserts only that we do not know yet. Either way the pipeline shows
   * something happening rather than four grey bars. */
  return 0;
}

function stepState(
  index: number,
  activeIndex: number,
  isTerminal: boolean,
  succeeded: boolean,
): "complete" | "active" | "error" | "pending" {
  if (succeeded || index < activeIndex) return "complete";
  if (index > activeIndex) return "pending";
  return isTerminal ? "error" : "active";
}

function EmptyWorkspace() {
  return (
    <EmptyState
      index="READY"
      title="Set a brief."
      body="Retrieval, semantic matching, and ranking stay visible here while the run moves through each stage."
      steps={pipelineStages.map((stage) => stage.label)}
    />
  );
}

function LoadingForm() {
  return <div className="skeleton-workspace"><div className="skeleton-rail" /><div className="skeleton-results"><span /><span /><span /></div></div>;
}

/** Shown between "the job succeeded" and the shortlist arriving. Matches the
 *  existing skeleton treatment rather than inventing a second one. */
function LoadingResults() {
  return (
    <div className="skeleton-results" aria-live="polite" aria-busy="true">
      <span className="visually-hidden">Loading your shortlist</span>
      <span /><span /><span />
    </div>
  );
}

function stageLabel(stage: string): string {
  if (stage === "queued") return "Waiting to start";
  if (stage === "embedding") return "Preparing the query";
  if (stage === "retrieval") return "Retrieving candidates";
  if (stage === "ranking") return "Ranking with Gemini";
  if (stage === "persisting") return "Saving the shortlist";
  if (stage === "complete") return "Match complete";
  if (stage === "failed") return "Match failed";
  if (stage === "cancelled") return "Run cancelled";
  // A stage this build has never heard of used to be echoed raw into the
  // heading; a backend can add one without this frontend knowing.
  return "Working";
}
