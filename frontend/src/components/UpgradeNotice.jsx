// A friendly "this needs a paid plan" banner with a link to /plans. Render it
// when the signed-in user's tier is below what a feature requires.

import { Link } from "react-router-dom";

const RANK = { free: 0, pro: 1, elite: 2 };

// tier: the current user's tier; need: the minimum tier for the feature.
export default function UpgradeNotice({ tier = "free", need = "pro", children }) {
  if (RANK[tier] >= RANK[need]) return null;
  const label = need === "elite" ? "Elite" : "Pro";
  return (
    <div className="upgrade-notice">
      <span>{children || `This is a ${label} feature.`}</span>
      <Link className="btn btn-primary" to="/plans">
        Upgrade to {label}
      </Link>
    </div>
  );
}
