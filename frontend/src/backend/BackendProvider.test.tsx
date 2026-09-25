import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BackendGate } from "./BackendGate";
import { BackendProvider, useBackend } from "./BackendProvider";

const apiMocks = vi.hoisted(() => ({ probeBackend: vi.fn() }));

vi.mock("../api/client", () => ({ api: { probeBackend: apiMocks.probeBackend } }));

function Harness() {
  const { status, error, wake } = useBackend();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="error">{error ?? ""}</span>
      <button type="button" onClick={() => void wake()}>Wake backend</button>
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
    expect(screen.getByText(/free service that sleeps when idle/)).toBeTruthy();
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
