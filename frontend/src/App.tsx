import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthProvider";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { BackendProvider } from "./backend/BackendProvider";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { ComparePage } from "./pages/ComparePage";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";
import { SearchPage } from "./pages/SearchPage";
import "./styles.css";

export function App() {
  return (
    <AuthProvider>
      <BackendProvider>
        <BrowserRouter>
          {/* Inside the router so the boundary can stay mounted across route
              changes: a boundary that remounts with the route would reset its
              error state on every navigation and never recover. */}
          <ErrorBoundary>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route index element={<Navigate to="/search" replace />} />
                  <Route path="search" element={<SearchPage />} />
                  <Route path="history" element={<HistoryPage />} />
                  <Route path="compare" element={<ComparePage />} />
                  <Route path="*" element={<Navigate to="/search" replace />} />
                </Route>
              </Route>
            </Routes>
          </ErrorBoundary>
        </BrowserRouter>
      </BackendProvider>
    </AuthProvider>
  );
}
