// Moderator dashboard (admins only, gated by ADMIN_EMAILS on the server).
// Triage reported users / messages / posts.

import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const TYPE_LABEL = { user: "User", message: "Message", post: "Post" };

export default function Admin() {
  const { user, notify } = useApp();
  const [reports, setReports] = useState([]);
  const [scope, setScope] = useState("open"); // open | all
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  const load = useCallback(async (s) => {
    setStatus("loading");
    try {
      setReports(await api.adminReports(s));
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    if (user?.is_admin) load(scope);
  }, [load, scope, user]);

  // Non-admins never see this page.
  if (user && !user.is_admin) return <Navigate to="/" replace />;

  async function resolve(id) {
    try {
      await api.resolveReport(id);
      notify("Report resolved", "success");
      setReports((r) =>
        scope === "open" ? r.filter((x) => x.id !== id) : r.map((x) => (x.id === id ? { ...x, status: "reviewed" } : x)),
      );
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (status === "loading") return <SkeletonPage cards={3} label="Loading reports…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={() => load(scope)} />;

  return (
    <section>
      <h1>Moderation</h1>
      <p className="muted">Review reported users, messages, and posts.</p>

      <div className="row-between">
        <div className="theme-options" role="tablist" aria-label="Report scope">
          {["open", "all"].map((s) => (
            <button
              key={s}
              type="button"
              className={`theme-option${scope === s ? " active" : ""}`}
              onClick={() => setScope(s)}
            >
              {s === "open" ? "Open" : "All"}
            </button>
          ))}
        </div>
      </div>

      {reports.length === 0 ? (
        <EmptyState title="Nothing to review" hint="No reports in this view." />
      ) : (
        <div className="grid">
          {reports.map((r) => (
            <div key={r.id} className="card">
              <div className="row-between">
                <span className="pill">{TYPE_LABEL[r.target_type] || r.target_type}</span>
                <span className="badge">{r.status}</span>
              </div>
              <p className="report-target">{r.target_summary}</p>
              <p className="muted">
                <strong>Reason:</strong> {r.reason}
              </p>
              <p className="field-hint">Reported by {r.reporter_name}</p>
              {r.status === "open" && (
                <button className="btn btn-primary" onClick={() => resolve(r.id)}>
                  Mark resolved
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
