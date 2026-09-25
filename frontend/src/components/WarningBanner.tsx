import type { Warning } from "../types";

const severityLabel = {
  error: "Error",
  warning: "Warning",
  info: "Notice",
};

export function WarningBanner({ warnings }: { warnings: Warning[] }) {
  if (!warnings.length) return null;
  const hasError = warnings.some((warning) => warning.severity === "error");
  return (
    <section className={`system-note ${hasError ? "system-note-error" : "system-note-info"}`} role={hasError ? "alert" : "status"}>
      <div className="system-note-heading">
        <span className="system-note-signal" aria-hidden="true" />
        <strong>{hasError ? "Review required" : "Run notes"}</strong>
        <span className="system-note-rule" />
        <span className="system-note-count">{warnings.length} {warnings.length === 1 ? "note" : "notes"}</span>
      </div>
      <ul className="system-note-list">
        {warnings.map((warning) => (
          <li key={`${warning.code}-${warning.message}`}>
            <span className="note-label">{severityLabel[warning.severity]}</span>
            <span>{warning.message}</span>
            {Object.keys(warning.details).length > 0 && (
              <details className="note-details">
                <summary>Details</summary>
                <span>{formatDetails(warning.details)}</span>
              </details>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function formatDetails(details: Record<string, unknown>) {
  return Object.entries(details)
    .map(([key, value]) => `${key.replace(/_/g, " ")}: ${String(value)}`)
    .join(" · ");
}
