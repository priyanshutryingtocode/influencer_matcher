import type { Brief } from "../types";
import { formatDate } from "../format";

interface RunContextProps {
  brief: Brief;
  createdAt: string;
  /** Distinct label per page, e.g. "Shortlist" or "Run detail". */
  label: string;
  /** A double-click used to fire two downloads before the first resolved. */
  exporting?: boolean;
  onExport: () => void;
}

export function RunContext({ brief, createdAt, label, exporting = false, onExport }: RunContextProps) {
  return (
    <div className="run-context">
      <div>
        <p className="eyebrow">{label} / {formatDate(createdAt)}</p>
        <h2 className="run-context-goal">{brief.goal}</h2>
        <p className="run-context-line">
          {brief.platform}
          {brief.audience && <><span>/</span> {brief.audience}</>}
          {brief.vibe && <><span>/</span> {brief.vibe}</>}
        </p>
      </div>
      <button className="btn btn-secondary" type="button" onClick={onExport} disabled={exporting} aria-busy={exporting}>
        {exporting ? "Exporting..." : "Export CSV"}
      </button>
    </div>
  );
}
