import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { api, ApiError } from "../api/client";
import { ResultCard } from "../components/ResultCard";
import { SummaryMetrics } from "../components/RunSummary";
import { WarningBanner } from "../components/WarningBanner";
import { useMatchJob } from "../hooks/useMatchJob";
import type { Brief, MatchJob, Meta, RunDetail } from "../types";

const emptyBrief: Brief = {
  niche: "Sustainable Fashion",
  platform: "Any",
  audience: "Gen Z",
  vibe: "",
};

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
          niche: value.niches.includes(current.niche) ? current.niche : value.niches[0] ?? current.niche,
          platform: value.platforms.includes(current.platform) ? current.platform : value.platforms[0] ?? current.platform,
          audience: value.defaults.audience,
          vibe: value.defaults.vibe,
        }));
        setTopK(value.defaults.top_k);
        setTopN(value.defaults.top_n);
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

  const creatorById = useMemo(
    () => new Map(run?.candidates.map((creator) => [creator.id, creator]) ?? []),
    [run],
  );

  function updateBrief(field: keyof Brief, value: string) {
    setBrief((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRun(null);
    setRunError(null);
    await start(brief, { top_k: topK, top_n: topN });
  }

  const disabled = meta?.index.status === "unavailable";
  const limits = meta?.limits;

  return (
    <section className="page-section">
      <div className="page-intro">
        <div>
          <p className="eyebrow">New match</p>
          <h1>Search</h1>
          <p className="page-description">A focused brief in, a defensible shortlist out.</p>
        </div>
        {meta && (
          <div className="page-intro-meta">
            <span className={`readiness ${disabled ? "readiness-off" : "readiness-on"}`}>
              <span className="readiness-dot" />
              {disabled ? "Index unavailable" : `${meta.index.count.toLocaleString()} creators indexed`}
            </span>
            <span className="page-index">Match desk / 01</span>
          </div>
        )}
      </div>

      {metaError && <div className="system-note system-note-error" role="alert"><span className="system-note-signal" aria-hidden="true" /><strong>Connection issue</strong><span>{metaError}</span></div>}
      {!meta && !metaError && <LoadingForm />}

      {meta && (
        <div className="match-workspace">
          <aside className="brief-rail">
            <div className="rail-heading"><span>Brief</span><span>01</span></div>
            <form className="brief-form" onSubmit={submit}>
              <div className="brief-fields">
                <label className="brief-field" htmlFor="niche">
                  <span>Niche</span>
                  <select id="niche" value={brief.niche} onChange={(event) => updateBrief("niche", event.target.value)}>
                    {meta.niches.map((niche) => <option key={niche}>{niche}</option>)}
                  </select>
                </label>
                <label className="brief-field" htmlFor="platform">
                  <span>Platform</span>
                  <select id="platform" value={brief.platform} onChange={(event) => updateBrief("platform", event.target.value)}>
                    {meta.platforms.map((platform) => <option key={platform}>{platform}</option>)}
                  </select>
                </label>
                <label className="brief-field" htmlFor="audience">
                  <span>Target audience</span>
                  <input id="audience" value={brief.audience} maxLength={limits?.audience_max_length ?? 300} onChange={(event) => updateBrief("audience", event.target.value)} />
                </label>
                <label className="brief-field" htmlFor="vibe">
                  <span>Vibe or tone</span>
                  <textarea id="vibe" value={brief.vibe} maxLength={limits?.vibe_max_length ?? 500} onChange={(event) => updateBrief("vibe", event.target.value)} rows={3} />
                </label>
              </div>
              <div className="rail-divider" />
              <div className="retrieval-controls">
                <div className="control-heading"><span>Search depth</span><span className="control-value">{topK} → {topN}</span></div>
                <RangeControl id="top-k" label="Candidates retrieved" value={topK} min={limits?.top_k_min ?? 1} max={limits?.top_k_max ?? 50} onChange={(next) => { setTopK(next); if (topN > next) setTopN(next); }} />
                <RangeControl id="top-n" label="Final shortlist" value={topN} min={limits?.top_n_min ?? 1} max={topK} onChange={setTopN} />
              </div>
              <div className="brief-footer">
                <button className="primary-button" type="submit" disabled={disabled || isRunning}>
                  {isRunning ? "Working..." : "Run match"}
                </button>
                {disabled && <span className="form-help">Index creators from the backend CLI first.</span>}
              </div>
            </form>
          </aside>

          <div className="run-workspace">
            {job && <RunStatus job={job} isRunning={isRunning} />}
            {(error || runError) && <div className="system-note system-note-error" role="alert"><span className="system-note-signal" aria-hidden="true" /><strong>Request issue</strong><span>{error ?? runError}</span></div>}
            {!job && !run && <EmptyWorkspace />}
            {job?.outcome === "no_results" && <div className="empty-state"><span className="empty-index">NO MATCH</span><h2>Try a wider platform.</h2><p>No creators came back for this filter. Switch to Any or adjust the brief.</p></div>}
            {run && (
              <div className="run-results">
                <div className="run-context">
                  <div>
                    <p className="eyebrow">Shortlist / {formatDate(run.created_at)}</p>
                    <h2>{run.brief.niche} <span>·</span> {run.brief.platform}</h2>
                    <p className="run-context-line">{run.brief.audience || "General audience"} <span>/</span> {run.brief.vibe || "Versatile tone"}</p>
                  </div>
                  <a className="secondary-button" href={api.exportUrl(run.run_id)} download>Export CSV</a>
                </div>
                <WarningBanner warnings={run.warnings} />
                <SummaryMetrics summary={run.summary} />
                <div className="result-list">
                  {run.ranked.map((entry) => {
                    const creator = creatorById.get(entry.id);
                    return creator ? <ResultCard key={entry.id} creator={creator} entry={entry} brief={run.brief} /> : null;
                  })}
                </div>
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
      <h2>Set a brief. We’ll do the sorting.</h2>
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

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
