// Gamification (spec §3.1): XP, level, streak, achievements + leaderboard.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";
import { share } from "../share.js";

const GOALS = [20, 30, 50, 100];

export default function Progress() {
  const { notify } = useApp();
  const [prog, setProg] = useState(null);
  const [board, setBoard] = useState([]);
  const [league, setLeague] = useState(null);
  const [shareLink, setShareLink] = useState("");
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const [p, b, l] = await Promise.all([
        api.getProgress(),
        api.getLeaderboard(),
        api.getLeague().catch(() => null),
      ]);
      setProg(p);
      setBoard(b);
      setLeague(l);
      setStatus("ready");
      // A referral link doubles as the share URL — shares become invites.
      api.referralMe().then((r) => setShareLink(r.link)).catch(() => {});
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  async function shareText(text) {
    const res = await share({ title: "SkillSwap AI", text, url: shareLink || window.location.origin });
    if (res === "copied") notify("Copied to clipboard — paste it anywhere!", "success");
    else if (res === "failed") notify("Couldn't share on this device.", "error");
  }

  async function chooseGoal(xp) {
    try {
      await api.setDailyGoal(xp);
      setProg((p) => ({ ...p, daily_goal: xp, daily_goal_pct: Math.min(100, Math.round((100 * p.day_xp) / xp)), daily_goal_met: p.day_xp >= xp }));
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function buyFreeze() {
    setBusy(true);
    try {
      const res = await api.buyStreakFreeze();
      setProg((p) => ({ ...p, streak_freezes: res.streak_freezes }));
      notify("Streak freeze added", "success");
      window.dispatchEvent(new Event("tokens:changed"));
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
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

      {/* Daily goal */}
      <div className="card">
        <div className="row-between">
          <strong>Today's goal</strong>
          <span className="muted">{prog.day_xp} / {prog.daily_goal} XP</span>
        </div>
        <div className="progress" role="progressbar" aria-valuenow={prog.daily_goal_pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="progress-bar" style={{ width: `${prog.daily_goal_pct}%` }} />
        </div>
        <div className="goal-picker">
          <span className="muted">Set goal:</span>
          {GOALS.map((g) => (
            <button
              key={g}
              type="button"
              className={`chip${prog.daily_goal === g ? " active" : ""}`}
              onClick={() => chooseGoal(g)}
            >
              {g} XP
            </button>
          ))}
        </div>
      </div>

      {/* Streak freezes */}
      <div className="card row-between">
        <div>
          <strong>❄️ Streak freezes: {prog.streak_freezes}</strong>
          <p className="muted xp-hint">Automatically saves your streak after one missed day.</p>
        </div>
        <div className="progress-share-actions">
          {prog.streak > 0 && (
            <button
              type="button"
              className="btn"
              onClick={() => shareText(`I'm on a ${prog.streak}-day learning streak on SkillSwap AI! 🔥`)}
            >
              Share streak
            </button>
          )}
          <button type="button" className="btn" onClick={buyFreeze} disabled={busy}>
            {busy ? "…" : "Buy (20 tokens)"}
          </button>
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

      {league && (
        <>
          <div className="row-between">
            <h2>{league.division} League · this week</h2>
            {league.entries.some((e) => e.is_me) && (
              <button
                type="button"
                className="btn"
                onClick={() => {
                  const me = league.entries.find((e) => e.is_me);
                  shareText(`I'm ranked #${me.rank} in the ${league.division} League on SkillSwap AI this week! 🏆`);
                }}
              >
                Share rank
              </button>
            )}
          </div>
          <div className="card lb-card">
            <table className="leaderboard">
              <thead>
                <tr><th>#</th><th>Learner</th><th>Weekly XP</th></tr>
              </thead>
              <tbody>
                {league.entries.length === 0 ? (
                  <tr><td colSpan={3} className="muted">No one has earned XP this week yet.</td></tr>
                ) : (
                  league.entries.map((e) => (
                    <tr key={e.user_id} className={e.is_me ? "lb-me" : ""}>
                      <td>{e.rank}</td>
                      <td><Link className="lb-name" to={`/u/${e.user_id}`}>{e.name}</Link>{e.is_me && " (you)"}</td>
                      <td>{e.week_xp}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2>All-time leaderboard</h2>
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
                <td><Link className="lb-name" to={`/u/${e.user_id}`}>{e.name}</Link></td>
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
