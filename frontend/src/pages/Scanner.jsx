// AI Skill Scanner (spec §3.9): paste résumé / profile text, extract strengths,
// missing skills, and next steps — and add extracted skills to your profile.

import { useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";

export default function Scanner() {
  const { notify } = useApp();
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [added, setAdded] = useState({}); // name -> kind, to disable re-adding

  async function analyze(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await api.scanSkills(text));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function addSkill(name, kind) {
    try {
      await api.addSkill({ name, kind });
      setAdded((a) => ({ ...a, [`${kind}:${name}`]: true }));
      notify(`Added "${name}" to ${kind === "have" ? "your skills" : "want to learn"}`, "success");
    } catch (err) {
      notify(err.message, "error");
    }
  }

  function SkillList({ items, kind, label }) {
    if (!items || items.length === 0) return null;
    return (
      <div className="card">
        <h3>{label}</h3>
        <div className="tags">
          {items.map((name) => {
            const key = `${kind}:${name}`;
            return (
              <span key={key} className={`tag skill-tag skill-${kind}`}>
                {name}
                <button
                  type="button"
                  className="skill-add-btn"
                  disabled={added[key]}
                  aria-label={`Add ${name} to ${kind === "have" ? "your skills" : "want to learn"}`}
                  onClick={() => addSkill(name, kind)}
                >
                  {added[key] ? "✓" : "+"}
                </button>
              </span>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <section>
      <h1>Skill Scanner</h1>
      <p className="muted">
        Paste your résumé, portfolio, or LinkedIn/GitHub summary — the AI finds your
        strengths, the skills you're missing for your goal, and what to do next.
      </p>

      <form className="card form" onSubmit={analyze}>
        <label>
          Your text
          <textarea
            rows={8}
            required
            minLength={20}
            value={text}
            placeholder="Paste résumé or profile text here…"
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        {error && <ErrorBanner message={error} />}
        <button className="btn btn-primary" disabled={busy || text.trim().length < 20} aria-busy={busy}>
          {busy ? "Analyzing…" : "Analyze"}
        </button>
      </form>

      {result && (
        <>
          {result.summary && (
            <div className="card">
              <h3>Summary</h3>
              <p>{result.summary}</p>
            </div>
          )}
          <SkillList items={result.strengths} kind="have" label="Your strengths (add to skills)" />
          <SkillList items={result.missing} kind="want" label="Skills to learn (add to wants)" />
          {result.next_steps?.length > 0 && (
            <div className="card">
              <h3>Next steps</h3>
              <ul>
                {result.next_steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}
