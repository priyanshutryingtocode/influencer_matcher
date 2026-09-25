import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Session } from "@supabase/supabase-js";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "./AuthProvider";

const authClientMocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  onAuthStateChange: vi.fn(),
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("../lib/supabase", () => ({
  isAuthConfigured: true,
  supabase: { auth: authClientMocks },
}));

function sessionFor(email: string, displayName?: string): Session {
  return {
    access_token: "access-token",
    token_type: "bearer",
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    refresh_token: "refresh-token",
    user: {
      id: "00000000-0000-4000-8000-000000000001",
      aud: "authenticated",
      role: "authenticated",
      email,
      app_metadata: {},
      user_metadata: displayName ? { display_name: displayName } : {},
      created_at: new Date().toISOString(),
    },
  };
}

function Harness() {
  const { user, signInWithPassword, signUp, signOut } = useAuth();
  return (
    <div>
      <span>{user?.email ?? "anonymous"}</span>
      <button type="button" onClick={() => void signInWithPassword("user@example.com", "password123")}>Sign in</button>
      <button type="button" onClick={() => void signUp({ displayName: "Demo User", email: "new@example.com", password: "password123" })}>Register</button>
      <button type="button" onClick={() => void signOut()}>Sign out</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    authClientMocks.getSession.mockReset().mockResolvedValue({ data: { session: null } });
    authClientMocks.onAuthStateChange.mockReset().mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    });
    authClientMocks.signInWithPassword.mockReset();
    authClientMocks.signUp.mockReset();
    authClientMocks.signOut.mockReset().mockResolvedValue({ error: null });
  });

  afterEach(() => {
    cleanup();
  });

  it("restores an existing session", async () => {
    authClientMocks.getSession.mockResolvedValue({ data: { session: sessionFor("restored@example.com") } });
    render(<AuthProvider><Harness /></AuthProvider>);

    expect(await screen.findByText("restored@example.com")).toBeTruthy();
  });

  it("signs in with password and signs out", async () => {
    authClientMocks.signInWithPassword.mockResolvedValue({ data: { session: sessionFor("user@example.com") }, error: null });
    render(<AuthProvider><Harness /></AuthProvider>);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => {
      expect(authClientMocks.signInWithPassword).toHaveBeenCalledWith({
        email: "user@example.com",
        password: "password123",
      });
      expect(screen.getByText("user@example.com")).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(screen.getByText("anonymous")).toBeTruthy());
  });

  it("registers a password account and stores the display name", async () => {
    authClientMocks.signUp.mockResolvedValue({ data: { session: sessionFor("new@example.com", "Demo User") }, error: null });
    render(<AuthProvider><Harness /></AuthProvider>);

    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    await waitFor(() => {
      expect(authClientMocks.signUp).toHaveBeenCalledWith({
        email: "new@example.com",
        password: "password123",
        options: { data: { display_name: "Demo User" } },
      });
      expect(screen.getByText("new@example.com")).toBeTruthy();
    });
  });
});
