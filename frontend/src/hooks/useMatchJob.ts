import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "../api/client";
import type { Brief, MatchJob, MatchParams } from "../types";

const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);

export function useMatchJob() {
  const [job, setJob] = useState<MatchJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sequenceRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const start = useCallback(async (brief: Brief, params: MatchParams) => {
    const sequence = ++sequenceRef.current;
    setError(null);
    setJob(null);
    try {
      let current = await api.createMatchJob(brief, params);
      if (!mountedRef.current || sequence !== sequenceRef.current) return;
      setJob(current);
      while (!terminalStatuses.has(current.status)) {
        await wait(1200);
        current = await api.getMatchJob(current.job_id);
        if (!mountedRef.current || sequence !== sequenceRef.current) return;
        setJob(current);
      }
      if (current.status === "failed") {
        setError(current.error ?? "The match failed.");
      }
    } catch (caught) {
      if (!mountedRef.current || sequence !== sequenceRef.current) return;
      setJob(null);
      setError(caught instanceof ApiError ? caught.message : "The match request failed.");
    }
  }, []);

  return {
    job,
    error,
    isRunning: job !== null && !terminalStatuses.has(job.status),
    start,
  };
}

function wait(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}
