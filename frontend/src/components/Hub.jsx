// Shared layout for the four hub landing pages (AI Hub, Learn, Connect, Grow).
// Renders a title, a tagline, and a responsive grid of feature cards — the
// Instagram-profile-style tile view the redesign calls for. Each card links to
// an existing feature route and shows a PRO/ELITE badge when it's gated.

import { Link } from "react-router-dom";
import PlanBadge from "./PlanBadge.jsx";

export function HubCard({ to, emoji, label, desc, plan }) {
  return (
    <Link to={to} className="hub-card">
      <span className="hub-card-emoji" aria-hidden="true">{emoji}</span>
      <span className="hub-card-body">
        <span className="hub-card-title">
          {label}
          <PlanBadge plan={plan} />
        </span>
        {desc && <span className="hub-card-desc muted">{desc}</span>}
      </span>
      <span className="hub-card-chevron" aria-hidden="true">›</span>
    </Link>
  );
}

export default function Hub({ title, tagline, links, children, accent }) {
  return (
    <section className={`hub hub-${accent || "default"}`}>
      <header className="hub-head">
        <h1>{title}</h1>
        {tagline && <p className="muted">{tagline}</p>}
      </header>
      {children}
      <div className="hub-grid">
        {links.map((l) => (
          <HubCard key={l.to} {...l} />
        ))}
      </div>
    </section>
  );
}
