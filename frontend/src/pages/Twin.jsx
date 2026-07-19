// AI Twin (spec §4): train a twin of your teaching style, then learn from other
// users' twins — chat in their voice and get quizzes in their style.

import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

function TrainTwin({ twin, onTrained }) {
  const { notify } = useApp();
  const [samples, setSamples] = useState(twin.style_prompt || "");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.trainTwin(samples);
      notify("Your AI Twin is trained", "success");
      onTrained();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h3>Your AI Twin {twin.trained && <span className="badge status-completed">trained</span>}</h3>
      <p className="field-hint">
        Paste a few examples of how you explain things (or describe your teaching
        style). Partners can then learn from your twin when you're offline.
      </p>
      <label>
        Teaching samples / style
        <textarea
          rows={5}
          required
          minLength={20}
          value={samples}
          placeholder="e.g. I explain with real-world analogies, start simple, and always end with a small exercise…"
          onChange={(e) => setSamples(e.target.value)}
        />
      </label>
      <button className="btn btn-primary" disabled={busy || samples.trim().length < 20} aria-busy={busy}>
        {busy ? "Training…" : twin.trained ? "Retrain twin" : "Train my twin"}
      </button>
    </form>
  );
}

function TwinChat({ owner, onBack }) {
  const { notify } = useApp();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [quiz, setQuiz] = useState(null);
  const [topic, setTopic] = useState("");
  const [revealed, setRevealed] = useState({});
  const endRef = useRef(null);

  useEffect(() => {
    api.twinHistory(owner.owner_id).then(setMessages).catch(() => {});
  }, [owner.owner_id]);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function send(e) {
    e.preventDefault();
    const message = input.trim();
    if (!message || sending) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setSending(true);
    try {
      const res = await api.twinChat(owner.owner_id, message);
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setSending(false);
    }
  }

  async function makeQuiz(e) {
    e.preventDefault();
    if (!topic.trim()) return;
    try {
      const res = await api.twinQuiz(owner.owner_id, topic.trim());
      setQuiz(res.questions);
      setRevealed({});
    } catch (err) {
      notify(err.message, "error");
    }
  }

  return (
    <section>
      <button type="button" className="btn back-btn" onClick={onBack}>
        ‹ All twins
      </button>
      <h1>{owner.name}'s Twin</h1>
      {owner.skills.length > 0 && (
        <div className="tags">
          {owner.skills.map((s) => (
            <span key={s} className="tag skill-tag skill-have">
              {s}
            </span>
          ))}
        </div>
      )}

      <div className="coach-thread" aria-live="polite">
        {messages.length === 0 ? (
          <p className="muted coach-empty">
            Ask {owner.name}'s twin anything about what they teach.
          </p>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`bubble bubble-${m.role}`}>
              {m.content}
            </div>
          ))
        )}
        {sending && <div className="bubble bubble-assistant bubble-typing">…</div>}
        <div ref={endRef} />
      </div>

      <form className="coach-input" onSubmit={send}>
        <input
          type="text"
          value={input}
          placeholder={`Ask ${owner.name}'s twin…`}
          aria-label="Message the twin"
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="btn btn-primary" disabled={!input.trim() || sending}>
          Send
        </button>
      </form>

      <form className="card form twin-quiz-form" onSubmit={makeQuiz}>
        <h3>Quiz me in {owner.name}'s style</h3>
        <div className="skill-add">
          <input
            type="text"
            value={topic}
            placeholder="Topic (e.g. chords)"
            aria-label="Quiz topic"
            onChange={(e) => setTopic(e.target.value)}
          />
          <button className="btn btn-primary" disabled={!topic.trim()}>
            Quiz me
          </button>
        </div>
        {quiz && (
          <ol className="twin-quiz">
            {quiz.map((q, i) => (
              <li key={i}>
                <strong>{q.question}</strong>
                {revealed[i] ? (
                  <p className="muted">{q.answer}</p>
                ) : (
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => setRevealed((r) => ({ ...r, [i]: true }))}
                  >
                    Show answer
                  </button>
                )}
              </li>
            ))}
          </ol>
        )}
      </form>
    </section>
  );
}

export default function Twin() {
  const [twin, setTwin] = useState(null);
  const [available, setAvailable] = useState([]);
  const [selected, setSelected] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const [me, avail] = await Promise.all([api.myTwin(), api.availableTwins()]);
      setTwin(me);
      setAvailable(avail);
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }
  useEffect(() => {
    load();
  }, []);

  if (selected)
    return <TwinChat owner={selected} onBack={() => setSelected(null)} />;
  if (status === "loading") return <SkeletonPage cards={2} label="Loading AI Twin…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>AI Twin</h1>
      <p className="muted">
        Train a twin of your teaching style so partners can keep learning from you —
        and learn from theirs anytime.
      </p>

      <TrainTwin twin={twin} onTrained={load} />

      <h2>Learn from a twin</h2>
      {available.length === 0 ? (
        <EmptyState
          title="No trained twins yet"
          hint="When other learners train their twin, they'll show up here."
        />
      ) : (
        <div className="grid">
          {available.map((t) => (
            <article className="card" key={t.owner_id}>
              <h3>{t.name}</h3>
              {t.skills.length > 0 && (
                <div className="tags">
                  {t.skills.slice(0, 6).map((s) => (
                    <span key={s} className="tag">
                      {s}
                    </span>
                  ))}
                </div>
              )}
              <button
                type="button"
                className="btn btn-primary twin-open"
                onClick={() => setSelected(t)}
              >
                Learn from {t.name}'s twin
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
