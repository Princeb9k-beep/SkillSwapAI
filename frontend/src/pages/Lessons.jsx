// Daily lessons with gamified completion + a simple progress bar.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import LessonCard from "../components/LessonCard.jsx";
import { LoadingState, ErrorBanner } from "../components/States.jsx";

export default function Lessons() {
  const { notify } = useApp();
  const [lessons, setLessons] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

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

  async function complete(id) {
    try {
      await api.completeLesson(id);
      setLessons((ls) => ls.map((l) => (l.id === id ? { ...l, completed: true } : l)));
      notify("Nice work! Lesson completed.", "success");
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (status === "loading") return <LoadingState label="Fetching today's lessons…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  const done = lessons.filter((l) => l.completed).length;
  const pct = lessons.length ? Math.round((done / lessons.length) * 100) : 0;

  return (
    <section>
      <h1>Today's Lessons</h1>
      <div
        className="progress"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${pct}% of today's lessons complete`}
      >
        <div className="progress-bar" style={{ width: `${pct}%` }} />
      </div>
      <p className="muted">
        {done} of {lessons.length} complete
      </p>
      <div className="grid">
        {lessons.map((l) => (
          <LessonCard key={l.id} lesson={l} onComplete={complete} />
        ))}
      </div>
    </section>
  );
}
