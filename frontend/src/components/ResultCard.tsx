import type { Brief, CreatorSnapshot, RankedCreator } from "../types";
import { SIMILARITY_EXPLANATION, formatFollowers } from "./RunSummary";

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

/** Only rows that did not come back through the normal ranked path need to say
 *  so; labelling every row just adds noise. `llm_unverified` is called out
 *  because the model gave a reason and the server could not confirm any part
 *  of it, which a reader needs to know. */
const fallbackSourceLabels = {
  filled: "Filled from retrieval",
  fallback: "Retrieval fallback",
  llm_unverified: "Reason not confirmed",
};

/** Field keys the API can ground a claim in, shown as readable labels. */
const groundingLabels: Record<string, string> = {
  tags: "Topics",
  bio: "Bio",
  content_style: "Content style",
  audience_age: "Audience age",
  audience_gender: "Audience gender",
  audience_country: "Audience country",
  brand_collaborations: "Brand partners",
  platform: "Platform",
  followers: "Followers",
  engagement_rate: "Engagement",
};

export function ResultCard({ creator, entry, brief, highlight = false }: ResultCardProps) {
  const subtitle = [creator.city, creator.content_style].filter(Boolean).join(" · ");
  const similarity = creator.similarity === null ? "—" : `${(creator.similarity * 100).toFixed(1)}%`;

  return (
    <article className={`result-row ${highlight ? "result-row-highlight" : ""}`} aria-label={`Match ${entry.rank} for ${brief.goal}`}>
      <div className="result-rank"><span>#</span>{String(entry.rank).padStart(2, "0")}</div>
      <div className="result-identity">
        <div className="result-identity-heading">
          <h3>{creator.handle}</h3>
          {creator.name && <span className="result-display-name">{creator.name}</span>}
          {creator.verified && <span className="verified-mark">Verified</span>}
        </div>
        {subtitle && <p className="result-subline">{subtitle}</p>}
        {creator.tags.length > 0 && <p className="result-tags">{creator.tags.slice(0, 3).join("  ·  ")}</p>}
      </div>
      <div className="result-fit">
        <span className="result-fit-line">
          <span className={`fit-mark fit-mark-${entry.fit}`} aria-hidden="true" />
          <span className="fit-label">{fitLabels[entry.fit]}</span>
          <span className="fit-match" title={SIMILARITY_EXPLANATION}>{similarity}</span>
        </span>
        {entry.source !== "llm" && <span className="source-label">{fallbackSourceLabels[entry.source]}</span>}
      </div>
      <div className="result-metrics">
        <Metric label="Reach" value={formatFollowers(creator.followers)} />
        <Metric label="Engagement" value={`${creator.engagement_pct.toFixed(1)}%`} />
      </div>
      <div className="result-rationale">
        {entry.rationale && <p>{entry.rationale}</p>}
        {entry.grounding.length > 0 && (
          <ul className="result-grounding">
            {entry.grounding.map((claim) => (
              <li key={`${claim.field}:${claim.quote}`}>
                <span className="grounding-field">{groundingLabels[claim.field] ?? claim.field}</span>
                <span className="grounding-quote">{claim.quote}</span>
              </li>
            ))}
          </ul>
        )}
        <details>
          <summary>Profile details</summary>
          <ul>
            {entry.evidence.map((evidence) => <li key={evidence}>{evidence}</li>)}
          </ul>
          {detailPairs(creator).length > 0 && (
            <p className="result-collaborations">{detailPairs(creator).join(" · ")}</p>
          )}
        </details>
      </div>
    </article>
  );
}

/** Missing attributes are omitted rather than rendered as "unavailable", which
 *  reads as broken data instead of absent data. */
function detailPairs(creator: CreatorSnapshot): string[] {
  const pairs: string[] = [];
  if (creator.content_style) pairs.push(`Style: ${creator.content_style}`);
  if (creator.language) pairs.push(`Language: ${creator.language}`);
  if (creator.audience_age) pairs.push(`Audience: ${creator.audience_age}`);
  if (creator.audience_gender) pairs.push(`Gender: ${creator.audience_gender}`);
  // Reach as a share of followers is what separates real reach from a large
  // follower count, which is the number a brand is most often misled by.
  if (creator.reach_ratio > 0) {
    pairs.push(`Reach vs followers: ${(creator.reach_ratio * 100).toFixed(0)}%`);
  }
  if (creator.sponsored_ratio > 0) {
    pairs.push(`Sponsored: ${(creator.sponsored_ratio * 100).toFixed(0)}%`);
  }
  if (creator.growth_trend) pairs.push(`Growth: ${creator.growth_trend}`);
  if (creator.audience_top_countries.length > 1) {
    pairs.push(`Top markets: ${creator.audience_top_countries.join(", ")}`);
  }
  if (creator.brand_collaborations.length > 0) {
    pairs.push(`Past work: ${creator.brand_collaborations.join(", ")}`);
  }
  return pairs;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="result-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
