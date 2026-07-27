// Flashcards with spaced repetition: generate cards for a topic, then review the
// ones due today (reveal the answer, grade Again/Good/Easy to reschedule).

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

export default function Flashcards() {
  const { notify } = useApp();
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState(false);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setData(await api.flashcards());
      setIdx(0);
      setRevealed(false);
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function generate(e) {
    e.preventDefault();
    if (topic.trim().length < 2) return;
    setBusy(true);
    try {
      const res = await api.generateFlashcards(topic.trim());
      notify(`Added ${res.cards.length} cards`, "success");
      window.dispatchEvent(new Event("tokens:changed"));
      setTopic("");
      await load();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function grade(g) {
    const card = data.due[idx];
    try {
      await api.reviewFlashcard(card.id, g);
    } catch (err) {
      notify(err.message, "error");
      return;
    }
    setRevealed(false);
    if (idx + 1 >= data.due.length) {
      notify("Review complete 🎉", "success");
      load();
    } else {
      setIdx((i) => i + 1);
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading flashcards…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  const card = data.due[idx];

  return (
    <section>
      <h1>Flashcards</h1>
      <p className="muted">
        Turn what you learn into spaced-repetition cards. {data.total} total ·{" "}
        {data.due_count} due today.
      </p>

      <form className="card form flashcard-gen" onSubmit={generate}>
        <label>
          Make cards for a topic
          <input
            type="text"
            value={topic}
            placeholder="e.g. Python decorators, React hooks…"
            onChange={(e) => setTopic(e.target.value)}
          />
        </label>
        <button className="btn btn-primary" disabled={busy || topic.trim().length < 2}>
          {busy ? "Generating…" : "Generate cards"}
        </button>
      </form>

      {data.due.length === 0 ? (
        <EmptyState title="Nothing due 🎉" hint="You're all caught up — generate a new set or come back tomorrow." />
      ) : (
        <div className="card flashcard" onClick={() => !revealed && setRevealed(true)}>
          <span className="muted flashcard-progress">
            Card {idx + 1} of {data.due.length} · {card.topic}
          </span>
          <div className="flashcard-front">{card.front}</div>
          {revealed ? (
            <>
              <hr className="flashcard-divider" />
              <div className="flashcard-back">{card.back}</div>
              <div className="flashcard-grades">
                <button type="button" className="btn" onClick={() => grade("again")}>Again</button>
                <button type="button" className="btn" onClick={() => grade("good")}>Good</button>
                <button type="button" className="btn btn-primary" onClick={() => grade("easy")}>Easy</button>
              </div>
            </>
          ) : (
            <button type="button" className="btn" onClick={() => setRevealed(true)}>
              Show answer
            </button>
          )}
        </div>
      )}
    </section>
  );
}
