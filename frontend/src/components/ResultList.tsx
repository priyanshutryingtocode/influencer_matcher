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
  const cards = run.ranked.map((entry) => {
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
  });

  /* A run whose ranked list is empty, or whose every snapshot failed the join,
   * used to render a bordered box with nothing in it -- which reads as a broken
   * page rather than an empty result. */
  if (cards.every((card) => card === null)) {
    return (
      <div className="result-list">
        <div className="empty-ledger">
          <p>{run.ranked.length ? "This shortlist's creator details are no longer available." : "No creators in this shortlist."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`result-list ${className ?? ""}`}>
      {cards}
    </div>
  );
}
