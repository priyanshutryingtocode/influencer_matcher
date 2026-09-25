import { useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../auth/AuthProvider";

type AuthMode = "signin" | "signup";

const minimumPasswordLength = 8;

export function LoginPage() {
  const { isConfigured, signInWithPassword, signUp } = useAuth();
  const [mode, setMode] = useState<AuthMode>("signin");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode);
    setMessage(null);
    setError(null);
    setPassword("");
    setConfirmPassword("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    const normalizedEmail = email.trim();
    if (!normalizedEmail) {
      setError("Enter your email address.");
      return;
    }
    if (password.length < minimumPasswordLength) {
      setError(`Password must be at least ${minimumPasswordLength} characters.`);
      return;
    }
    if (mode === "signup") {
      if (displayName.trim().length < 2) {
        setError("Enter a display name with at least two characters.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
    }

    setIsSubmitting(true);
    try {
      if (mode === "signup") {
        const hasSession = await signUp({ displayName, email: normalizedEmail, password });
        setMessage(hasSession ? "Account created. You are signed in." : "Account created. Check your email to confirm it.");
      } else {
        await signInWithPassword(normalizedEmail, password);
      }
    } catch (caught) {
      setError(authErrorMessage(caught, mode === "signup" ? "Could not create the account." : "Could not sign in."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <p className="eyebrow">Influencer Matcher</p>
        <h1>{mode === "signin" ? "Sign in to your desk." : "Create your account."}</h1>
        <p className="page-description">
          {mode === "signin" ? "Use the email and password for your demo account." : "Your account and run history are isolated by your Supabase user ID."}
        </p>
        {!isConfigured ? (
          <div className="system-note system-note-error" role="alert">
            <span className="system-note-signal" aria-hidden="true" />
            <strong>Auth not configured</strong>
            <span>Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in the frontend environment.</span>
          </div>
        ) : (
          <>
            <div className="auth-mode-switch" role="group" aria-label="Account access">
              <button className={mode === "signin" ? "auth-mode-button active" : "auth-mode-button"} type="button" aria-pressed={mode === "signin"} onClick={() => changeMode("signin")}>Sign in</button>
              <button className={mode === "signup" ? "auth-mode-button active" : "auth-mode-button"} type="button" aria-pressed={mode === "signup"} onClick={() => changeMode("signup")}>Create</button>
            </div>
            <form className="auth-form" onSubmit={submit}>
              {mode === "signup" && (
                <label>
                  Display name
                  <input type="text" required minLength={2} maxLength={60} autoComplete="name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Your name" />
                </label>
              )}
              <label>
                Email address
                <input type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
              </label>
              <label>
                Password
                <input type="password" required minLength={minimumPasswordLength} autoComplete={mode === "signin" ? "current-password" : "new-password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 8 characters" />
              </label>
              {mode === "signup" && (
                <label>
                  Confirm password
                  <input type="password" required minLength={minimumPasswordLength} autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Repeat your password" />
                </label>
              )}
              <button className="primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Working..." : mode === "signin" ? "Sign in to account" : "Create account"}
              </button>
              {message && <p className="auth-message">{message}</p>}
              {error && <p className="auth-error" role="alert">{error}</p>}
            </form>
          </>
        )}
      </section>
    </main>
  );
}

export function authErrorMessage(caught: unknown, fallback: string): string {
  if (caught instanceof Error && caught.message.trim()) return caught.message;
  if (typeof caught === "string" && caught.trim()) return caught;
  if (caught && typeof caught === "object" && "message" in caught) {
    const message = (caught as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}
