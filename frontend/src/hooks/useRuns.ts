import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import type { RunListItem } from "../types";

export function useRuns() {
  const [items, setItems] = useState<RunListItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (cursor?: string, append = false) => {
    if (append) setIsLoadingMore(true);
    else setIsLoading(true);
    setError(null);
    try {
      const response = await api.listRuns(cursor);
      setItems((current) => (append ? [...current, ...response.items] : response.items));
      setNextCursor(response.next_cursor);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load run history.");
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const remove = useCallback(async (runId: string) => {
    try {
      await api.deleteRun(runId);
      setItems((current) => current.filter((item) => item.run_id !== runId));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not delete the run.");
      throw caught;
    }
  }, []);

  return {
    items,
    isLoading,
    isLoadingMore,
    hasMore: nextCursor !== null,
    error,
    refresh: () => load(),
    loadMore: () => (nextCursor ? load(nextCursor, true) : Promise.resolve()),
    remove,
  };
}
