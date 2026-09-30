import type { RunDetail } from "../types";
import { ResultCard } from "./ResultCard";

interface ResultListProps {
  run: Pick<RunDetail, "brief" | "candidates" | "ranked">;
  /** Creator keys to tint; Compare uses this to mark the shared creators. */
  highlightKeys?: Set<string>;
  className?: string;
}

/** Renders a ranked shortlist, skipping any entry whose creator snapshot is
 *  missing from the run. Shared so the pages cannot drift apart. */
export function ResultList({ run, highlightKeys, className }: ResultListProps) {
  const creatorById = new Map(run.candidates.map((creator) => [creator.id, creator]));
  return (
    <div className={`result-list ${className ?? ""}`}>
      {run.ranked.map((entry) => {
        const creator = creatorById.get(entry.id);
        if (!creator) return null;
        return (
          <ResultCard
            key={entry.id}
            creator={creator}
            entry={entry}
            brief={run.brief}
            highlight={highlightKeys?.has(creator.creator_key) ?? false}
          />
        );
      })}
    </div>
  );
}
