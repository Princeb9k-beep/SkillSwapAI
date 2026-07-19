// Portfolio Builder (spec §3.2): a shareable profile assembled from the user's
// skills, verified badges, achievements, and projects. Shown inside the Career tab.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

function toMarkdown(p) {
  const lines = [`# ${p.name}`, ""];
  if (p.goal) lines.push(`**Goal:** ${p.goal}`, "");
  lines.push(`**Level ${p.level}** · ${p.xp} XP · ${p.streak}-day streak`, "");
  if (p.skills_have.length) {
    lines.push("## Skills");
    p.skills_have.forEach((s) =>
      lines.push(`- ${s.name}${s.verified ? " ✓ (verified)" : ""}`)
    );
    lines.push("");
  }
  if (p.skills_want.length) {
    lines.push("## Learning", ...p.skills_want.map((s) => `- ${s}`), "");
  }
  if (p.achievements.length) {
    lines.push("## Achievements", ...p.achievements.map((a) => `- ${a.title}`), "");
  }
  if (p.projects.length) {
    lines.push("## Projects", ...p.projects.map((pr) => `- ${pr.title}`), "");
  }
  return lines.join("\n");
}

export default function Portfolio() {
  const { notify } = useApp();
  const [p, setP] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      setP(await api.getPortfolio());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }
  useEffect(() => {
    load();
  }, []);

  if (status === "loading") return <SkeletonPage cards={2} label="Building your portfolio…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <div className="row-between">
        <h2>{p.name}</h2>
        <button
          type="button"
          className="btn"
          aria-label="Copy portfolio as markdown"
          onClick={() => {
            navigator.clipboard.writeText(toMarkdown(p));
            notify("Portfolio copied to clipboard", "success");
          }}
        >
          Copy
        </button>
      </div>
      {p.goal && <p className="muted">{p.goal}</p>}

      <div className="grid stat-grid">
        <div className="card stat">
          <span className="stat-num">{p.level}</span>
          <span className="muted">Level</span>
        </div>
        <div className="card stat">
          <span className="stat-num">{p.verified_count}</span>
          <span className="muted">Verified skills</span>
        </div>
        <div className="card stat">
          <span className="stat-num">
            {p.reputation?.score ?? "—"}
          </span>
          <span className="muted">
            Reputation
            {p.reputation?.count ? ` (${p.reputation.count})` : ""}
          </span>
        </div>
      </div>

      <div className="card">
        <h3>Skills</h3>
        {p.skills_have.length === 0 ? (
          <p className="muted">No skills yet — add them on the Matches tab.</p>
        ) : (
          <div className="tags">
            {p.skills_have.map((s) => (
              <span key={s.name} className="tag skill-tag skill-have">
                {s.name}
                {s.verified && <span className="verified-tick" title="Verified"> ✓</span>}
              </span>
            ))}
          </div>
        )}
        {p.skills_want.length > 0 && (
          <>
            <h3 className="want-head">Learning</h3>
            <div className="tags">
              {p.skills_want.map((s) => (
                <span key={s} className="tag skill-tag skill-want">
                  {s}
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      {p.achievements.length > 0 && (
        <div className="card">
          <h3>Achievements</h3>
          <div className="tags">
            {p.achievements.map((a) => (
              <span key={a.title} className="badge achievement-pill" title={a.description || ""}>
                {a.title}
              </span>
            ))}
          </div>
        </div>
      )}

      {p.projects.length > 0 && (
        <div className="card">
          <h3>Projects</h3>
          <ul>
            {p.projects.map((pr, i) => (
              <li key={i}>
                <strong>{pr.title}</strong>
                {pr.description ? ` — ${pr.description}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
