import { describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { ApiError } from "../api/client";
import { useResource } from "./useResource";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

describe("useResource", () => {
  it("loads and exposes the value", async () => {
    const { result } = renderHook(() => useResource(async () => "value", []));

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe("value");
    expect(result.current.error).toBeNull();
  });

  it("surfaces an ApiError message", async () => {
    const { result } = renderHook(() =>
      useResource(async () => { throw new ApiError("index is empty", 503, null); }, []),
    );

    await waitFor(() => expect(result.current.error).toBe("index is empty"));
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("falls back for a non-ApiError rejection", async () => {
    const { result } = renderHook(() =>
      useResource(async () => { throw new TypeError("bad"); }, [], { fallbackError: "Could not load runs." }),
    );

    await waitFor(() => expect(result.current.error).toBe("Could not load runs."));
  });

  it("clears the previous error when a retry succeeds", async () => {
    let attempt = 0;
    const { result } = renderHook(() =>
      useResource(async () => {
        attempt += 1;
        if (attempt === 1) throw new ApiError("backend asleep", 0, null);
        return "value";
      }, []),
    );

    await waitFor(() => expect(result.current.error).toBe("backend asleep"));
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.data).toBe("value"));
    expect(result.current.error).toBeNull();
  });

  it("re-runs when a dep changes", async () => {
    const load = vi.fn(async (signal: AbortSignal) => {
      void signal;
      return "value";
    });
    const { rerender } = renderHook(
      ({ id }: { id: number }) => useResource(load, [id]),
      { initialProps: { id: 1 } },
    );
    await waitFor(() => expect(load).toHaveBeenCalledTimes(1));

    rerender({ id: 2 });
    await waitFor(() => expect(load).toHaveBeenCalledTimes(2));
  });

  it("does not re-run for a new loader identity on the same deps", async () => {
    const load = vi.fn(async () => "value");
    const { rerender } = renderHook(
      ({ tick }: { tick: number }) => {
        void tick;
        return useResource(async () => load(), []);
      },
      { initialProps: { tick: 0 } },
    );
    await waitFor(() => expect(load).toHaveBeenCalledTimes(1));

    rerender({ tick: 1 });
    rerender({ tick: 2 });
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("skips the request while disabled and runs once enabled", async () => {
    const load = vi.fn(async () => "value");
    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) => useResource(load, [], { enabled }),
      { initialProps: { enabled: false } },
    );
    expect(load).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);

    rerender({ enabled: true });
    await waitFor(() => expect(result.current.data).toBe("value"));
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("aborts the in-flight request on unmount", async () => {
    const gate = deferred<string>();
    let seen: AbortSignal | null = null;
    const { unmount } = renderHook(() =>
      useResource((signal) => { seen = signal; return gate.promise; }, []),
    );
    expect(seen!.aborted).toBe(false);

    unmount();
    expect(seen!.aborted).toBe(true);

    // A late resolution after unmount must not throw or warn.
    await act(async () => { gate.resolve("late"); });
  });

  it("calls onLoad with the loaded value", async () => {
    const onLoad = vi.fn();
    const { result } = renderHook(() => useResource(async () => "value", [], { onLoad }));

    await waitFor(() => expect(result.current.data).toBe("value"));
    expect(onLoad).toHaveBeenCalledWith("value");
  });

  it("setData replaces the value without refetching", async () => {
    const load = vi.fn(async () => "value");
    const { result } = renderHook(() => useResource(load, []));

    await waitFor(() => expect(result.current.data).toBe("value"));
    act(() => result.current.setData("replaced"));
    expect(result.current.data).toBe("replaced");
    expect(load).toHaveBeenCalledTimes(1);
  });
});
