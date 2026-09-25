import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { api } from "../api/client";

export type BackendState = "idle" | "waking" | "online" | "error";

interface BackendContextValue {
  status: BackendState;
  error: string | null;
  checkedAt: Date | null;
  wake: () => Promise<boolean>;
  recheck: () => void;
}

const BackendContext = createContext<BackendContextValue | null>(null);
const onlineWindowMs = 15 * 60 * 1000;

export function BackendProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<BackendState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const requestRef = useRef(0);

  useEffect(() => {
    if (status !== "online") return;
    const timer = setTimeout(() => setStatus("idle"), onlineWindowMs);
    return () => clearTimeout(timer);
  }, [status]);

  const wake = useCallback(async () => {
    const requestId = requestRef.current + 1;
    requestRef.current = requestId;
    setStatus("waking");
    setError(null);
    try {
      await api.probeBackend();
      if (requestRef.current !== requestId) return false;
      setStatus("online");
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
    if (status === "online") setStatus("idle");
  }, [status]);

  const value = useMemo(
    () => ({ status, error, checkedAt, wake, recheck }),
    [status, error, checkedAt, wake, recheck],
  );

  return <BackendContext.Provider value={value}>{children}</BackendContext.Provider>;
}

export function useBackend(): BackendContextValue {
  const context = useContext(BackendContext);
  if (!context) throw new Error("useBackend must be used inside BackendProvider.");
  return context;
}
