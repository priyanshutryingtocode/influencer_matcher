import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { api, ApiError } from "../api/client";
import { ErrorNote } from "../components/ErrorNote";
import { PageIntro } from "../components/PageIntro";
import { ResultList } from "../components/ResultList";
import { RunContext } from "../components/RunContext";
import { SummaryMetrics } from "../components/RunSummary";
import { WarningBanner } from "../components/WarningBanner";
import { useMatchJob } from "../hooks/useMatchJob";
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

export function SearchPage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [brief, setBrief] = useState<Brief>(emptyBrief);
  const [topK, setTopK] = useState(10);
  const [topN, setTopN] = useState(5);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const { job, error, isRunning, start } = useMatchJob();

  useEffect(() => {
    let active = true;
    void api.getMeta()
      .then((value) => {
        if (!active) return;
        setMeta(value);
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
      })
      .catch((caught) => {
        if (active) setMetaError(caught instanceof ApiError ? caught.message : "Could not load API metadata.");
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (job?.status !== "succeeded") return;
    if (job.outcome === "no_results") {
      setRun(null);
      setRunError(null);
      return;
    }
    if (!job.run_id) return;
    let active = true;
    void api.getRun(job.run_id)
      .then((value) => { if (active) setRun(value); })
      .catch((caught) => { if (active) setRunError(caught instanceof ApiError ? caught.message : "Could not load the completed run."); });
    return () => { active = false; };
  }, [job?.status, job?.run_id, job?.outcome]);

  function updateBrief(field: keyof Brief, value: string) {
    setBrief((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRun(null);
    setRunError(null);
    await start(brief, { top_k: topK, top_n: topN });
  }

  const needsReindex = meta?.index.status === "reindex_required";
  const disabled = meta ? meta.index.status !== "ready" : false;
  const limits = meta?.limits;
  // Read through a local rather than off the state object, so a brief missing
  // a field cannot throw on a later render.
  const goal = brief.goal ?? "";
  const goalLength = goal.trim().length;
  const goalTooShort = goalLength > 0 && goalLength < (limits?.goal_min_length ?? 20);

  return (
    <section className="page-section">
      <PageIntro
        eyebrow="New match"
        title="Search"
        description="Look up creators based on your requirements."
        meta={meta && (
          <span className={`readiness ${disabled ? "readiness-off" : "readiness-on"}`}>
            <span className="readiness-dot" />
            {needsReindex
              ? "Index needs re-embedding"
              : disabled
                ? "Index unavailable"
                : `${meta.index.count.toLocaleString()} creators indexed`}
          </span>
        )}
      />

      {metaError && <ErrorNote title="Connection issue">{metaError}</ErrorNote>}
      {!meta && !metaError && <LoadingForm />}

      {meta && (
        <div className="match-workspace">
          <aside className="brief-rail">
            <div className="rail-heading"><span>Brief</span></div>
            <form className="brief-form" onSubmit={submit}>
              <div className="brief-fields">
                <label className="brief-field" htmlFor="goal">
                  <span>What are you promoting?</span>
                  <textarea
                    id="goal"
                    value={goal}
                    maxLength={limits?.goal_max_length ?? 1000}
                    placeholder="Describe the product or campaign in your own words."
                    onChange={(event) => updateBrief("goal", event.target.value)}
                    rows={5}
                  />
                  <span className="field-count">{goalLength}{limits ? `/${limits.goal_max_length}` : ""}</span>
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
                    {meta.platforms.map((platform) => <option key={platform}>{platform}</option>)}
                  </select>
                </label>
                <label className="brief-field" htmlFor="audience">
                  <span>Target audience <em>optional</em></span>
                  <input id="audience" value={brief.audience} maxLength={limits?.audience_max_length ?? 300} placeholder="e.g. first-time buyers" onChange={(event) => updateBrief("audience", event.target.value)} />
                </label>
                <label className="brief-field" htmlFor="vibe">
                  <span>Vibe or tone <em>optional</em></span>
                  <textarea id="vibe" value={brief.vibe} maxLength={limits?.vibe_max_length ?? 500} placeholder="e.g. warm, practical, no-nonsense" onChange={(event) => updateBrief("vibe", event.target.value)} rows={2} />
                </label>
              </div>
              <div className="rail-divider" />
              <div className="retrieval-controls">
                <div className="control-heading"><span>Search depth</span><span className="control-value">{topK} → {topN}</span></div>
                <RangeControl id="top-k" label="Candidates retrieved" value={topK} min={limits?.top_k_min ?? 1} max={limits?.top_k_max ?? 50} onChange={(next) => { setTopK(next); if (topN > next) setTopN(next); }} />
                <RangeControl id="top-n" label="Final shortlist" value={topN} min={limits?.top_n_min ?? 1} max={topK} onChange={setTopN} />
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
            {(error || runError) && <ErrorNote title="Request issue">{error ?? runError}</ErrorNote>}
            {!job && !run && <EmptyWorkspace />}
            {job?.outcome === "no_results" && <div className="empty-state"><span className="empty-index">NO MATCH</span><h2>Try a wider platform.</h2><p>No creators came back for this filter. Switch to Any or adjust the brief.</p></div>}
            {run && (
              <div className="run-results">
                <RunContext
                  brief={run.brief}
                  createdAt={run.created_at}
                  label="Shortlist"
                  onExport={() => void api.downloadRun(run.run_id).catch((caught) => setRunError(caught instanceof ApiError ? caught.message : "Could not export the run."))}
                />
                <WarningBanner warnings={run.warnings} />
                <SummaryMetrics summary={run.summary} />
                <ResultList run={run} />
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function RangeControl({ id, label, value, min, max, onChange }: { id: string; label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <label className="range-control" htmlFor={id}>
      <span>{label}<strong>{value}</strong></span>
      <input id={id} type="range" min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function RunStatus({ job, isRunning }: { job: MatchJob; isRunning: boolean }) {
  const activeIndex = job.stage === "failed" || job.stage === "cancelled"
    ? pipelineStages.length - 1
    : pipelineStages.findIndex((stage) => stage.key === job.stage);
  const isTerminal = job.status === "succeeded" || job.status === "failed" || job.status === "cancelled";
  return (
    <div className={`run-status run-status-${job.status}`} aria-live="polite">
      <div className="run-status-heading">
        <div>
          <p className="eyebrow">{job.status === "succeeded" ? "Completed run" : isTerminal ? "Run status" : "Live run"}</p>
          <h2>{stageLabel(job.stage)}</h2>
        </div>
        <span className="status-text">{isRunning ? "In progress" : job.status === "succeeded" ? "Complete" : job.status}</span>
      </div>
      <ol className="pipeline">
        {pipelineStages.map((stage, index) => {
          const state = job.status === "succeeded" || index < activeIndex
            ? "complete"
            : index === activeIndex && !isTerminal
              ? "active"
              : index === activeIndex && isTerminal
                ? "error"
                : "pending";
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

function EmptyWorkspace() {
  return (
    <div className="empty-state">
      <span className="empty-index">READY</span>
      <h2>Set a brief.</h2>
      <p>Retrieval, semantic matching, and ranking stay visible here while the run moves through each stage.</p>
      <div className="empty-steps"><span>Brief</span><span>Retrieve</span><span>Rank</span><span>Save</span></div>
    </div>
  );
}

function LoadingForm() {
  return <div className="skeleton-workspace"><div className="skeleton-rail" /><div className="skeleton-results"><span /><span /><span /></div></div>;
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
  return stage;
}
