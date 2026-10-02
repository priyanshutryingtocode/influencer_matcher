import type { MatchJob } from "../types";

/** The four stages a run moves through, in order. */
export const pipelineStages = [
  { key: "embedding", label: "Prepare" },
  { key: "retrieval", label: "Retrieve" },
  { key: "ranking", label: "Rank" },
  { key: "persisting", label: "Save" },
];

export function RunStatus({ job, isRunning }: { job: MatchJob; isRunning: boolean }) {
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
 *  Must never return -1: the step-ternary has no branch for it, so every stage
 *  renders `pending`. A plain findIndex returned -1 for `queued`, the state
 *  every job is created in. */
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

/** Shown between "the job succeeded" and the shortlist arriving. Matches the
 *  existing skeleton treatment rather than inventing a second one. */
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