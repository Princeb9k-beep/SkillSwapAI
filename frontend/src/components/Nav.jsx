import { useState } from "react";
import { NavLink } from "react-router-dom";
import { useApp } from "../context/AppContext.jsx";

const LINKS = [
  { to: "/", label: "Goal", end: true },
  { to: "/matches", label: "Matches" },
  { to: "/coach", label: "Coach" },
  { to: "/scanner", label: "Scanner" },
  { to: "/verify", label: "Verify" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/lessons", label: "Lessons" },
  { to: "/challenges", label: "Challenges" },
  { to: "/progress", label: "Progress" },
  { to: "/community", label: "Community" },
  { to: "/market", label: "Market" },
  { to: "/career", label: "Career" },
];

function MenuIcon({ open }) {
  // Vector icon (skill rule: no emoji for controls). Hamburger ⇄ close.
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      {open ? (
        <>
          <path d="M6 6l12 12" />
          <path d="M18 6L6 18" />
        </>
      ) : (
        <>
          <path d="M3 6h18" />
          <path d="M3 12h18" />
          <path d="M3 18h18" />
        </>
      )}
    </svg>
  );
}

export default function Nav() {
  const { user, logout, notify } = useApp();
  const [open, setOpen] = useState(false);

  function signOut() {
    setOpen(false);
    logout();
    notify("Signed out", "info");
  }

  return (
    <nav className="nav" aria-label="Main navigation">
      <NavLink to="/" end className="brand" aria-label="SkillSwap AI home">
        SkillSwap<span className="brand-ai">AI</span>
      </NavLink>

      <button
        type="button"
        className="nav-toggle"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls="nav-menu"
        onClick={() => setOpen((o) => !o)}
      >
        <MenuIcon open={open} />
      </button>

      <div id="nav-menu" className={`nav-menu${open ? " open" : ""}`}>
        <div className="nav-links">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className="nav-link"
              onClick={() => setOpen(false)}
            >
              {l.label}
            </NavLink>
          ))}
        </div>
        <div className="nav-user">
          {user?.name || user?.email ? (
            <span className="nav-who muted" title={user.email}>
              {user.name || user.email}
            </span>
          ) : null}
          <button
            type="button"
            className="btn btn-danger nav-signout"
            onClick={signOut}
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}
