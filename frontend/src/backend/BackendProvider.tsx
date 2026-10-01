import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { api } from "../api/client";

export type BackendState = "idle" | "waking" | "online" | "error";

interface BackendContextValue {
  status: BackendState;
  error: string | null;
  checkedAt: Date | null;
  /** True once a probe has succeeded this session. The gate only ever shows
   *  before the first success, so a later sleeping instance never unmounts a
   *  page the user is working in. */
  entered: boolean;
  wake: () => Promise<boolean>;
  recheck: () => void;
}

const BackendContext = createContext<BackendContextValue | null>(null);

export function BackendProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<BackendState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const [entered, setEntered] = useState(false);
  const requestRef = useRef(0);

  // There used to be a 15-minute timer that flipped `online` back to `idle`,
  // which made the gate replace the whole routed app with the "backend
  // resting" panel -- losing a half-typed brief, an in-flight poll, and the
  // selected run. It was guessing at when the host sleeps, and it collided
  // exactly with useMatchJob's 15-minute poll ceiling. Nothing schedules that
  // any more: once we have been online, a sleeping instance shows up as a
  // request timeout that names the cause and can be retried from the pill.

  const wake = useCallback(async () => {
    const requestId = requestRef.current + 1;
    requestRef.current = requestId;
    setStatus("waking");
    setError(null);
    try {
      await api.probeBackend();
      if (requestRef.current !== requestId) return false;
      setStatus("online");
      setEntered(true);
      setCheckedAt(new Date());
      return true;
    } catch (cause) {
      if (requestRef.current !== requestId) return false;
      setStatus("error");
      setError(cause instanceof Error ? cause.message : "The backend could not be started.");
      return false;
    }
  }, []);

  const recheck = useCallback(() => {
    // Deliberately does not return to a blocking state. The user asked to
    // re-verify, not to be ejected from the page they are on.
    void wake();
  }, [wake]);

  const value = useMemo(
    () => ({ status, error, checkedAt, entered, wake, recheck }),
    [status, error, checkedAt, entered, wake, recheck],
  );

  return <BackendContext.Provider value={value}>{children}</BackendContext.Provider>;
}

export function useBackend(): BackendContextValue {
  const context = useContext(BackendContext);
  if (!context) throw new Error("useBackend must be used inside BackendProvider.");
  return context;
}
