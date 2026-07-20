// Notification bell for the top nav: an unread badge that polls the server, and
// a dropdown panel listing recent notifications. Clicking one marks it read and
// navigates to its linked page.

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";

const POLL_MS = 45000;

function timeAgo(iso) {
  if (!iso) return "";
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function BellIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

export default function NotificationBell() {
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef(null);

  const refreshCount = useCallback(async () => {
    try {
      const { unread } = await api.notificationsUnread();
      setUnread(unread);
    } catch {
      /* offline / not authed — leave the badge as-is */
    }
  }, []);

  // Poll the unread count on mount and on an interval.
  useEffect(() => {
    refreshCount();
    const id = setInterval(refreshCount, POLL_MS);
    return () => clearInterval(id);
  }, [refreshCount]);

  // Close the panel on an outside click.
  useEffect(() => {
    if (!open) return;
    function onDown(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next) {
      setLoading(true);
      try {
        const list = await api.notifications();
        setItems(list);
        setUnread(list.filter((n) => !n.read).length);
      } catch {
        setItems([]);
      } finally {
        setLoading(false);
      }
    }
  }

  async function openItem(n) {
    setOpen(false);
    if (!n.read) {
      setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
      setUnread((u) => Math.max(0, u - 1));
      api.readNotification(n.id).catch(() => {});
    }
    if (n.link) navigate(n.link);
  }

  async function markAll() {
    setItems((prev) => prev.map((x) => ({ ...x, read: true })));
    setUnread(0);
    try {
      await api.readAllNotifications();
    } catch {
      /* best effort */
    }
  }

  return (
    <div className="bell-wrap" ref={wrapRef}>
      <button
        type="button"
        className="bell-btn"
        aria-label={`Notifications${unread ? ` (${unread} unread)` : ""}`}
        aria-haspopup="true"
        aria-expanded={open}
        onClick={toggle}
      >
        <BellIcon />
        {unread > 0 && <span className="bell-badge">{unread > 9 ? "9+" : unread}</span>}
      </button>

      {open && (
        <div className="bell-panel" role="menu" aria-label="Notifications">
          <div className="bell-panel-head">
            <strong>Notifications</strong>
            {items.some((n) => !n.read) && (
              <button type="button" className="link-btn" onClick={markAll}>
                Mark all read
              </button>
            )}
          </div>
          {loading ? (
            <p className="bell-empty muted">Loading…</p>
          ) : items.length === 0 ? (
            <p className="bell-empty muted">You're all caught up.</p>
          ) : (
            <ul className="bell-list">
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    className={`bell-item${n.read ? "" : " unread"}`}
                    onClick={() => openItem(n)}
                  >
                    <span className="bell-item-title">
                      {!n.read && <span className="bell-dot" aria-hidden="true" />}
                      {n.title}
                    </span>
                    {n.body && <span className="bell-item-body muted">{n.body}</span>}
                    <span className="bell-item-time muted">{timeAgo(n.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
