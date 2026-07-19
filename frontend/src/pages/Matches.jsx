// AI Skill Matching (spec §2.1): manage the skills you have / want, then find
// complementary learning partners ranked by compatibility.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

function SkillEditor({ kind, title, hint, skills, onAdd, onRemove }) {
  const [value, setValue] = useState("");
  const list = skills.filter((s) => s.kind === kind);

  async function submit(e) {
    e.preventDefault();
    const name = value.trim();
    if (!name) return;
    setValue("");
    await onAdd(name, kind);
  }

  return (
    <div className="card">
      <h3>{title}</h3>
      <p className="field-hint">{hint}</p>
      <form className="skill-add" onSubmit={submit}>
        <input
          type="text"
          value={value}
          placeholder={kind === "have" ? "e.g. Python" : "e.g. Guitar"}
          aria-label={title}
          onChange={(e) => setValue(e.target.value)}
        />
        <button type="submit" className="btn btn-primary">
          Add
        </button>
      </form>
      <div className="tags skill-tags">
        {list.length === 0 ? (
          <span className="muted">None yet.</span>
        ) : (
          list.map((s) => (
            <span key={s.id} className={`tag skill-tag skill-${kind}`}>
              {s.name}
              <button
                type="button"
                className="skill-remove"
                aria-label={`Remove ${s.name}`}
                onClick={() => onRemove(s.id)}
              >
                ×
              </button>
            </span>
          ))
        )}
      </div>
    </div>
  );
}

function MatchCard({ m }) {
  const cls =
    m.compatibility >= 70 ? "score-good" : m.compatibility >= 40 ? "score-mid" : "score-low";
  const { notify } = useApp();
  const [rating, setRating] = useState(false);
  const [rep, setRep] = useState({
    score: m.reputation_score,
    count: m.reputation_count,
  });
  const [form, setForm] = useState({
    teaching_quality: 5,
    reliability: 5,
    response_time: 5,
    completed: true,
    comment: "",
  });

  async function submitReview(e) {
    e.preventDefault();
    try {
      const res = await api.reviewReputation(m.user_id, form);
      setRep({ score: res.score, count: res.count });
      setRating(false);
      notify("Review submitted", "success");
    } catch (err) {
      notify(err.message, "error");
    }
  }

  const dims = [
    ["teaching_quality", "Teaching"],
    ["reliability", "Reliability"],
    ["response_time", "Response time"],
  ];

  return (
    <article className="card match-card">
      <div className="row-between">
        <h3>{m.name}</h3>
        <span className={`match-score ${cls}`}>{m.compatibility}%</span>
      </div>
      <p className="muted match-rep">
        {rep.score === null || rep.score === undefined
          ? "No reputation yet"
          : `Reputation ${rep.score}/100 · ${rep.count} review${rep.count === 1 ? "" : "s"}`}
      </p>
      {m.mutual && <span className="badge match-mutual">Two-way swap</span>}
      {m.goal && <p className="muted">Goal: {m.goal}</p>}
      {m.they_teach_you.length > 0 && (
        <p>
          <strong>Teaches you:</strong> {m.they_teach_you.join(", ")}
        </p>
      )}
      {m.you_teach_them.length > 0 && (
        <p>
          <strong>You teach them:</strong> {m.you_teach_them.join(", ")}
        </p>
      )}

      {rating ? (
        <form className="rate-form" onSubmit={submitReview}>
          {dims.map(([key, label]) => (
            <label key={key} className="rate-row">
              {label}
              <select
                value={form[key]}
                onChange={(e) =>
                  setForm((f) => ({ ...f, [key]: Number(e.target.value) }))
                }
              >
                {[5, 4, 3, 2, 1].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <label className="rate-check">
            <input
              type="checkbox"
              checked={form.completed}
              onChange={(e) => setForm((f) => ({ ...f, completed: e.target.checked }))}
            />
            Session completed
          </label>
          <input
            type="text"
            placeholder="Comment (optional)"
            value={form.comment}
            onChange={(e) => setForm((f) => ({ ...f, comment: e.target.value }))}
          />
          <div className="community-actions">
            <button type="submit" className="btn btn-primary">
              Submit
            </button>
            <button type="button" className="btn" onClick={() => setRating(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button type="button" className="btn rate-btn" onClick={() => setRating(true)}>
          Rate partner
        </button>
      )}
    </article>
  );
}

export default function Matches() {
  const { notify } = useApp();
  const [skills, setSkills] = useState([]);
  const [matches, setMatches] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [finding, setFinding] = useState(false);

  async function loadSkills() {
    try {
      setSkills(await api.getSkills());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  useEffect(() => {
    loadSkills();
  }, []);

  async function addSkill(name, kind) {
    try {
      await api.addSkill({ name, kind });
      setSkills(await api.getSkills());
      setMatches([]); // stale once skills change
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function removeSkill(id) {
    try {
      await api.deleteSkill(id);
      setSkills((s) => s.filter((x) => x.id !== id));
      setMatches([]);
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function findMatches() {
    setFinding(true);
    try {
      const data = await api.getMatches();
      setMatches(data);
      if (data.length === 0) notify("No matches yet — add more skills.", "info");
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setFinding(false);
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading your skills…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={loadSkills} />;

  const canMatch =
    skills.some((s) => s.kind === "have") || skills.some((s) => s.kind === "want");

  return (
    <section>
      <h1>Find your match</h1>
      <p className="muted">
        List the skills you can teach and the ones you want to learn — we'll find
        complementary partners, ranked by how well you fit.
      </p>

      <div className="grid match-editors">
        <SkillEditor
          kind="have"
          title="Skills I have"
          hint="Things you can teach others."
          skills={skills}
          onAdd={addSkill}
          onRemove={removeSkill}
        />
        <SkillEditor
          kind="want"
          title="Skills I want"
          hint="Things you want to learn."
          skills={skills}
          onAdd={addSkill}
          onRemove={removeSkill}
        />
      </div>

      <button
        className="btn btn-primary find-btn"
        onClick={findMatches}
        disabled={!canMatch || finding}
        aria-busy={finding}
      >
        {finding ? "Finding matches…" : "Find matches"}
      </button>

      {matches.length > 0 && (
        <div className="grid match-results">
          {matches.map((m) => (
            <MatchCard key={m.user_id} m={m} />
          ))}
        </div>
      )}

      {matches.length === 0 && canMatch && !finding && (
        <EmptyState
          title="Ready when you are"
          hint="Click “Find matches” to see complementary learners."
        />
      )}
    </section>
  );
}
