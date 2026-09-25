import { useBackend } from "./BackendProvider";

export function BackendGate() {
  const { status, error, wake } = useBackend();
  const isWaking = status === "waking";
  return (
    <section className="backend-gate" aria-labelledby="backend-gate-title">
      <div className="backend-gate-panel">
        <p className="eyebrow">Free-tier hosting</p>
        <h1 id="backend-gate-title">Backend resting</h1>
        <p className="backend-gate-copy">
          This demo runs on a free service that sleeps when idle. Start it to load matches — the first
          request usually takes about a minute.
        </p>
        <button
          type="button"
          className="primary-button backend-gate-button"
          onClick={() => void wake()}
          disabled={isWaking}
        >
          {isWaking ? "Waking backend..." : "Start backend"}
        </button>
        <p className="backend-gate-status" role="status">
          {isWaking
            ? "Waking up. Keep this tab open."
            : status === "error"
              ? (error ?? "The backend did not start.")
              : "The app continues automatically once it is online."}
        </p>
      </div>
    </section>
  );
}
