import type { Brief, CreatorSnapshot, RankedCreator } from "../types";
import { formatFollowers } from "./RunSummary";

interface ResultCardProps {
  creator: CreatorSnapshot;
  entry: RankedCreator;
  brief: Brief;
  highlight?: boolean;
}

const fitLabels = {
  strong: "Strong",
  partial: "Partial",
  weak: "Weak",
  unknown: "Unknown",
};

const sourceLabels = {
  llm: "Gemini ranked",
  filled: "Filled from retrieval",
  fallback: "Retrieval fallback",
};

export function ResultCard({ creator, entry, brief, highlight = false }: ResultCardProps) {
  return (
    <article className={`result-row ${highlight ? "result-row-highlight" : ""}`} aria-label={`Match ${entry.rank} for ${brief.niche}`}>
      <div className="result-rank"><span>#</span>{String(entry.rank).padStart(2, "0")}</div>
      <div className="result-identity">
        <div className="result-identity-heading">
          <h3>{creator.handle}</h3>
          {creator.name && <span className="result-display-name">{creator.name}</span>}
          {creator.verified && <span className="verified-mark">Verified</span>}
        </div>
        <p className="result-subline">{[creator.niche, creator.platform, creator.city].filter(Boolean).join(" · ")}</p>
        <p className="result-meta">{creator.content_style || "Content style unavailable"} · {creator.language || "Language unavailable"} · {creator.audience_age || "Audience unknown"}</p>
        {creator.tags.length > 0 && <p className="result-tags">{creator.tags.slice(0, 4).join("  ·  ")}</p>}
      </div>
      <div className="result-fit">
        <span className={`fit-mark fit-mark-${entry.fit}`} aria-hidden="true" />
        <span className="fit-label">{fitLabels[entry.fit]}</span>
        <span className="source-label">{sourceLabels[entry.source]}</span>
      </div>
      <div className="result-metrics">
        <Metric label="Reach" value={formatFollowers(creator.followers)} />
        <Metric label="Engagement" value={`${creator.engagement_pct.toFixed(1)}%`} />
        <Metric label="Match" value={creator.similarity === null ? "—" : `${(creator.similarity * 100).toFixed(1)}%`} />
      </div>
      <div className="result-rationale">
        {entry.rationale && <p>{entry.rationale}</p>}
        <details>
          <summary>Evidence</summary>
          <ul>
            {entry.evidence.map((evidence) => <li key={evidence}>{evidence}</li>)}
          </ul>
          {creator.brand_collaborations.length > 0 && <p className="result-collaborations">Past work: {creator.brand_collaborations.join(", ")}</p>}
        </details>
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="result-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
