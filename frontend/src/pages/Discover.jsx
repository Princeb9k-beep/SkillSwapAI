// Discover — a TikTok-style vertical feed of skill "clips". Each full-height
// panel is a short pitch for a skill (emoji, hook, caption, category, how many
// learners know it). For each one you decide: get the course, learn it (adds it
// as a "want" skill), or add it because you already know it (a "have" skill).
// Same snap-scroll mechanics as the lesson Stream.

import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";
import SkillClip from "../components/SkillClip.jsx";

export default function Discover() {
  const { notify } = useApp();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [current, setCurrent] = useState(0);
  const [busy, setBusy] = useState(null); // `${name}:${kind}` in flight
  const viewportRef = useRef(null);

  async function load() {
    setStatus("loading");
    try {
      setItems(await api.discoverSkills());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  function onScroll(e) {
    const el = e.currentTarget;
    const idx = Math.round(el.scrollTop / el.clientHeight);
    if (idx !== current) setCurrent(idx);
  }

  function scrollToPanel(idx) {
    const el = viewportRef.current;
    if (el) el.scrollTo({ top: idx * el.clientHeight, behavior: "smooth" });
  }

  async function addAs(item, kind) {
    setBusy(`${item.name}:${kind}`);
    try {
      await api.addSkill({ name: item.name, kind, category: item.category });
      setItems((list) => list.map((it) => (it.name === item.name ? { ...it, status: kind } : it)));
      notify(
        kind === "have"
          ? `Added ${item.name} to skills you can teach.`
          : `Added ${item.name} to skills you want to learn.`,
        "success",
      );
      const i = items.findIndex((it) => it.name === item.name);
      if (i >= 0 && i < items.length - 1) setTimeout(() => scrollToPanel(i + 1), 350);
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(null);
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading skills to discover…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;
  if (items.length === 0) {
    return (
      <EmptyState icon="✨" title="Nothing to discover right now" hint="Check back soon for new skills.">
        <Link className="btn btn-primary" to="/learn">Back to Learn</Link>
      </EmptyState>
    );
  }

  return (
    <div className="disco">
      <div className="disco-progress" aria-hidden="true">
        {items.map((it, i) => (
          <span key={it.name} className={`disco-seg${i <= current ? " on" : ""}`} />
        ))}
      </div>

      <div className="disco-viewport" ref={viewportRef} onScroll={onScroll} aria-label="Skill discovery feed">
        {items.map((item, i) => (
          <section
            key={item.name}
            className="disco-panel"
            aria-roledescription="skill"
          >
            <SkillClip
              category={item.category}
              emoji={item.emoji}
              videoUrl={item.video_url}
              active={i === current}
            />
            <div className="disco-top">
              <span className="disco-cat">{item.category}</span>
              <span className="disco-diff">{item.difficulty}</span>
            </div>

            <div className="disco-center">
              <span className="disco-emoji" aria-hidden="true">{item.emoji}</span>
              <h2 className="disco-name">{item.name}</h2>
              <p className="disco-hook">{item.hook}</p>
              <p className="disco-blurb">{item.blurb}</p>
              <span className="disco-learners">
                {item.learners > 0
                  ? `${item.learners} ${item.learners === 1 ? "learner" : "learners"} here can teach it`
                  : "Be one of the first to learn it here"}
              </span>
              {item.status && (
                <span className="disco-status">
                  {item.status === "have" ? "✓ In your skills to teach" : "✓ On your learning list"}
                </span>
              )}
            </div>

            <div className="disco-actions">
              <button
                type="button"
                className="disco-act disco-act-course"
                onClick={() => navigate("/academy")}
              >
                <span className="disco-act-emoji" aria-hidden="true">🎓</span>
                Get the course
              </button>
              <button
                type="button"
                className="disco-act disco-act-learn"
                disabled={item.status === "want" || busy === `${item.name}:want`}
                onClick={() => addAs(item, "want")}
              >
                <span className="disco-act-emoji" aria-hidden="true">📚</span>
                {item.status === "want" ? "On your list" : "Learn it"}
              </button>
              <button
                type="button"
                className="disco-act disco-act-know"
                disabled={item.status === "have" || busy === `${item.name}:have`}
                onClick={() => addAs(item, "have")}
              >
                <span className="disco-act-emoji" aria-hidden="true">✋</span>
                {item.status === "have" ? "Added" : "I know this"}
              </button>
            </div>

            <span className="disco-swipe" aria-hidden="true">Swipe up ↑</span>
          </section>
        ))}
      </div>
    </div>
  );
}
