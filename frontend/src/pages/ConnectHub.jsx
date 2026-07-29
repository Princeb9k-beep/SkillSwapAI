// Connect — "Community Pulse". The social surface: matches, messages, activity,
// rooms, community, meetups, sessions, and search.

import Hub from "../components/Hub.jsx";
import { NAV_GROUPS } from "../components/navGroups.jsx";

const G = NAV_GROUPS.find((g) => g.key === "connect");

export default function ConnectHub() {
  return <Hub title="Connect" tagline={G.tagline} links={G.links} accent="connect" />;
}
