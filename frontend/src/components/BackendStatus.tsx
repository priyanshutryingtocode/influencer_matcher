import { useBackend } from "../backend/BackendProvider";


const hint = import.meta.env.VITE_DEMO_MODE === "true"
  ? "Personal project demo. Free-tier hosting sleeps between visits; completed runs stay saved."
  : "Wakes the local API. The first request can take a moment if the server is starting.";

export function BackendStatus() {
  const { status, checkedAt, wake, recheck } = useBackend();
  const isWaking = status === "waking";
  const isOnline = status === "online";
  const isError = status === "error";
  const label = isWaking
    ? "Waking backend"
    : isOnline
      ? "Backend online"
      : isError
        ? "Backend unavailable"
        : "Backend idle";
  const checked = isOnline && checkedAt ? ` Last checked ${checkedAt.toLocaleTimeString()}.` : "";
  return (
    <button
      type="button"
      className={`backend-status backend-status-${status}`}
      onClick={isOnline ? recheck : () => void wake()}
      disabled={isWaking}
      title={`${hint}${checked}`}
      aria-label={`${label}. ${hint}`}
    >
      <span className="backend-status-dot" aria-hidden="true" />
      <span className="backend-status-label">{label}</span>
      <span className="backend-status-action">{isOnline ? "Recheck" : isError ? "Retry" : "Wake"}</span>
    </button>
  );
}
