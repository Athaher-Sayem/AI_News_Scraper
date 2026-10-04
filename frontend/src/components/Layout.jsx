import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { NAV_ITEMS } from "../sections.js";
import { formatDate } from "../utils.js";

function SearchBox() {
  const navigate = useNavigate();
  const [term, setTerm] = useState("");

  function submit(event) {
    event.preventDefault();
    const value = term.trim();
    if (value) navigate(`/search?q=${encodeURIComponent(value)}`);
  }

  return (
    <form className="search" role="search" onSubmit={submit}>
      <label className="visually-hidden" htmlFor="site-search">Search stories</label>
      <input
        id="site-search"
        name="q"
        value={term}
        maxLength={200}
        placeholder="Search headlines…"
        onChange={(event) => setTerm(event.target.value)}
      />
      <button type="submit">Search</button>
    </form>
  );
}

export default function Layout() {
  return (
    <div className="page">
      <a className="skip-link" href="#main">Skip to content</a>

      <div className="topbar">
        <span>{formatDate(new Date().toISOString())}</span>
        <span className="topbar__tagline">Collected headlines · sourced and attributed</span>
      </div>

      <header className="masthead">
        <Link to="/" className="brand">
          Newsroom<span>Collected news, connected sources</span>
        </Link>
        <SearchBox />
      </header>

      <nav className="mainnav" aria-label="Sections">
        {NAV_ITEMS.map((section) => (
          <NavLink
            key={section.slug}
            to={`/section/${section.slug}`}
            className={({ isActive }) => (isActive ? "mainnav__link is-active" : "mainnav__link")}
          >
            {section.label}
          </NavLink>
        ))}
        <NavLink to="/about" className={({ isActive }) => (isActive ? "mainnav__link is-active" : "mainnav__link")}>
          About
        </NavLink>
        <NavLink to="/contact" className={({ isActive }) => (isActive ? "mainnav__link is-active" : "mainnav__link")}>
          Contact
        </NavLink>
      </nav>

      <main id="main" className="content">
        <Outlet />
      </main>

      <footer className="footer">
        <p className="footer__brand">Newsroom</p>
        <p>
          Every excerpt stays attributed to its original publisher. Collected source
          material is shown for review and does not imply editorial approval.
        </p>
        <p className="footer__links">
          <Link to="/">Latest</Link>
          <Link to="/about">About</Link>
          <Link to="/contact">Contact</Link>
          <a href="/api/v1/docs/">API docs</a>
          <a href="/collected/">Collected site</a>
          <a href="/admin/">Editor admin</a>
        </p>
      </footer>
    </div>
  );
}
