// Route guard for PRO/ELITE features. Wraps a page and, when the signed-in
// user's tier is below what the route needs, renders a full-page upgrade prompt
// instead of the feature. Admins are treated as Elite. Pages that show their own
// free preview (e.g. Academy, Rooms) gate inline and are not wrapped here.

import { useApp } from "../context/AppContext.jsx";
import UpgradeNotice from "./UpgradeNotice.jsx";

const RANK = { free: 0, pro: 1, elite: 2 };

export default function RequirePlan({ need = "pro", name, children }) {
  const { user } = useApp();
  const tier = user?.is_admin ? "elite" : user?.tier || "free";
  if (RANK[tier] >= RANK[need]) return children;

  const label = need === "elite" ? "Elite" : "Pro";
  return (
    <section className="plan-gate">
      <div className="plan-gate-emoji" aria-hidden="true">{need === "elite" ? "💎" : "⭐"}</div>
      <h1>{name || "A premium feature"}</h1>
      <p className="muted">
        {name ? `${name} is` : "This is"} a {label} feature. Upgrade to unlock it and
        the rest of the {label} toolkit.
      </p>
      <UpgradeNotice tier={tier} need={need} />
    </section>
  );
}
