import { NavLink } from "react-router-dom";
import { useApp } from "../context/AppContext.jsx";
import { HUBS } from "./navGroups.jsx";
import NotificationBell from "./NotificationBell.jsx";
import TokenPill from "./TokenPill.jsx";

// Desktop top bar mirrors the mobile five-slot nav: the four hub destinations
// plus a Create button that opens the same action dock. Sub-features live inside
// each hub page, so the bar stays clean instead of listing every tab.
export default function Nav({ onCreate }) {
  const { user } = useApp();

  return (
    <nav className="nav" aria-label="Main navigation">
      <NavLink to="/" end className="brand" aria-label="SkillSwap AI home">
        SkillSwap<span className="brand-ai">AI</span>
      </NavLink>

      <div className="nav-menu">
        <div className="nav-links">
          {HUBS.map((h) => (
            <NavLink key={h.key} to={h.to} end={h.end} className="nav-link">
              {h.label}
            </NavLink>
          ))}
          <button type="button" className="nav-link nav-create" onClick={onCreate}>
            + Create
          </button>
        </div>
        <div className="nav-user">
          <TokenPill />
          <NotificationBell />
          {user?.name || user?.email ? (
            <NavLink to="/settings" className="nav-who muted" title="Settings">
              {user.name || user.email}
            </NavLink>
          ) : null}
        </div>
      </div>
    </nav>
  );
}
