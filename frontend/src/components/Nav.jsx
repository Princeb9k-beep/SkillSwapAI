import { NavLink } from "react-router-dom";

const LINKS = [
  { to: "/", label: "Goal", end: true },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/lessons", label: "Lessons" },
  { to: "/resume", label: "Resume" },
  { to: "/interview", label: "Interview" },
];

export default function Nav() {
  return (
    <nav className="nav">
      <span className="brand">SkillSwap<span className="brand-ai">AI</span></span>
      <div className="nav-links">
        {LINKS.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className="nav-link">
            {l.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
