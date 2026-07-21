// Skill Academy: browse paid AI-guided skill courses, enroll, and work through
// step-by-step lessons with hands-on exercises, external tools, and an AI tutor.

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const price = (cents) => `$${(cents / 100).toFixed(0)}`;

// ---- AI tutor panel for a single lesson ----
function Tutor({ slug, lessonKey }) {
  const { notify } = useApp();
  const [mode, setMode] = useState("explain");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [busy, setBusy] = useState(false);

  const labels = { explain: "Explain", hint: "Hint", review: "Review my work" };
  const placeholders = {
    explain: "Ask anything about this lesson (optional)…",
    hint: "Where are you stuck? (optional)",
    review: "Paste your work for feedback…",
  };

  async function ask() {
    setBusy(true);
    try {
      const res = await api.academyAssist(slug, lessonKey, mode, question || null);
      setAnswer(res.answer);
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="tutor card">
      <h4>AI tutor</h4>
      <div className="theme-options tutor-modes">
        {Object.keys(labels).map((m) => (
          <button
            key={m}
            type="button"
            className={`theme-option${mode === m ? " active" : ""}`}
            onClick={() => { setMode(m); setAnswer(null); }}
          >
            {labels[m]}
          </button>
        ))}
      </div>
      <textarea
        rows={mode === "review" ? 4 : 2}
        value={question}
        placeholder={placeholders[mode]}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <button className="btn btn-primary" onClick={ask} disabled={busy} aria-busy={busy}>
        {busy ? "Thinking…" : mode === "review" ? "Get feedback" : "Ask the tutor"}
      </button>
      {answer && <p className="tutor-answer">{answer}</p>}
    </div>
  );
}

// ---- Single lesson view ----
function LessonView({ slug, lesson, onBack, onCompleted }) {
  const { notify } = useApp();
  const [done, setDone] = useState(lesson.completed);
  const [busy, setBusy] = useState(false);

  async function complete() {
    setBusy(true);
    try {
      const res = await api.academyComplete(slug, lesson.key);
      setDone(true);
      onCompleted(lesson.key, res);
      notify(`+${15} XP · ${res.progress}% complete`, "success");
      (res.new_achievements || []).forEach((a) => notify(`Achievement: ${a}`, "success"));
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button className="btn btn-ghost" onClick={onBack}>← Back to course</button>
      <h2>{lesson.title}</h2>
      <p className="muted">{lesson.summary}</p>

      <div className="card">
        <h4>Step-by-step</h4>
        <ol className="lesson-steps">
          {lesson.steps.map((s, i) => <li key={i}>{s}</li>)}
        </ol>
      </div>

      <div className="card lesson-exercise">
        <h4>Hands-on exercise</h4>
        <p>{lesson.exercise}</p>
      </div>

      {lesson.tools?.length > 0 && (
        <div className="card">
          <h4>Tools for this lesson</h4>
          <div className="tags">
            {lesson.tools.map((t) => (
              <a key={t.name} className="tag tool-tag" href={t.url} target="_blank" rel="noreferrer">
                {t.name} ↗
              </a>
            ))}
          </div>
        </div>
      )}

      <Tutor slug={slug} lessonKey={lesson.key} />

      <button className="btn btn-primary complete-btn" onClick={complete} disabled={busy || done}>
        {done ? "Completed ✓" : busy ? "Saving…" : "Mark lesson complete"}
      </button>
    </div>
  );
}

// ---- Path (course) detail ----
function PathDetail({ slug, onBack }) {
  const { notify } = useApp();
  const [path, setPath] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [activeLesson, setActiveLesson] = useState(null);
  const [enrolling, setEnrolling] = useState(false);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setPath(await api.academyPath(slug));
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, [slug]);

  useEffect(() => { load(); }, [load]);

  async function enroll() {
    setEnrolling(true);
    try {
      await api.academyEnroll(slug);
      notify("Enrolled — full course unlocked", "success");
      load();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setEnrolling(false);
    }
  }

  if (status === "loading") return <SkeletonPage cards={3} label="Loading course…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  if (activeLesson) {
    return (
      <section>
        <LessonView
          slug={slug}
          lesson={activeLesson}
          onBack={() => { setActiveLesson(null); load(); }}
          onCompleted={() => {}}
        />
      </section>
    );
  }

  return (
    <section>
      <button className="btn btn-ghost" onClick={onBack}>← All skills</button>
      <div className="row-between">
        <h1>{path.title}</h1>
        <span className="pill">{path.category}</span>
      </div>
      <p className="muted">{path.summary}</p>
      <p className="field-hint">
        {path.difficulty} · {path.module_count} modules · {path.lesson_count} lessons · ~{path.hours}h
      </p>

      {path.enrolled ? (
        <div className="course-progress">
          <div className="progress-track"><div className="progress-fill" style={{ width: `${path.progress}%` }} /></div>
          <span className="muted">{path.completed}/{path.lesson_count} complete</span>
        </div>
      ) : (
        <div className="enroll-bar card">
          <div>
            <strong>{price(path.price_cents)}</strong>
            <span className="muted"> · one-time · full lifetime access</span>
          </div>
          <button className="btn btn-primary" onClick={enroll} disabled={enrolling}>
            {enrolling ? "Enrolling…" : `Enroll — ${price(path.price_cents)}`}
          </button>
        </div>
      )}

      {path.tools?.length > 0 && (
        <p className="field-hint">
          Tools: {path.tools.map((t) => t.name).join(", ")}
        </p>
      )}

      {path.modules.map((m, mi) => (
        <div key={mi} className="card module-card">
          <h3>{mi + 1}. {m.title}</h3>
          <ul className="lesson-list">
            {m.lessons.map((l) => (
              <li key={l.key}>
                <button
                  className="lesson-row"
                  disabled={l.locked}
                  onClick={() => setActiveLesson(l)}
                >
                  <span className="lesson-status">
                    {l.completed ? "✓" : l.locked ? "🔒" : "○"}
                  </span>
                  <span className="lesson-name">{l.title}</span>
                  {l.locked && <span className="muted lesson-lock">Enroll to unlock</span>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

// ---- Catalog ----
export default function Academy() {
  const [paths, setPaths] = useState([]);
  const [categories, setCategories] = useState(["All"]);
  const [category, setCategory] = useState("All");
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [active, setActive] = useState(null); // slug

  const load = useCallback(async (cat) => {
    setStatus("loading");
    try {
      setPaths(await api.academyPaths(cat));
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    api.academyCategories().then(setCategories).catch(() => {});
  }, []);
  useEffect(() => { load(category); }, [load, category]);

  if (active) return <PathDetail slug={active} onBack={() => { setActive(null); load(category); }} />;

  if (status === "loading") return <SkeletonPage cards={4} label="Loading the Academy…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={() => load(category)} />;

  return (
    <section>
      <h1>Skill Academy</h1>
      <p className="muted">
        Paid, AI-guided courses — step-by-step modules, hands-on exercises, real tools,
        and an AI tutor on every lesson.
      </p>

      <div className="category-chips">
        {categories.map((c) => (
          <button
            key={c}
            type="button"
            className={`chip${category === c ? " active" : ""}`}
            onClick={() => setCategory(c)}
          >
            {c}
          </button>
        ))}
      </div>

      {paths.length === 0 ? (
        <EmptyState title="No courses here" hint="Try another category." />
      ) : (
        <div className="grid">
          {paths.map((p) => (
            <div key={p.slug} className="card academy-card">
              <div className="row-between">
                <span className="pill">{p.category}</span>
                <span className="muted">{p.difficulty}</span>
              </div>
              <h3>{p.title}</h3>
              <p className="muted">{p.summary}</p>
              <p className="field-hint">
                {p.module_count} modules · {p.lesson_count} lessons · ~{p.hours}h
              </p>
              {p.enrolled ? (
                <div className="course-progress">
                  <div className="progress-track"><div className="progress-fill" style={{ width: `${p.progress}%` }} /></div>
                  <span className="muted">{p.progress}%</span>
                </div>
              ) : null}
              <div className="row-between academy-card-foot">
                <strong>{p.enrolled ? "Enrolled" : price(p.price_cents)}</strong>
                <button className="btn btn-primary" onClick={() => setActive(p.slug)}>
                  {p.enrolled ? "Continue" : "View course"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
