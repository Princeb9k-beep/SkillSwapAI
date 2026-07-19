// Daily AI Challenges (spec §3.8): one Groq-generated challenge per day that
// awards XP + streak on completion.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

export default function Challenges() {
  const { notify } = useApp();
  const [challenge, setChallenge] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      setChallenge(await api.todayChallenge());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function complete() {
    setBusy(true);
    try {
      const res = await api.completeChallenge(challenge.id);
      setChallenge((c) => ({ ...c, completed: true }));
      const badge = res.new_achievements?.length
        ? ` Badge: ${res.new_achievements.join(", ")}!`
        : "";
      notify(`+15 XP · level ${res.level} · ${res.streak}-day streak.${badge}`, "success");
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  if (status === "loading") return <SkeletonPage cards={1} label="Loading today's challenge…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>Daily Challenge</h1>
      <p className="muted">A fresh bite-sized challenge each day. Complete it for +15 XP.</p>

      <article className={`card challenge-card ${challenge.completed ? "done" : ""}`}>
        <div className="row-between">
          <span className="badge">Today</span>
          {challenge.completed && (
            <span className="badge status-completed">Completed</span>
          )}
        </div>
        <h2>{challenge.title}</h2>
        {challenge.description && <p>{challenge.description}</p>}
        {!challenge.completed && (
          <button
            className="btn btn-primary"
            onClick={complete}
            disabled={busy}
            aria-busy={busy}
          >
            {busy ? "Completing…" : "Mark complete (+15 XP)"}
          </button>
        )}
      </article>
    </section>
  );
}
