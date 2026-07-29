// 1:1 session scheduling: see upcoming/pending sessions and propose new ones.
// A ?to=<id>&name=<n> deep link (from a profile or chat) pre-opens the form.

import { useCallback, useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const fmt = (iso) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";

export default function Sessions() {
  const { notify } = useApp();
  const [params, setParams] = useSearchParams();
  const [list, setList] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  const to = params.get("to");
  const toName = params.get("name");
  const [form, setForm] = useState({ when: "", duration: 30, skill: "", trial: false, note: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setList(await api.sessions());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function propose(e) {
    e.preventDefault();
    if (!form.when) return;
    setBusy(true);
    try {
      await api.proposeSession({
        partner_id: Number(to),
        scheduled_at: new Date(form.when).toISOString(),
        duration_min: Number(form.duration),
        skill: form.skill || null,
        is_trial: form.trial,
        note: form.note || null,
      });
      notify("Session proposed", "success");
      setParams({}, { replace: true });
      setForm({ when: "", duration: 30, skill: "", trial: false, note: "" });
      load();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function respond(id, accept) {
    try {
      await api.respondSession(id, accept);
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function cancel(id) {
    if (!window.confirm("Cancel this session?")) return;
    try {
      await api.cancelSession(id);
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading sessions…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>Sessions</h1>
      <p className="muted">Book 1:1 time with a partner — or a free 15-minute intro.</p>

      {to && (
        <form className="card form" onSubmit={propose}>
          <h3>Propose a session with {toName || `Learner #${to}`}</h3>
          <label>
            When
            <input type="datetime-local" required value={form.when} onChange={(e) => setForm((f) => ({ ...f, when: e.target.value }))} />
          </label>
          <label>
            Skill <span className="field-hint">(optional)</span>
            <input type="text" value={form.skill} placeholder="e.g. Guitar" onChange={(e) => setForm((f) => ({ ...f, skill: e.target.value }))} />
          </label>
          <label>
            Duration
            <select value={form.duration} onChange={(e) => setForm((f) => ({ ...f, duration: e.target.value }))} disabled={form.trial}>
              {[30, 45, 60, 90].map((d) => <option key={d} value={d}>{d} min</option>)}
            </select>
          </label>
          <label className="setting-row">
            <span className="setting-row-label">Free 15-min intro (trial)</span>
            <input type="checkbox" className="switch" checked={form.trial} onChange={(e) => setForm((f) => ({ ...f, trial: e.target.checked }))} />
          </label>
          <label>
            Note <span className="field-hint">(optional)</span>
            <textarea rows={2} value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} />
          </label>
          <button className="btn btn-primary" disabled={busy || !form.when}>
            {busy ? "Proposing…" : "Propose session"}
          </button>
        </form>
      )}

      <h2>Upcoming & pending</h2>
      {list.length === 0 ? (
        <EmptyState icon="📆" title="No sessions yet" hint="Book your first 1-on-1 to practice with a partner in real time.">
          <Link className="btn btn-primary" to="/matches">Find a partner</Link>
        </EmptyState>
      ) : (
        <div className="grid">
          {list.map((s) => (
            <div className="card session-card" key={s.id}>
              <div className="row-between">
                <h3>
                  <Link className="lb-name" to={`/u/${s.partner_id}`}>{s.partner_name}</Link>
                  {s.is_trial && <span className="badge">Intro</span>}
                </h3>
                <span className={`badge status-${s.status}`}>{s.status}</span>
              </div>
              <p className="muted">
                {fmt(s.scheduled_at)} · {s.duration_min} min{s.skill ? ` · ${s.skill}` : ""}
              </p>
              {s.note && <p>{s.note}</p>}
              <div className="community-actions">
                {s.status === "proposed" && s.role === "guest" && (
                  <>
                    <button className="btn btn-primary" onClick={() => respond(s.id, true)}>Confirm</button>
                    <button className="btn" onClick={() => respond(s.id, false)}>Decline</button>
                  </>
                )}
                {(s.status === "confirmed" || (s.status === "proposed" && s.role === "host")) && (
                  <button className="btn btn-danger" onClick={() => cancel(s.id)}>Cancel</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
