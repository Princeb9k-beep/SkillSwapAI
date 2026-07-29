// Learn — "Academy Stream". Your learning surface: courses, lessons, flashcards,
// challenges, progress, and social learning, as a card grid — fronted by a
// featured entry into the immersive, Reels-style lesson Stream.

import { Link } from "react-router-dom";
import Hub from "../components/Hub.jsx";
import { NAV_GROUPS } from "../components/navGroups.jsx";

const G = NAV_GROUPS.find((g) => g.key === "learn");

export default function LearnHub() {
  return (
    <Hub title="Learn" tagline={G.tagline} links={G.links} accent="learn">
      <Link to="/stream" className="stream-feature">
        <span className="stream-feature-emoji" aria-hidden="true">▶</span>
        <span className="stream-feature-body">
          <span className="stream-feature-title">Today's Stream</span>
          <span className="stream-feature-desc">
            Swipe through today's lessons, Reels-style.
          </span>
        </span>
        <span className="stream-feature-go" aria-hidden="true">›</span>
      </Link>
    </Hub>
  );
}
