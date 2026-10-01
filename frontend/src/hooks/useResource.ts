import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";

export interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  /** Re-run the loader. Bumps the attempt counter, so this is a stable identity. */
  retry: () => void;
  /** Replace the value without refetching, e.g. to clear before a new submit. */
  setData: (value: T | null) => void;
  /** Clear a stale error, e.g. the moment the user starts a different action. */
  setError: (message: string | null) => void;
}

export interface ResourceOptions<T> {
  /** Skip the request entirely. Defaults to true. */
  enabled?: boolean;
  /** Shown when the rejection is not an ApiError, so the user is not shown "unknown". */
  fallbackError?: string;
  /** Runs on a successful load, for writing into other state. */
  onLoad?: (value: T) => void;
}

/**
 * The fetch-once-retry-on-demand shape that was hand-written in every page:
 * a data slot, an error slot, a loading flag, an attempt counter, an `active`
 * guard for unmount, an AbortController, and a retry button wired to the
 * counter. Six pages each had their own copy, and they had drifted -- some
 * cleared the error on retry, some did not, and only some aborted in flight.
 *
 * The loader is held in a ref so a new inline closure each render does not
 * retrigger the effect; `deps` is the explicit list of things that should.
 */
export function useResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
  options: ResourceOptions<T> = {},
): Resource<T> {
  const { enabled = true, fallbackError = "Could not load data.", onLoad } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const loadRef = useRef(load);
  const onLoadRef = useRef(onLoad);
  const fallbackRef = useRef(fallbackError);
  useEffect(() => {
    loadRef.current = load;
    onLoadRef.current = onLoad;
    fallbackRef.current = fallbackError;
  });

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setError(null);
    setLoading(true);
    void loadRef.current(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setData(value);
        onLoadRef.current?.(value);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof ApiError ? caught.message : fallbackRef.current);
      })
      .finally(() => {
        // Skipped once aborted: the next attempt owns the flag by then, and on
        // unmount there is nothing left to update.
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt, enabled]);

  const retry = useCallback(() => setAttempt((count) => count + 1), []);
  return { data, error, loading, retry, setData, setError };
}
