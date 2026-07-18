// Progress dashboard: shows the roadmap milestones + suggested projects.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { LoadingState, ErrorBanner, EmptyState } from "../components/States.jsx";

export default function Dashboard() {
  const [roadmap, setRoadmap] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const data = await api.getRoadmap();
      setRoadmap(data);
      setStatus("ready");
    } catch (err) {
      // 404 == no roadmap yet; anything else is a real error.
      if (/no roadmap/i.test(err.message)) setStatus("empty");
      else {
        setError(err.message);
        setStatus("error");
      }
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (status === "loading") return <LoadingState label="Loading your roadmap…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;
  if (status === "empty")
    return (
      <EmptyState
        title="No roadmap yet"
        hint="Create one from the Goal tab to see your milestones here."
      />
    );

  const milestones = roadmap?.content?.milestones || [];

  return (
    <section>
      <h1>Your Roadmap</h1>
      <p className="muted">{roadmap?.content?.summary}</p>
      <div className="grid">
        {milestones.map((m, i) => (
          <article className="card milestone" key={i}>
            <span className="badge">Step {i + 1}</span>
            <h3>{m.title}</h3>
            {m.weeks && <p className="muted">~{m.weeks} weeks</p>}
            <ul>
              {(m.steps || []).map((s, j) => (
                <li key={j}>{s}</li>
              ))}
            </ul>
            {m.skills?.length > 0 && (
              <div className="tags">
                {m.skills.map((s, k) => (
                  <span className="tag" key={k}>
                    {s}
                  </span>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
      <p className="muted">
        Keep going with your <Link to="/lessons">daily lessons →</Link>
      </p>
    </section>
  );
}
