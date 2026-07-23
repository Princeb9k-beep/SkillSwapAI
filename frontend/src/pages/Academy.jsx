// Skill Academy: browse paid AI-guided skill courses, enroll, and work through
// step-by-step lessons with hands-on exercises, external tools, and an AI tutor.

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";
import UpgradeNotice from "../components/UpgradeNotice.jsx";

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

// Minimal, safe markdown -> React for lesson articles (##, **bold**, - bullets).
function bold(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  );
}
function Article({ text }) {
  const lines = (text || "").split("\n");
  const blocks = [];
  let list = null;
  lines.forEach((raw, i) => {
    const line = raw.trimEnd();
    if (line.startsWith("- ") || line.startsWith("* ")) {
      list = list || [];
      list.push(<li key={`li-${i}`}>{bold(line.slice(2))}</li>);
      return;
    }
    if (list) { blocks.push(<ul key={`ul-${i}`}>{list}</ul>); list = null; }
    if (!line.trim()) return;
    if (line.startsWith("### ")) blocks.push(<h5 key={i}>{bold(line.slice(4))}</h5>);
    else if (line.startsWith("## ")) blocks.push(<h4 key={i}>{bold(line.slice(3))}</h4>);
    else if (line.startsWith("# ")) blocks.push(<h4 key={i}>{bold(line.slice(2))}</h4>);
    else blocks.push(<p key={i}>{bold(line)}</p>);
  });
  if (list) blocks.push(<ul key="ul-end">{list}</ul>);
  return <div className="article">{blocks}</div>;
}

// ---- Single lesson view ----
function LessonView({ slug, lesson, onBack }) {
  const { notify } = useApp();
  const [content, setContent] = useState(null);
  const [status, setStatus] = useState("loading");
  const [done, setDone] = useState(lesson.completed);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    api.academyContent(slug, lesson.key)
      .then((c) => { if (!cancelled) { setContent(c); setStatus("ready"); } })
      .catch((err) => { if (!cancelled) { notify(err.message, "error"); setStatus("error"); } });
    return () => { cancelled = true; };
  }, [slug, lesson.key, notify]);

  async function complete() {
    setBusy(true);
    try {
      const res = await api.academyComplete(slug, lesson.key);
      setDone(true);
      notify(`+15 XP · ${res.progress}% complete`, "success");
      (res.new_achievements || []).forEach((a) => notify(`Achievement: ${a}`, "success"));
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  const res = content?.resources;

  return (
    <div>
      <button className="btn btn-ghost" onClick={onBack}>← Back to course</button>
      <h2>{lesson.title}</h2>
      <p className="muted">{lesson.summary}</p>

      {status === "loading" && <SkeletonPage cards={1} label="Loading lesson…" />}

      {status === "ready" && content && (
        <>
          {/* Watch + read: real teaching resources for this topic */}
          {res && (
            <div className="card lesson-media">
              <h4>Learn this skill</h4>
              <div className="media-links">
                <a className="btn btn-primary" href={res.video_url} target="_blank" rel="noreferrer">
                  ▶ Watch video lessons
                </a>
                <a className="btn" href={res.read_url} target="_blank" rel="noreferrer">
                  Read the guide ↗
                </a>
                <a className="btn btn-ghost" href={res.course_video_url} target="_blank" rel="noreferrer">
                  Full course video ↗
                </a>
              </div>
            </div>
          )}

          {/* The taught article */}
          <div className="card lesson-article-card">
            <Article text={content.article} />
            {content.fallback && (
              <p className="field-hint">
                Full AI-written lessons turn on once GROQ_API_KEY is configured; the video
                and reading above teach this topic now.
              </p>
            )}
          </div>

          <div className="card">
            <h4>Step-by-step</h4>
            <ol className="lesson-steps">
              {content.steps.map((s, i) => <li key={i}>{s}</li>)}
            </ol>
          </div>

          <div className="card lesson-exercise">
            <h4>Hands-on exercise</h4>
            <p>{content.exercise}</p>
          </div>

          {content.tools?.length > 0 && (
            <div className="card">
              <h4>Tools for this lesson</h4>
              <div className="tags">
                {content.tools.map((t) => (
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
        </>
      )}
    </div>
  );
}

// ---- Path (course) detail ----
function PathDetail({ slug, onBack }) {
  const { notify, user } = useApp();
  const effTier = user?.is_admin ? "elite" : (user?.tier || "free");
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
      ) : effTier === "free" ? (
        <UpgradeNotice tier={effTier} need="pro">
          The full Skill Academy is a Pro feature. Upgrade to enroll and unlock
          every course.
        </UpgradeNotice>
      ) : (
        <div className="enroll-bar card">
          <div>
            <strong>Included with your plan</strong>
            <span className="muted"> · full lifetime access</span>
          </div>
          <button className="btn btn-primary" onClick={enroll} disabled={enrolling}>
            {enrolling ? "Enrolling…" : "Enroll now"}
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
