// Direct messaging (spec §2.3). A two-pane view: conversation threads on the
// left, the open conversation on the right. A `?to=<id>&name=<n>` query (used by
// the "Message" button on Matches) opens a conversation directly.

import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

export default function Messages() {
  const { notify } = useApp();
  const [params, setParams] = useSearchParams();
  const [threads, setThreads] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  const [active, setActive] = useState(null); // { partner_id, partner_name }
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const logRef = useRef(null);

  const loadThreads = useCallback(async () => {
    try {
      setThreads(await api.messageThreads());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  const openConversation = useCallback(async (partnerId, fallbackName) => {
    try {
      const data = await api.conversation(partnerId);
      setActive({ partner_id: partnerId, partner_name: data.partner_name || fallbackName });
      setMessages(data.messages);
    } catch (err) {
      notify(err.message, "error");
    }
  }, [notify]);

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  // Honor a deep link from Matches ("Message" button), once.
  const to = params.get("to");
  const toName = params.get("name");
  useEffect(() => {
    if (to) {
      openConversation(Number(to), toName || `Learner #${to}`);
      setParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [to]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages]);

  async function send(e) {
    e.preventDefault();
    const body = draft.trim();
    if (!body || !active) return;
    setSending(true);
    try {
      const msg = await api.sendMessage(active.partner_id, body);
      setMessages((m) => [...m, msg]);
      setDraft("");
      loadThreads(); // refresh preview/order
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setSending(false);
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading messages…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={loadThreads} />;

  return (
    <section>
      <h1>Messages</h1>
      <p className="muted">
        Chat with your learning partners. Start a conversation from a match, or pick up
        where you left off.
      </p>

      <div className="messages-layout">
        <aside className="messages-threads">
          {threads.length === 0 ? (
            <EmptyState
              title="No conversations yet"
              hint="Find a partner and say hello to start chatting."
            >
              <Link className="btn btn-primary" to="/matches">
                Find matches
              </Link>
            </EmptyState>
          ) : (
            threads.map((t) => (
              <button
                key={t.partner_id}
                type="button"
                className={`thread${active?.partner_id === t.partner_id ? " active" : ""}`}
                onClick={() => openConversation(t.partner_id, t.partner_name)}
              >
                <span className="thread-top">
                  <strong>{t.partner_name}</strong>
                  {t.unread > 0 && <span className="thread-badge">{t.unread}</span>}
                </span>
                <span className="thread-preview muted">
                  {t.last_mine ? "You: " : ""}
                  {t.last_message}
                </span>
              </button>
            ))
          )}
        </aside>

        <div className="messages-conversation card">
          {!active ? (
            <EmptyState title="Pick a conversation" hint="Select a thread to view messages." />
          ) : (
            <>
              <h3 className="conversation-title">{active.partner_name}</h3>
              <div className="conversation-log" ref={logRef}>
                {messages.length === 0 ? (
                  <p className="muted">No messages yet — say hello.</p>
                ) : (
                  messages.map((m) => (
                    <div
                      key={m.id}
                      className={`bubble${m.mine ? " bubble-mine" : ""}`}
                    >
                      {m.body}
                    </div>
                  ))
                )}
              </div>
              <form className="conversation-input" onSubmit={send}>
                <input
                  value={draft}
                  placeholder="Type a message…"
                  onChange={(e) => setDraft(e.target.value)}
                />
                <button className="btn btn-primary" disabled={sending || !draft.trim()}>
                  Send
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
