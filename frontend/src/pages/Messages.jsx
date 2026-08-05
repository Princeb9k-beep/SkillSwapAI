// Direct messaging (spec §2.3). A two-pane view: conversation threads on the
// left, the open conversation on the right. A `?to=<id>&name=<n>` query (used by
// the "Message" button on Matches) opens a conversation directly.

import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";
import { onRealtime, sendRealtime } from "../realtime.js";

const REACTIONS = ["👍", "❤️", "😂", "🎉", "👏"];

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
  const [online, setOnline] = useState(() => new Set());
  const [partnerTyping, setPartnerTyping] = useState(false);
  const [icebreakers, setIcebreakers] = useState([]);
  const [loadingIce, setLoadingIce] = useState(false);
  const logRef = useRef(null);
  const typingSentAt = useRef(0);
  const typingClearTimer = useRef(null);

  const loadThreads = useCallback(async () => {
    try {
      const data = await api.messageThreads();
      setThreads(data);
      setOnline((prev) => {
        const next = new Set(prev);
        data.forEach((t) => (t.online ? next.add(t.partner_id) : next.delete(t.partner_id)));
        return next;
      });
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
      setIcebreakers([]);
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

  // Live updates: messages, presence, typing, and reactions.
  useEffect(() => {
    const off = onRealtime((e) => {
      if (e.type === "message") {
        loadThreads();
        const partnerId = e.data.to_id ?? e.data.from_id;
        if (active && active.partner_id === partnerId) {
          setPartnerTyping(false);
          openConversation(partnerId, active.partner_name);
        }
      } else if (e.type === "presence") {
        setOnline((prev) => {
          const next = new Set(prev);
          if (e.online) next.add(e.user_id);
          else next.delete(e.user_id);
          return next;
        });
      } else if (e.type === "typing") {
        if (active && e.from_id === active.partner_id) {
          setPartnerTyping(true);
          clearTimeout(typingClearTimer.current);
          typingClearTimer.current = setTimeout(() => setPartnerTyping(false), 3500);
        }
      } else if (e.type === "reaction") {
        setMessages((prev) =>
          prev.map((m) => (m.id === e.data.id ? { ...m, reaction: e.data.reaction } : m)),
        );
      }
    });
    return off;
  }, [active, loadThreads, openConversation]);

  function onDraftChange(value) {
    setDraft(value);
    // Throttle typing signals to the partner to once every ~2s.
    const now = Date.now();
    if (active && now - typingSentAt.current > 2000) {
      typingSentAt.current = now;
      sendRealtime({ type: "typing", to: active.partner_id });
    }
  }

  async function suggestIcebreakers() {
    if (!active) return;
    setLoadingIce(true);
    try {
      const res = await api.icebreakers(active.partner_id);
      setIcebreakers(res.icebreakers || []);
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setLoadingIce(false);
    }
  }

  async function setReaction(messageId, emoji) {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, reaction: m.reaction === emoji ? null : emoji } : m)),
    );
    try {
      const cur = messages.find((m) => m.id === messageId);
      await api.reactMessage(messageId, cur?.reaction === emoji ? null : emoji);
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function blockPartner() {
    if (!active) return;
    if (!window.confirm(`Block ${active.partner_name}? They can't message you and won't appear in your matches.`)) return;
    try {
      await api.blockUser(active.partner_id);
      notify(`${active.partner_name} blocked`, "info");
      setActive(null);
      setMessages([]);
      loadThreads();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function reportPartner() {
    if (!active) return;
    const reason = window.prompt(`Report ${active.partner_name}? Tell us what's wrong:`);
    if (!reason || !reason.trim()) return;
    try {
      await api.reportContent("user", active.partner_id, reason.trim());
      notify("Report submitted", "success");
    } catch (err) {
      notify(err.message, "error");
    }
  }

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
              icon="chat"
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
                  <strong>
                    {online.has(t.partner_id) && <span className="online-dot" aria-label="online" />}
                    {t.partner_name}
                  </strong>
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
            <EmptyState icon="inbox" title="Pick a conversation" hint="Select a thread to view messages." />
          ) : (
            <>
              <div className="row-between conversation-head">
                <h3 className="conversation-title">
                  {online.has(active.partner_id) && <span className="online-dot" aria-label="online" />}
                  {active.partner_name}
                  <span className="conversation-presence muted">
                    {partnerTyping ? "typing…" : online.has(active.partner_id) ? "online" : "offline"}
                  </span>
                </h3>
                <div className="conversation-mod">
                  <Link
                    className="link-btn"
                    to={`/sessions?to=${active.partner_id}&name=${encodeURIComponent(active.partner_name)}`}
                  >
                    Schedule
                  </Link>
                  <button type="button" className="link-btn" onClick={reportPartner}>
                    Report
                  </button>
                  <button type="button" className="link-btn" onClick={blockPartner}>
                    Block
                  </button>
                </div>
              </div>
              <div className="conversation-log" ref={logRef}>
                {messages.length === 0 ? (
                  <div className="convo-empty">
                    <p className="muted">No messages yet — say hello.</p>
                    {icebreakers.length === 0 ? (
                      <button
                        type="button"
                        className="btn"
                        onClick={suggestIcebreakers}
                        disabled={loadingIce}
                      >
                        {loadingIce ? "Thinking…" : "Suggest openers"}
                      </button>
                    ) : (
                      <div className="icebreakers">
                        {icebreakers.map((ib, i) => (
                          <button
                            key={i}
                            type="button"
                            className="icebreaker-chip"
                            onClick={() => setDraft(ib)}
                          >
                            {ib}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  messages.map((m) => (
                    <div key={m.id} className={`bubble-row${m.mine ? " bubble-row-mine" : ""}`}>
                      <div className={`bubble${m.mine ? " bubble-mine" : ""}`}>
                        {m.body}
                        {m.reaction && <span className="bubble-reaction">{m.reaction}</span>}
                      </div>
                      <div className="bubble-react-bar">
                        {REACTIONS.map((emoji) => (
                          <button
                            key={emoji}
                            type="button"
                            className={`react-emoji${m.reaction === emoji ? " active" : ""}`}
                            onClick={() => setReaction(m.id, emoji)}
                            aria-label={`React ${emoji}`}
                          >
                            {emoji}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>
              <form className="conversation-input" onSubmit={send}>
                <input
                  value={draft}
                  placeholder="Type a message…"
                  onChange={(e) => onDraftChange(e.target.value)}
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
