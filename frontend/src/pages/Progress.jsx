// Gamification (spec §3.1): XP, level, streak, achievements + leaderboard.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { ErrorBanner } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

export default function Progress() {
  const [prog, setProg] = useState(null);
  const [board, setBoard] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const [p, b] = await Promise.all([api.getProgress(), api.getLeaderboard()]);
      setProg(p);
      setBoard(b);
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (status === "loading") return <SkeletonPage cards={2} label="Loading your progress…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>Your progress</h1>

      <div className="grid stat-grid">
        <div className="card stat">
          <span className="stat-num">{prog.level}</span>
          <span className="muted">Level</span>
        </div>
        <div className="card stat">
          <span className="stat-num">{prog.xp}</span>
          <span className="muted">Total XP</span>
        </div>
        <div className="card stat">
          <span className="stat-num">{prog.streak}</span>
          <span className="muted">Day streak</span>
        </div>
      </div>

      <div className="card">
        <div className="row-between">
          <strong>Level {prog.level}</strong>
          <span className="muted">
            {prog.xp_into_level} / {prog.xp_for_next_level} XP to level {prog.level + 1}
          </span>
        </div>
        <div
          className="progress"
          role="progressbar"
          aria-valuenow={prog.level_progress_pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${prog.level_progress_pct}% to next level`}
        >
          <div className="progress-bar" style={{ width: `${prog.level_progress_pct}%` }} />
        </div>
        <p className="muted xp-hint">Complete daily lessons to earn +20 XP each.</p>
      </div>

      <h2>Achievements</h2>
      {prog.achievements.length === 0 ? (
        <p className="muted">None yet — complete a lesson to earn your first badge.</p>
      ) : (
        <div className="grid">
          {prog.achievements.map((a) => (
            <div className="card achievement" key={a.code}>
              <span className="badge">Badge</span>
              <h3>{a.title}</h3>
              <p className="muted">{a.description}</p>
            </div>
          ))}
        </div>
      )}

      <h2>Leaderboard</h2>
      <div className="card lb-card">
        <table className="leaderboard">
          <thead>
            <tr>
              <th>#</th>
              <th>Learner</th>
              <th>Level</th>
              <th>XP</th>
            </tr>
          </thead>
          <tbody>
            {board.map((e) => (
              <tr key={e.user_id}>
                <td>{e.rank}</td>
                <td>{e.name}</td>
                <td>{e.level}</td>
                <td>{e.xp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
