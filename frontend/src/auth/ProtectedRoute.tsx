import { Navigate, Outlet } from "react-router-dom";

import { isApiConfigured } from "../api/client";
import { BackendGate } from "../backend/BackendGate";
import { useBackend } from "../backend/BackendProvider";
import { useAuth } from "./AuthProvider";

export function ProtectedRoute() {
  const { session, loading, isConfigured } = useAuth();
  const { status, entered } = useBackend();
  if (loading) return <div className="auth-loading">Checking your session...</div>;
  if (import.meta.env.PROD && !isApiConfigured) return <div className="auth-loading">VITE_API_BASE_URL is not configured.</div>;
  if (import.meta.env.PROD && !isConfigured) return <div className="auth-loading">Supabase Auth is not configured.</div>;
  if (!isConfigured) return <Outlet />;
  if (!session) return <Navigate to="/login" replace />;
  // Gate the very first visit only. After that the routed app stays mounted even
  // if the host goes to sleep, so a wake never costs the user their page; the
  // pill reports the state and each request fails on its own with a message.
  if (!entered && status !== "online") return <BackendGate />;
  return <Outlet />;
}
