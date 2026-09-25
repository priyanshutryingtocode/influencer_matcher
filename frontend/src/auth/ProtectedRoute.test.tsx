import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BackendState } from "../backend/BackendProvider";
import { ProtectedRoute } from "./ProtectedRoute";

const authMocks = vi.hoisted(() => ({ session: null as unknown }));
const backendMocks = vi.hoisted(() => ({ status: "idle" as BackendState }));

vi.mock("./AuthProvider", () => ({
  useAuth: () => ({ session: authMocks.session, loading: false, isConfigured: true }),
}));

vi.mock("../backend/BackendProvider", () => ({
  useBackend: () => ({
    status: backendMocks.status,
    error: null,
    checkedAt: null,
    wake: vi.fn(),
    recheck: vi.fn(),
  }),
}));

function renderGuard() {
  return render(
    <MemoryRouter initialEntries={["/search"]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/search" element={<div>Search page</div>} />
        </Route>
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    authMocks.session = { access_token: "token" };
    backendMocks.status = "idle";
  });

  afterEach(() => {
    cleanup();
  });

  it("redirects anonymous visitors to login without probing the backend", () => {
    authMocks.session = null;
    renderGuard();

    expect(screen.getByText("Login page")).toBeTruthy();
  });

  it("gates the workspace until the backend is online", () => {
    renderGuard();

    expect(screen.getByRole("heading", { name: "Backend resting" })).toBeTruthy();
    expect(screen.queryByText("Search page")).toBeNull();
  });

  it("renders the workspace once the backend is online", () => {
    backendMocks.status = "online";
    renderGuard();

    expect(screen.getByText("Search page")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Backend resting" })).toBeNull();
  });
});
