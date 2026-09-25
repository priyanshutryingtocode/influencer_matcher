import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BackendState } from "../backend/BackendProvider";
import { BackendStatus } from "./BackendStatus";

const backendMocks = vi.hoisted(() => ({
  status: "idle" as BackendState,
  wake: vi.fn(),
  recheck: vi.fn(),
}));

vi.mock("../backend/BackendProvider", () => ({
  useBackend: () => ({
    status: backendMocks.status,
    error: null,
    checkedAt: null,
    wake: backendMocks.wake,
    recheck: backendMocks.recheck,
  }),
}));

describe("BackendStatus", () => {
  beforeEach(() => {
    backendMocks.status = "idle";
    backendMocks.wake.mockReset();
    backendMocks.recheck.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("offers a wake action while the backend is idle", () => {
    render(<BackendStatus />);

    const trigger = screen.getByRole("button", { name: /Backend idle/ });
    fireEvent.click(trigger);

    expect(backendMocks.wake).toHaveBeenCalledOnce();
  });

  it("disables the control while waking", () => {
    backendMocks.status = "waking";
    render(<BackendStatus />);

    const trigger = screen.getByRole("button", { name: /Waking backend/ });
    expect(trigger.hasAttribute("disabled")).toBe(true);
  });

  it("switches to a recheck action when online", () => {
    backendMocks.status = "online";
    render(<BackendStatus />);

    fireEvent.click(screen.getByRole("button", { name: /Backend online/ }));

    expect(backendMocks.recheck).toHaveBeenCalledOnce();
  });

  it("offers retry after a failure", () => {
    backendMocks.status = "error";
    render(<BackendStatus />);

    fireEvent.click(screen.getByRole("button", { name: /Backend unavailable/ }));

    expect(backendMocks.wake).toHaveBeenCalledOnce();
  });
});
