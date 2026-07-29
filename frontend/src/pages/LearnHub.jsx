// Learn — "Academy Stream". Your learning surface: courses, lessons, flashcards,
// challenges, progress, and social learning, as a card grid.

import Hub from "../components/Hub.jsx";
import { NAV_GROUPS } from "../components/navGroups.jsx";

const G = NAV_GROUPS.find((g) => g.key === "learn");

export default function LearnHub() {
  return <Hub title="Learn" tagline={G.tagline} links={G.links} accent="learn" />;
}
