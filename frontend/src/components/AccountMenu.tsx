import { useEffect, useRef, useState } from "react";
import type { User } from "@supabase/supabase-js";

interface AccountMenuProps {
  user: User;
  signOut: () => Promise<void>;
}

interface AccountIdentity {
  displayName: string;
  email: string;
  initials: string;
}

export function AccountMenu({ user, signOut }: AccountMenuProps) {
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const identity = getAccountIdentity(user);

  useEffect(() => {
    if (!open) return;

    function closeOnOutsidePointer(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  async function handleSignOut() {
    setSigningOut(true);
    setError(null);
    try {
      await signOut();
    } catch {
      setError("Could not sign out. Please try again.");
      setSigningOut(false);
    }
  }

  return (
    <div className="account-menu-root" ref={rootRef}>
      <button
        className={open ? "account-trigger open" : "account-trigger"}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={open ? "Close account menu" : "Open account menu"}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="account-avatar" aria-hidden="true">{identity.initials}</span>
        <span className="account-trigger-name">{identity.displayName}</span>
      </button>
      {open && (
        <div className="account-menu" role="menu" aria-label="Account">
          <div className="account-menu-header">
            <span className="account-avatar account-avatar-large" aria-hidden="true">{identity.initials}</span>
            <div className="account-menu-identity">
              <strong>{identity.displayName}</strong>
              <span>{identity.email}</span>
            </div>
          </div>
          <div className="account-menu-rule" />
          <button className="account-menu-action" type="button" role="menuitem" disabled={signingOut} onClick={() => void handleSignOut()}>
            {signingOut ? "Signing out..." : "Sign out"}
          </button>
          {error && <p className="account-menu-error" role="alert">{error}</p>}
        </div>
      )}
    </div>
  );
}

export function getAccountIdentity(user: User): AccountIdentity {
  const metadataName = user.user_metadata?.display_name;
  const email = typeof user.email === "string" && user.email.trim() ? user.email.trim() : "Signed in";
  const displayName = typeof metadataName === "string" && metadataName.trim()
    ? metadataName.trim()
    : email.split("@")[0] || "Account";
  return { displayName, email, initials: getInitials(displayName, email) };
}

export function getInitials(displayName: string, email: string): string {
  const words = displayName.trim().split(/\s+/).filter(Boolean);
  if (words.length > 1) {
    return `${words[0][0]}${words[words.length - 1][0]}`.toUpperCase();
  }
  const source = words[0] ?? email.split("@")[0] ?? "Account";
  return source.replace(/[^a-z0-9]/gi, "").slice(0, 2).toUpperCase() || "AC";
}
