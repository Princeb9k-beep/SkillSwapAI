// Public profile: a learner's gamification stats, skills, badges, and reputation.

import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";
import { share } from "../share.js";

const memberSince = (iso) =>
  iso
    ? new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "long" })
    : null;

export default function Profile() {
  const { id } = useParams();
  const { notify, user } = useApp();
  const [p, setP] = useState(null);
  const [certs, setCerts] = useState([]);
  const [buddyBusy, setBuddyBusy] = useState(false);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  const isOwn = user?.id === Number(id);

  async function addBuddy() {
    setBuddyBusy(true);
    try {
      await api.inviteBuddy(Number(id));
      notify("Buddy request sent", "success");
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBuddyBusy(false);
    }
  }

  async function endorse(skill) {
    try {
      const res = await api.endorse(Number(id), skill);
      setP((prev) => ({
        ...prev,
        skills: prev.skills.map((s) =>
          s.name === skill ? { ...s, endorsements: res.endorsements, endorsed: true } : s,
        ),
      }));
      notify(`Endorsed ${skill}`, "success");
    } catch (err) {
      notify(err.message, "error");
    }
  }

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

  useEffect(() => {
    if (isOwn) api.myCertificates().then(setCerts).catch(() => {});
  }, [isOwn]);

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
          {p.availability_note && (
            <p className="field-hint">🗓 Usually free: {p.availability_note}</p>
          )}
          <div className="profile-actions">
            <Link className="btn btn-primary" to={`/sessions?to=${p.id}&name=${encodeURIComponent(p.name)}`}>
              Book a session
            </Link>
            <button className="btn" onClick={addBuddy} disabled={buddyBusy}>
              {buddyBusy ? "Sending…" : "Add as learning buddy"}
            </button>
          </div>
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
          <ul className="skill-endorse-list">
            {p.skills.map((s) => (
              <li key={s.name} className="skill-endorse-row">
                <span className={`tag${s.verified ? " tag-verified" : ""}`}>
                  {s.name}
                  {s.verified && " ✓"}
                </span>
                {s.endorsements > 0 && (
                  <span className="endorse-count muted">👍 {s.endorsements}</span>
                )}
                {!isOwn && (
                  <button
                    type="button"
                    className="btn btn-ghost endorse-btn"
                    disabled={s.endorsed}
                    onClick={() => endorse(s.name)}
                  >
                    {s.endorsed ? "Endorsed" : "Endorse"}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {isOwn && certs.length > 0 && (
        <div className="card">
          <h3>Certificates</h3>
          <ul className="cert-list">
            {certs.map((c) => (
              <li key={c.id} className="cert-row">
                <span>🎓 {c.title}</span>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={async () => {
                    const url = `${window.location.origin}/verify-cert?code=${c.code}`;
                    const res = await share({
                      title: "My SkillSwap AI certificate",
                      text: `I completed “${c.title}” on SkillSwap AI 🎓`,
                      url,
                    });
                    if (res === "copied") notify("Verify link copied", "success");
                    else if (res === "failed") notify(url, "info");
                  }}
                >
                  Share certificate
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

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
