import { useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../auth/AuthProvider";

export function LoginPage() {
  const { isConfigured, signInWithEmail } = useAuth();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setIsSending(true);
    try {
      await signInWithEmail(email);
      setMessage("Check your inbox for the sign-in link.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not send the sign-in link.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <p className="eyebrow">Influencer Matcher</p>
        <h1>Sign in to your desk.</h1>
        <p className="page-description">Use your email to receive a secure Supabase sign-in link.</p>
        {!isConfigured ? (
          <div className="system-note system-note-error" role="alert">
            <span className="system-note-signal" aria-hidden="true" />
            <strong>Auth not configured</strong>
            <span>Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in the frontend environment.</span>
          </div>
        ) : (
          <form className="auth-form" onSubmit={submit}>
            <label>
              Email address
              <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
            </label>
            <button className="primary-button" type="submit" disabled={isSending}>
              {isSending ? "Sending link..." : "Email me a sign-in link"}
            </button>
            {message && <p className="auth-message">{message}</p>}
            {error && <p className="auth-error">{error}</p>}
          </form>
        )}
      </section>
    </main>
  );
}
