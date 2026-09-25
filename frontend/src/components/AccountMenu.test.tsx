import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { User } from "@supabase/supabase-js";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountMenu, getInitials } from "./AccountMenu";

function makeUser(displayName?: string, email = "user@example.com"): User {
  return {
    id: "00000000-0000-4000-8000-000000000001",
    aud: "authenticated",
    role: "authenticated",
    email,
    app_metadata: {},
    user_metadata: displayName ? { display_name: displayName } : {},
    created_at: new Date().toISOString(),
  };
}

describe("AccountMenu", () => {
  afterEach(() => {
    cleanup();
  });

  it("derives readable initials", () => {
    expect(getInitials("Alex Morgan", "alex@example.com")).toBe("AM");
    expect(getInitials("abc", "abc@example.com")).toBe("AB");
    expect(getInitials("", "alex@example.com")).toBe("AL");
  });

  it("opens an account menu with identity details", () => {
    render(<AccountMenu user={makeUser("Alex Morgan")} signOut={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Open account menu" }));
    const menu = screen.getByRole("menu", { name: "Account" });
    expect(within(menu).getByText("Alex Morgan")).toBeTruthy();
    expect(within(menu).getByText("user@example.com")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Close account menu" }).getAttribute("aria-expanded")).toBe("true");
  });

  it("signs out from the menu instead of the trigger", () => {
    const signOut = vi.fn().mockResolvedValue(undefined);
    render(<AccountMenu user={makeUser("Alex Morgan")} signOut={signOut} />);

    fireEvent.click(screen.getByRole("button", { name: "Open account menu" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));

    expect(signOut).toHaveBeenCalledOnce();
  });

  it("closes on Escape and outside pointer events", () => {
    render(<AccountMenu user={makeUser()} signOut={vi.fn()} />);
    const trigger = screen.getByRole("button", { name: "Open account menu" });

    fireEvent.click(trigger);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Open account menu" }));
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("shows a readable message when sign-out fails", async () => {
    const signOut = vi.fn().mockRejectedValue(new Error("network"));
    render(<AccountMenu user={makeUser()} signOut={signOut} />);

    fireEvent.click(screen.getByRole("button", { name: "Open account menu" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Could not sign out");
  });
});
