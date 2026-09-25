import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import { AccountMenu } from "./AccountMenu";
import { BackendStatus } from "./BackendStatus";

export function Layout() {
  const { user, signOut, isConfigured } = useAuth();
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand-lockup">
            <span className="brand-mark" aria-hidden="true">IM</span>
            <div className="brand-copy">
              <span className="brand-name">Influencer Matcher</span>
              <span className="brand-context">Creator intelligence desk</span>
            </div>
          </div>
          <nav className="main-nav" aria-label="Primary navigation">
            <NavLink to="/search" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
              <span className="nav-index">01</span>Search
            </NavLink>
            <NavLink to="/history" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
              <span className="nav-index">02</span>History
            </NavLink>
            <NavLink to="/compare" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
              <span className="nav-index">03</span>Compare
            </NavLink>
          </nav>
          <div className="account-slot">
            {import.meta.env.VITE_DEMO_MODE === "true" && <BackendStatus />}
            {isConfigured && user && <AccountMenu user={user} signOut={signOut} />}
          </div>
        </div>
      </header>
      {import.meta.env.VITE_DEMO_MODE === "true" && (
        <div className="demo-banner" role="status">
          <strong>Personal project demo</strong>
          <span>Free-tier hosting may sleep between visits; completed runs remain saved.</span>
        </div>
      )}
      <main id="main-content" className="page-content">
        <Outlet />
      </main>
    </div>
  );
}
