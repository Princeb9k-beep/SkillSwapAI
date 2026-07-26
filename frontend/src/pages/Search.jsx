// Global search: people (by name/skill), communities, and Academy courses.

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { EmptyState } from "../components/States.jsx";

export default function Search() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run(e) {
    e.preventDefault();
    const term = q.trim();
    if (term.length < 2) return;
    setBusy(true);
    setError(null);
    try {
      setResults(await api.search(term));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const empty =
    results &&
    results.people.length === 0 &&
    results.communities.length === 0 &&
    results.courses.length === 0;

  return (
    <section>
      <h1>Search</h1>
      <p className="muted">Find people to learn from, communities to join, and courses to take.</p>

      <form className="search-bar" onSubmit={run}>
        <input
          type="search"
          value={q}
          placeholder="Search people, skills, communities, courses…"
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
        <button className="btn btn-primary" disabled={busy || q.trim().length < 2}>
          {busy ? "Searching…" : "Search"}
        </button>
      </form>

      {error && <p className="field-hint">{error}</p>}

      {empty && <EmptyState title="No results" hint="Try a different word or a broader term." />}

      {results && results.people.length > 0 && (
        <>
          <h2>People</h2>
          <div className="grid">
            {results.people.map((p) => (
              <button key={p.id} type="button" className="card search-card" onClick={() => navigate(`/u/${p.id}`)}>
                <h3>{p.name}</h3>
                <p className="field-hint">Level {p.level}</p>
                {p.skills.length > 0 && (
                  <div className="tags">
                    {p.skills.map((s) => (
                      <span key={s} className="tag">{s}</span>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </div>
        </>
      )}

      {results && results.communities.length > 0 && (
        <>
          <h2>Communities</h2>
          <div className="grid">
            {results.communities.map((c) => (
              <Link key={c.id} className="card search-card" to="/community">
                <div className="row-between">
                  <h3>{c.name}</h3>
                  <span className="pill">{c.topic}</span>
                </div>
                {c.description && <p className="muted">{c.description}</p>}
              </Link>
            ))}
          </div>
        </>
      )}

      {results && results.courses.length > 0 && (
        <>
          <h2>Courses</h2>
          <div className="grid">
            {results.courses.map((c) => (
              <Link key={c.slug} className="card search-card" to="/academy">
                <div className="row-between">
                  <span className="pill">{c.category}</span>
                  <span className="muted">{c.difficulty}</span>
                </div>
                <h3>{c.title}</h3>
              </Link>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
