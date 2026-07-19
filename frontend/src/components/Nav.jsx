import { NavLink } from "react-router-dom";
import { useApp } from "../context/AppContext.jsx";

const LINKS = [
  { to: "/", label: "Goal", end: true },
  { to: "/matches", label: "Matches" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/lessons", label: "Lessons" },
  { to: "/progress", label: "Progress" },
  { to: "/community", label: "Community" },
  { to: "/resume", label: "Resume" },
  { to: "/interview", label: "Interview" },
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
    </nav>
  );
}
