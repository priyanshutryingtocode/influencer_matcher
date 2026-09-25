import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";

const authMocks = vi.hoisted(() => ({
  session: null as unknown,
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
}));

vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => ({
    session: authMocks.session,
    isConfigured: true,
    signInWithPassword: authMocks.signInWithPassword,
    signUp: authMocks.signUp,
  }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    authMocks.session = null;
    authMocks.signInWithPassword.mockReset();
    authMocks.signUp.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("redirects an authenticated visitor to search", async () => {
    authMocks.session = {};
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/search" element={<div>Search page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Search page")).toBeTruthy();
  });

  it("signs in with email and password", async () => {
    authMocks.signInWithPassword.mockResolvedValue(undefined);
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in to account" }));

    await waitFor(() => {
      expect(authMocks.signInWithPassword).toHaveBeenCalledWith("user@example.com", "password123");
    });
  });

  it("creates an account with a display name", async () => {
    authMocks.signUp.mockResolvedValue(true);
    render(<LoginPage />);

    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Demo User" } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: " user@example.com " } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(authMocks.signUp).toHaveBeenCalledWith({
        displayName: "Demo User",
        email: "user@example.com",
        password: "password123",
      });
    });
    expect(await screen.findByText("Account created. You are signed in.")).toBeTruthy();
  });

  it("rejects mismatched password confirmation", () => {
    render(<LoginPage />);

    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Demo User" } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "different123" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(screen.getByText("Passwords do not match.")).toBeTruthy();
    expect(authMocks.signUp).not.toHaveBeenCalled();
  });

  it("renders a readable fallback for non-error rejections", async () => {
    authMocks.signInWithPassword.mockRejectedValue(0);
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in to account" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Could not sign in.");
    expect(screen.queryByText("0")).toBeNull();
  });
});
