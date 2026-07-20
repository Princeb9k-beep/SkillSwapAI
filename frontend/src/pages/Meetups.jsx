// Local Meetups (spec §3.5): browse and RSVP to opt-in study meetups, or host one.

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

function fmt(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// Default the datetime-local input to a sensible near-future slot.
function defaultWhen() {
  const d = new Date(Date.now() + 24 * 3600 * 1000);
  d.setMinutes(0, 0, 0);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function Meetups() {
  const { user, notify } = useApp();
  const [meetups, setMeetups] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [form, setForm] = useState({
    title: "",
    location: "Online",
    starts_at: defaultWhen(),
    capacity: "",
    description: "",
  });
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setMeetups(await api.listMeetups());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function create(e) {
    e.preventDefault();
    setCreating(true);
    try {
      await api.createMeetup({
        title: form.title,
        location: form.location,
        starts_at: new Date(form.starts_at).toISOString(),
        capacity: form.capacity === "" ? 0 : Number(form.capacity),
        description: form.description || null,
      });
      notify("Meetup created", "success");
      setForm((f) => ({ ...f, title: "", description: "" }));
      load();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setCreating(false);
    }
  }

  async function toggleRsvp(m) {
    try {
      if (m.joined) await api.cancelMeetup(m.id);
      else await api.rsvpMeetup(m.id);
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function remove(m) {
    try {
      await api.deleteMeetup(m.id);
      notify("Meetup deleted", "info");
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading meetups…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>Meetups</h1>
      <p className="muted">
        Learn together in person or online — study groups, hackathons, practice
        sessions. Opt-in and public.
      </p>

      <form className="card form" onSubmit={create}>
        <h3>Host a meetup</h3>
        <label>
          Title
          <input
            required
            maxLength={160}
            value={form.title}
            placeholder="e.g. Weekend Python study group"
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
          />
        </label>
        <div className="grid-2">
          <label>
            Location
            <input
              value={form.location}
              placeholder="City, venue, or Online"
              onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
            />
          </label>
          <label>
            When
            <input
              type="datetime-local"
              required
              value={form.starts_at}
              onChange={(e) => setForm((f) => ({ ...f, starts_at: e.target.value }))}
            />
          </label>
        </div>
        <label>
          Capacity (0 = unlimited)
          <input
            type="number"
            min={0}
            value={form.capacity}
            placeholder="0"
            onChange={(e) => setForm((f) => ({ ...f, capacity: e.target.value }))}
          />
        </label>
        <label>
          Description
          <textarea
            rows={2}
            value={form.description}
            placeholder="What you'll do, who should come…"
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          />
        </label>
        <button className="btn btn-primary" disabled={creating || !form.title.trim()}>
          {creating ? "Creating…" : "Create meetup"}
        </button>
      </form>

      <h3>Upcoming</h3>
      {meetups.length === 0 ? (
        <EmptyState title="No upcoming meetups" hint="Host the first one above." />
      ) : (
        <div className="grid">
          {meetups.map((m) => (
            <div key={m.id} className="card">
              <div className="row-between">
                <h3>{m.title}</h3>
                <span className="pill">{m.location}</span>
              </div>
              <p className="muted">
                {fmt(m.starts_at)} · {m.attendee_count}
                {m.capacity ? ` / ${m.capacity}` : ""} going · Host {m.host_name}
              </p>
              {m.description && <p>{m.description}</p>}
              <div className="match-actions">
                <button
                  className={`btn ${m.joined ? "" : "btn-primary"}`}
                  onClick={() => toggleRsvp(m)}
                  disabled={!m.joined && m.is_full}
                >
                  {m.joined ? "Cancel RSVP" : m.is_full ? "Full" : "RSVP"}
                </button>
                {m.host_id === user?.id && (
                  <button className="btn btn-ghost" onClick={() => remove(m)}>
                    Delete
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
