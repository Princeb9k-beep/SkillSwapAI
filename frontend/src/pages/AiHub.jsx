// Home — "AI Hub". The central landing for AI-powered actions: the four AI
// tools as a card grid, plus a "For You" strip of quick, personalized starting
// points. Honest shortcuts (not a fabricated feed) that get the user into an AI
// task in one tap.

import { Link } from "react-router-dom";
import Hub from "../components/Hub.jsx";
import { NAV_GROUPS } from "../components/navGroups.jsx";
import { useApp } from "../context/AppContext.jsx";

const AI = NAV_GROUPS.find((g) => g.key === "ai");

function forYou(user) {
  // Suggestions keyed to what the user has (or hasn't) set up yet, so the strip
  // feels personal without inventing data.
  const items = [];
  if (!user?.goal) {
    items.push({ to: "/goal", emoji: "🎯", text: "Set your goal and get a roadmap" });
  } else {
    items.push({ to: "/lessons", emoji: "📖", text: `Continue toward: ${user.goal}` });
  }
  items.push(
    { to: "/discover", emoji: "✨", text: "Discover new skills to learn" },
    { to: "/coach", emoji: "🧠", text: "Ask the AI coach a question" },
    { to: "/scanner", emoji: "🔍", text: "Get feedback on your resume or code" },
    { to: "/flashcards", emoji: "🃏", text: "Review today's flashcards" },
    { to: "/challenges", emoji: "⚡", text: "Take today's challenge" },
  );
  return items;
}

export default function AiHub() {
  const { user } = useApp();
  const suggestions = forYou(user);

  return (
    <Hub title="AI Hub" tagline={AI.tagline} links={AI.links} accent="ai">
      <section className="foryou" aria-label="For you">
        <h2 className="foryou-title">For you</h2>
        <div className="foryou-strip">
          {suggestions.map((s) => (
            <Link key={s.to + s.text} to={s.to} className="foryou-card">
              <span className="foryou-emoji" aria-hidden="true">{s.emoji}</span>
              <span className="foryou-text">{s.text}</span>
            </Link>
          ))}
        </div>
      </section>
    </Hub>
  );
}
