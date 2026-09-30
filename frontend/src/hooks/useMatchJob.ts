import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "../api/client";
import type { Brief, MatchJob, MatchParams } from "../types";

const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);
const maxPollDurationMs = 15 * 60 * 1000;
/** The API can drop a connection while a free-tier instance sleeps or
 *  restarts, which is not the same as the match failing. A few consecutive
 *  poll errors are tolerated so a transient blip does not throw away a run
 *  the server already finished. */
const maxPollErrors = 3;
const pollErrorBackoffMs = [1_000, 2_000, 4_000];

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
    const startedAt = Date.now();
    try {
      let current = await api.createMatchJob(brief, params);
      if (!mountedRef.current || sequence !== sequenceRef.current) return;
      setJob(current);
      let pollErrors = 0;
      while (!terminalStatuses.has(current.status)) {
        if (Date.now() - startedAt > maxPollDurationMs) {
          throw new Error("The match is taking too long. Please try again shortly.");
        }
        await wait(1200);
        try {
          current = await api.getMatchJob(current.job_id);
          pollErrors = 0;
        } catch (caught) {
          pollErrors += 1;
          if (pollErrors >= maxPollErrors) throw caught;
          await wait(pollErrorBackoffMs[Math.min(pollErrors - 1, pollErrorBackoffMs.length - 1)]);
        }
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
