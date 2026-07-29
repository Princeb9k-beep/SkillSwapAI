// Learn — "Academy Stream": an Instagram-Reels-style vertical feed of today's
// lessons. Each lesson is a full-height panel you swipe/scroll through with
// snap-scrolling; a progress overlay tracks how far you've come, and completing
// a card advances you. The classic list view still lives at /lessons — this is
// the immersive way to move through the same daily set.

import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

function CheckIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

export default function Stream() {
  const { notify } = useApp();
  const navigate = useNavigate();
  const [lessons, setLessons] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [current, setCurrent] = useState(0);
  const [busyId, setBusyId] = useState(null);
  const viewportRef = useRef(null);

  async function load() {
    setStatus("loading");
    try {
      const data = await api.dailyLessons();
      setLessons(data);
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  // Track which panel is centered to drive the progress overlay + dots.
  function onScroll(e) {
    const el = e.currentTarget;
    const idx = Math.round(el.scrollTop / el.clientHeight);
    if (idx !== current) setCurrent(idx);
  }

  function scrollToPanel(idx) {
    const el = viewportRef.current;
    if (el) el.scrollTo({ top: idx * el.clientHeight, behavior: "smooth" });
  }

  async function complete(lesson) {
    setBusyId(lesson.id);
    try {
      const res = await api.completeLesson(lesson.id);
      setLessons((ls) => ls.map((l) => (l.id === lesson.id ? { ...l, completed: true } : l)));
      const badge = res.new_achievements?.length
        ? ` Badge unlocked: ${res.new_achievements.join(", ")}!`
        : "";
      notify(`+20 XP · level ${res.level} · ${res.streak}-day streak.${badge}`, "success");
      // Auto-advance to the next card so the stream keeps flowing.
      const i = lessons.findIndex((l) => l.id === lesson.id);
      if (i >= 0 && i < lessons.length - 1) setTimeout(() => scrollToPanel(i + 1), 350);
      else setTimeout(() => scrollToPanel(lessons.length), 350);
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusyId(null);
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading your stream…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;
  if (lessons.length === 0) {
    return (
      <EmptyState
        icon="📖"
        title="No lessons in your stream yet"
        hint="Set a goal and we'll generate a daily set you can swipe through."
      >
        <Link className="btn btn-primary" to="/goal">Set a goal</Link>
      </EmptyState>
    );
  }

  const done = lessons.filter((l) => l.completed).length;
  const pct = Math.round((done / lessons.length) * 100);
  // The last swipe target is a wrap-up panel after the final lesson.
  const total = lessons.length + 1;

  return (
    <div className="stream">
      {/* Progress overlay — segmented bar (one segment per lesson) + count. */}
      <div className="stream-progress" aria-hidden="true">
        {lessons.map((l, i) => (
          <span
            key={l.id}
            className={`stream-seg${l.completed ? " done" : ""}${i === current ? " current" : ""}`}
          />
        ))}
      </div>
      <div className="stream-meta">
        <span className="stream-count">
          {Math.min(current + 1, lessons.length)} / {lessons.length}
        </span>
        <span className="stream-pct muted">{pct}% complete today</span>
      </div>

      <div
        className="stream-viewport"
        ref={viewportRef}
        onScroll={onScroll}
        aria-label="Lesson stream"
      >
        {lessons.map((l) => (
          <section
            key={l.id}
            className={`stream-panel${l.completed ? " done" : ""}`}
            aria-roledescription="lesson"
          >
            <div className="stream-panel-inner">
              <span className="stream-day">Day {l.day}</span>
              <h2 className="stream-title">{l.title}</h2>
              {l.content && <p className="stream-content">{l.content}</p>}
              {l.completed ? (
                <div className="stream-done-tag"><CheckIcon /> Completed</div>
              ) : (
                <button
                  className="btn btn-primary stream-cta"
                  disabled={busyId === l.id}
                  aria-busy={busyId === l.id}
                  onClick={() => complete(l)}
                >
                  {busyId === l.id ? "Saving…" : "Mark complete"}
                </button>
              )}
            </div>
            <span className="stream-swipe muted" aria-hidden="true">Swipe up ↑</span>
          </section>
        ))}

        {/* Wrap-up panel */}
        <section className="stream-panel stream-outro" aria-roledescription="summary">
          <div className="stream-panel-inner">
            <span className="stream-outro-emoji" aria-hidden="true">{done === lessons.length ? "🎉" : "💪"}</span>
            <h2 className="stream-title">
              {done === lessons.length ? "You finished today's stream!" : "Keep the streak going"}
            </h2>
            <p className="stream-content">
              {done} of {lessons.length} lessons done.
              {done === lessons.length ? " Come back tomorrow for more." : " Swipe back up to finish the rest."}
            </p>
            <div className="stream-outro-actions">
              <button className="btn btn-primary" onClick={() => navigate("/challenges")}>
                Take today's challenge
              </button>
              <Link className="btn" to="/learn">Back to Learn</Link>
            </div>
          </div>
        </section>
      </div>

      {/* Right-edge dots (Reels-style) to jump between panels. */}
      <div className="stream-dots" role="tablist" aria-label="Jump to lesson">
        {Array.from({ length: total }).map((_, i) => (
          <button
            key={i}
            type="button"
            role="tab"
            aria-selected={i === current}
            aria-label={i < lessons.length ? `Lesson ${i + 1}` : "Summary"}
            className={`stream-dot${i === current ? " active" : ""}`}
            onClick={() => scrollToPanel(i)}
          />
        ))}
      </div>
    </div>
  );
}
