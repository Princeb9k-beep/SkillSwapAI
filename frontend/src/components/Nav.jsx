import { NavLink } from "react-router-dom";
import { useApp } from "../context/AppContext.jsx";
import { NAV_GROUPS } from "./navGroups.jsx";

// Flat list (desktop top bar) is derived from the same grouped source of truth
// the mobile BottomNav uses, so the two navigations never drift apart.
const LINKS = [
  { to: "/", label: "Goal", end: true },
  ...NAV_GROUPS.flatMap((g) => g.links),
];

export default function Nav() {
  const { user, logout, notify } = useApp();

  function signOut() {
    logout();
    notify("Signed out", "info");
  }

  return (
    <nav className="nav" aria-label="Main navigation">
      <NavLink to="/" end className="brand" aria-label="SkillSwap AI home">
        SkillSwap<span className="brand-ai">AI</span>
      </NavLink>

      <div className="nav-menu">
        <div className="nav-links">
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className="nav-link">
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
