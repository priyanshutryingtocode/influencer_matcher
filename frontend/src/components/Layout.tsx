import { NavLink, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="topbar">
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
      </header>
      <main id="main-content" className="page-content">
        <Outlet />
      </main>
    </div>
  );
}
