// Community activity feed: recent learner milestones with kudos.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const timeAgo = (iso) => {
  if (!iso) return "";
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

export default function Feed() {
  const { notify } = useApp();
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setItems(await api.feed());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function kudos(a) {
    // Optimistic toggle.
    setItems((prev) =>
      prev.map((x) =>
        x.id === a.id
          ? { ...x, kudoed: !x.kudoed, kudos: x.kudos + (x.kudoed ? -1 : 1) }
          : x,
      ),
    );
    try {
      await api.kudos(a.id);
    } catch (err) {
      notify(err.message, "error");
      load();
    }
  }

  if (status === "loading") return <SkeletonPage cards={4} label="Loading the feed…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>Activity</h1>
      <p className="muted">See what the community is achieving — and cheer them on.</p>

      {items.length === 0 ? (
        <EmptyState title="Nothing here yet" hint="Milestones show up as people verify skills, level up, and earn badges." />
      ) : (
        <div className="feed-list">
          {items.map((a) => (
            <div className="card feed-item" key={a.id}>
              <span className="feed-icon" aria-hidden="true">{a.icon}</span>
              <div className="feed-body">
                <p>
                  <Link className="lb-name" to={`/u/${a.user_id}`}>{a.name}</Link> {a.text}
                </p>
                <span className="muted feed-time">{timeAgo(a.created_at)}</span>
              </div>
              <button
                type="button"
                className={`kudos-btn${a.kudoed ? " active" : ""}`}
                onClick={() => kudos(a)}
                aria-label={a.kudoed ? "Remove kudos" : "Give kudos"}
              >
                👏 {a.kudos}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
