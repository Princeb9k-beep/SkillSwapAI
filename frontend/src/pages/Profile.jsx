// Public profile: a learner's gamification stats, skills, badges, and reputation.

import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { ErrorBanner } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const memberSince = (iso) =>
  iso
    ? new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "long" })
    : null;

export default function Profile() {
  const { id } = useParams();
  const [p, setP] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setP(await api.userProfile(id));
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (status === "loading") return <SkeletonPage cards={3} label="Loading profile…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  const rep = p.reputation || {};

  return (
    <section className="profile">
      <Link className="btn btn-ghost" to="/progress">← Leaderboard</Link>

      <div className="card profile-head">
        <div className="profile-avatar" aria-hidden="true">
          {(p.name || "?").charAt(0).toUpperCase()}
        </div>
        <div>
          <h1>{p.name}</h1>
          {p.tier && p.tier !== "free" && (
            <span className={`tier-pill tier-${p.tier}`}>{p.tier.toUpperCase()}</span>
          )}
          {p.goal && <p className="muted">{p.goal}</p>}
          {memberSince(p.member_since) && (
            <p className="field-hint">Member since {memberSince(p.member_since)}</p>
          )}
        </div>
      </div>

      <div className="profile-stats">
        <div className="card stat-tile"><span className="stat-num">{p.level}</span><span className="muted">Level</span></div>
        <div className="card stat-tile"><span className="stat-num">{p.xp}</span><span className="muted">XP</span></div>
        <div className="card stat-tile"><span className="stat-num">{p.streak}🔥</span><span className="muted">Day streak</span></div>
        {rep.count > 0 && typeof rep.score === "number" && (
          <div className="card stat-tile"><span className="stat-num">{rep.score.toFixed(1)}</span><span className="muted">Rating ({rep.count})</span></div>
        )}
      </div>

      <div className="card">
        <h3>Skills</h3>
        {p.skills.length === 0 ? (
          <p className="field-hint">No skills listed yet.</p>
        ) : (
          <div className="tags">
            {p.skills.map((s) => (
              <span key={s.name} className={`tag${s.verified ? " tag-verified" : ""}`}>
                {s.name}
                {s.verified && " ✓"}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h3>Badges</h3>
        {p.badges.length === 0 ? (
          <p className="field-hint">No badges earned yet.</p>
        ) : (
          <div className="badge-grid">
            {p.badges.map((b) => (
              <div key={b.code} className="badge-item" title={b.description || ""}>
                <span className="badge-medal" aria-hidden="true">🏅</span>
                <span className="badge-title">{b.title}</span>
              </div>
            ))}
          </div>
        )}
      </div>

    </section>
  );
}
