// Grow — "Career Engine". Professional growth and monetization: career tools,
// the marketplace, partners, verification, plans, and settings.

import Hub from "../components/Hub.jsx";
import { NAV_GROUPS } from "../components/navGroups.jsx";
import { useApp } from "../context/AppContext.jsx";

const G = NAV_GROUPS.find((g) => g.key === "grow");

export default function GrowHub() {
  const { user } = useApp();
  // Admins get a moderation tile here alongside the growth tools.
  const links = user?.is_admin
    ? [...G.links, { to: "/admin", label: "Moderation", icon: "shield", desc: "Review reports and content." }]
    : G.links;
  return <Hub title="Grow" tagline={G.tagline} links={links} accent="grow" />;
}
