// AI Coach (spec §2.4): a chat with a Groq-backed learning mentor.

import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const SUGGESTIONS = [
  "What should I learn first for my goal?",
  "Give me a study plan for this week.",
  "Explain a concept I'm stuck on.",
];

export default function Coach() {
  const { notify } = useApp();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      setMessages(await api.coachHistory());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }
  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || sending) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setSending(true);
    try {
      const res = await api.coachChat(message);
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
    } catch (err) {
      notify(err.message, "error");
      setMessages((m) => m.slice(0, -1)); // roll back the optimistic user msg
      setInput(message);
    } finally {
      setSending(false);
    }
  }

  async function clear() {
    try {
      await api.clearCoach();
      setMessages([]);
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading your coach…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section className="coach">
      <div className="row-between">
        <h1>AI Coach</h1>
        {messages.length > 0 && (
          <button type="button" className="btn" onClick={clear}>
            Clear
          </button>
        )}
      </div>

      <div className="coach-thread" aria-live="polite">
        {messages.length === 0 ? (
          <div className="coach-empty">
            <p className="muted">
              Ask your coach anything — study plans, feedback, or a topic you're
              stuck on.
            </p>
            <div className="coach-suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="btn chip" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
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

      <form
        className="coach-input"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          type="text"
          value={input}
          placeholder="Ask your coach…"
          aria-label="Message the coach"
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="btn btn-primary" disabled={!input.trim() || sending} aria-busy={sending}>
          Send
        </button>
      </form>
    </section>
  );
}
