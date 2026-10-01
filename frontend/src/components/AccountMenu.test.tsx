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

function openMenu(displayName?: string, signOut = vi.fn()) {
  render(<AccountMenu user={makeUser(displayName)} signOut={signOut} />);
  fireEvent.click(screen.getByRole("button", { name: "Open account menu" }));
  return { signOut, trigger: screen.getByRole("button", { name: "Close account menu" }) };
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

  it("opens a disclosure with identity details", () => {
    const { trigger } = openMenu("Alex Morgan");
    const popover = screen.getByLabelText("Account");

    expect(within(popover).getByText("Alex Morgan")).toBeTruthy();
    expect(within(popover).getByText("user@example.com")).toBeTruthy();
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(trigger.getAttribute("aria-controls")).toBe(popover.id);
  });

  /* role="menu" claimed a widget pattern the contents did not follow -- an
   * identity header, a decorative rule and a live error region are not menu
   * items. These assert the pattern that replaced it, so the invalid roles
   * cannot come back unnoticed. */
  it("does not claim the menu widget pattern", () => {
    openMenu("Alex Morgan");

    expect(screen.queryByRole("menu")).toBeNull();
    expect(screen.queryByRole("menuitem")).toBeNull();
  });

    /* The focus effect also runs on mount. Unguarded, it pulled focus to the
     * account button every time the page loaded -- which fought the skip
     * link, the one control whose whole job is to move focus deliberately. */
    it("does not steal focus on mount", () => {
      const outside = document.createElement("input");
      document.body.appendChild(outside);
      outside.focus();
      expect(document.activeElement).toBe(outside);

      render(<AccountMenu user={makeUser()} signOut={vi.fn()} />);

      expect(document.activeElement).toBe(outside);
      document.body.removeChild(outside);
    });

    it("moves focus into the popover on open and back to the trigger on close", () => {
    const { trigger } = openMenu();

    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Sign out" }));

    fireEvent.click(trigger);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Open account menu" }));
  });

  it("signs out from the popover instead of the trigger", () => {
    const signOut = vi.fn().mockResolvedValue(undefined);
    openMenu("Alex Morgan", signOut);

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(signOut).toHaveBeenCalledOnce();
  });

  it("closes on Escape and outside pointer events", () => {
    render(<AccountMenu user={makeUser()} signOut={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Open account menu" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByLabelText("Account")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Open account menu" }));
    fireEvent.pointerDown(document.body);
    expect(screen.queryByLabelText("Account")).toBeNull();
  });

  it("shows a readable message when sign-out fails", async () => {
    openMenu(undefined, vi.fn().mockRejectedValue(new Error("network")));

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Could not sign out");
  });
});
