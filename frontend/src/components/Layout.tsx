import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import { AccountMenu } from "./AccountMenu";
import { BackendStatus } from "./BackendStatus";

const navItems = [
  { to: "/search", label: "Search" },
  { to: "/history", label: "History" },
  { to: "/compare", label: "Compare" },
];

export function Layout() {
  const { user, signOut, isConfigured } = useAuth();
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand-lockup">
            <span className="brand-mark" aria-hidden="true">IM</span>
            <span className="brand-name">Influencer Matcher</span>
          </div>
          <nav className="main-nav" aria-label="Primary navigation">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="account-slot">
            <BackendStatus />
            {isConfigured && user && <AccountMenu user={user} signOut={signOut} />}
          </div>
        </div>
      </header>
      <main id="main-content" className="page-content">
        <Outlet />
      </main>
    </div>
  );
}
