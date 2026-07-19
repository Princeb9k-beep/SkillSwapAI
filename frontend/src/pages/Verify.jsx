// Skill verification (spec §2.5): request peer verification of your skills and
// review other people's requests. Verified skills earn a badge + a checkmark.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const STATUS_CLASS = { verified: "score-good", pending: "score-mid", rejected: "score-low" };

export default function Verify() {
  const { notify } = useApp();
  const [skills, setSkills] = useState([]);
  const [mine, setMine] = useState([]);
  const [queue, setQueue] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ skill_name: "", evidence_url: "", description: "" });

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const [sk, m, q] = await Promise.all([
        api.getSkills(),
        api.myVerifications(),
        api.verificationQueue(),
      ]);
      setSkills(sk.filter((s) => s.kind === "have"));
      setMine(m);
      setQueue(q);
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function submitRequest(e) {
    e.preventDefault();
    if (!form.skill_name) return;
    try {
      await api.requestVerification(form);
      setForm({ skill_name: "", evidence_url: "", description: "" });
      notify("Verification requested", "success");
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function vote(id, v) {
    try {
      const res = await api.reviewVerification(id, { vote: v });
      notify(`Review submitted — request is now ${res.status}.`, "success");
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading verification…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>Skill verification</h1>
      <p className="muted">
        Get your skills peer-verified for a trust badge, and help verify others.
      </p>

      <form className="card form" onSubmit={submitRequest}>
        <h3>Request verification</h3>
        <label>
          Skill
          <select
            required
            value={form.skill_name}
            onChange={(e) => setForm((f) => ({ ...f, skill_name: e.target.value }))}
          >
            <option value="">Choose a skill you can teach…</option>
            {skills.map((s) => (
              <option key={s.id} value={s.name}>
                {s.name}
                {s.verified ? " ✓ verified" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          Evidence link <span className="field-hint">(optional)</span>
          <input
            type="url"
            inputMode="url"
            placeholder="https://github.com/you/project"
            value={form.evidence_url}
            onChange={(e) => setForm((f) => ({ ...f, evidence_url: e.target.value }))}
          />
        </label>
        <label>
          Notes
          <textarea
            rows={2}
            placeholder="Briefly, how you know this skill…"
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          />
        </label>
        <button className="btn btn-primary" disabled={skills.length === 0}>
          {skills.length === 0 ? "Add a 'have' skill first" : "Request verification"}
        </button>
      </form>

      <h2>My requests</h2>
      {mine.length === 0 ? (
        <p className="muted">No requests yet.</p>
      ) : (
        <div className="grid">
          {mine.map((r) => (
            <div className="card" key={r.id}>
              <div className="row-between">
                <h3>{r.skill_name}</h3>
                <span className={`badge status-${r.status}`}>{r.status}</span>
              </div>
              <p className="muted">
                {r.approvals} approve · {r.rejections} reject
              </p>
            </div>
          ))}
        </div>
      )}

      <h2>Review peers</h2>
      {queue.length === 0 ? (
        <EmptyState title="Nothing to review" hint="Check back later for peer requests." />
      ) : (
        <div className="grid">
          {queue.map((r) => (
            <article className="card" key={r.id}>
              <h3>{r.skill_name}</h3>
              <p className="muted">Requested by {r.requester}</p>
              {r.description && <p>{r.description}</p>}
              {r.evidence_url && (
                <p>
                  <a href={r.evidence_url} target="_blank" rel="noreferrer">
                    View evidence
                  </a>
                </p>
              )}
              <div className="community-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => vote(r.id, "approve")}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => vote(r.id, "reject")}
                >
                  Reject
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
