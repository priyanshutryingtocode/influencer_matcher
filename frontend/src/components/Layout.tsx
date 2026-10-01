import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

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
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const isFirstRender = useRef(true);

  useEffect(() => {
    /* Nothing announced a page change, so a keyboard or screen-reader user
     * moved through three routes with no signal that anything had happened.
     * Focusing <main> (rather than the h1) also puts the next Tab back at the
     * top of the new page's controls. Skipped on first render so arriving at
     * the app does not yank focus away from whatever the user was doing. */
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    mainRef.current?.focus();
  }, [location.pathname]);

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
      {/* tabindex="-1" so the skip link can actually move focus here, not just
       * scroll to it -- several browsers ignore focus() on a non-focusable
       * element, which left the target of the skip link unreliable. */}
      <main id="main-content" className="page-content" tabIndex={-1} ref={mainRef}>
        <Outlet />
      </main>
    </div>
  );
}
