import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BackendGate } from "./BackendGate";
import { BackendProvider, useBackend } from "./BackendProvider";

const apiMocks = vi.hoisted(() => ({ probeBackend: vi.fn() }));

vi.mock("../api/client", () => ({ api: { probeBackend: apiMocks.probeBackend } }));

function Harness() {
  const { status, error, entered, wake, recheck } = useBackend();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="error">{error ?? ""}</span>
      <span data-testid="entered">{String(entered)}</span>
      <button type="button" onClick={() => void wake()}>Wake backend</button>
      <button type="button" onClick={() => recheck()}>Recheck backend</button>
    </div>
  );
}

describe("BackendProvider", () => {
  beforeEach(() => {
    apiMocks.probeBackend.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("stays idle until the visitor asks for a wake", () => {
    render(
      <BackendProvider>
        <Harness />
      </BackendProvider>,
    );

    expect(screen.getByTestId("status").textContent).toBe("idle");
    expect(apiMocks.probeBackend).not.toHaveBeenCalled();
  });

  it("marks the backend online after a successful probe", async () => {
    apiMocks.probeBackend.mockResolvedValue(undefined);
    render(
      <BackendProvider>
        <Harness />
      </BackendProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Wake backend" }));

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("online");
    });
    expect(apiMocks.probeBackend).toHaveBeenCalledOnce();
  });

  it("keeps a failure visible for retry", async () => {
    apiMocks.probeBackend.mockRejectedValue(new Error("The backend could not be reached."));
    render(
      <BackendProvider>
        <Harness />
      </BackendProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Wake backend" }));

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("error");
    });
    expect(screen.getByTestId("error").textContent).toBe("The backend could not be reached.");
  });

  it("stays entered once online, so a later recheck never re-gates", async () => {
    apiMocks.probeBackend.mockResolvedValue(undefined);
    render(
      <BackendProvider>
        <Harness />
      </BackendProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Wake backend" }));
    await waitFor(() => expect(screen.getByTestId("entered").textContent).toBe("true"));

    fireEvent.click(screen.getByRole("button", { name: "Recheck backend" }));

    await waitFor(() => expect(apiMocks.probeBackend).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId("entered").textContent).toBe("true");
  });

  it("does not expire the online state on a timer", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      apiMocks.probeBackend.mockResolvedValue(undefined);
      render(
        <BackendProvider>
          <Harness />
        </BackendProvider>,
      );

      fireEvent.click(screen.getByRole("button", { name: "Wake backend" }));
      await vi.waitFor(() => expect(screen.getByTestId("status").textContent).toBe("online"));

      /* The old decay was 15 minutes, identical to useMatchJob's poll ceiling,
       * so a slow run and the timer collided exactly. */
      await vi.advanceTimersByTimeAsync(16 * 60 * 1000);

      expect(screen.getByTestId("status").textContent).toBe("online");
      expect(screen.getByTestId("entered").textContent).toBe("true");
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("BackendGate", () => {
  beforeEach(() => {
    apiMocks.probeBackend.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("explains the free-tier sleep and starts the backend on request", async () => {
    let releaseProbe = () => {};
    apiMocks.probeBackend.mockImplementation(
      () => new Promise<void>((resolve) => {
        releaseProbe = resolve;
      }),
    );
    render(
      <BackendProvider>
        <BackendGate />
      </BackendProvider>,
    );

    expect(screen.getByRole("heading", { name: "Backend resting" })).toBeTruthy();
    // Matched loosely on the one phrase that carries the meaning. This was
    // pinned to "free service that sleeps when idle" and broke the moment the
    // copy was rewritten to name Render instead, which says nothing about
    // whether the gate is explaining itself correctly.
    expect(screen.getByText(/sleeps when idle/)).toBeTruthy();
    expect(apiMocks.probeBackend).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Start backend" }));

    await waitFor(() => {
      expect(apiMocks.probeBackend).toHaveBeenCalledOnce();
    });
    expect(screen.getByRole("button", { name: "Waking backend..." })).toBeTruthy();
    expect(screen.getByText("Waking up. Keep this tab open.")).toBeTruthy();

    releaseProbe();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Start backend" })).toBeTruthy();
    });
  });
});
