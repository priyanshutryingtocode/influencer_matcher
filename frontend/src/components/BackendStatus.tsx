import { useBackend } from "../backend/BackendProvider";

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
  return (
    <button
      type="button"
      className={`backend-status backend-status-${status}`}
      onClick={isOnline ? recheck : () => void wake()}
      disabled={isWaking}
      title={isOnline && checkedAt ? `Checked at ${checkedAt.toLocaleTimeString()}` : "Wake the free backend"}
    >
      <span className="backend-status-dot" aria-hidden="true" />
      <span className="backend-status-label">{label}</span>
      <span className="backend-status-action">{isOnline ? "Recheck" : isError ? "Retry" : "Wake"}</span>
    </button>
  );
}
