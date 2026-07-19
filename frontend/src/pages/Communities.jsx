// Communities (spec §3.4): topic-based groups with membership + posts.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

function CreateForm({ onCreated }) {
  const { notify } = useApp();
  const [form, setForm] = useState({ name: "", topic: "Coding", description: "" });
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.createCommunity(form);
      setForm({ name: "", topic: "Coding", description: "" });
      notify("Community created", "success");
      onCreated();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h3>Start a community</h3>
      <label>
        Name
        <input
          required
          minLength={2}
          value={form.name}
          placeholder="Python Nerds"
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        />
      </label>
      <label>
        Topic
        <select
          value={form.topic}
          onChange={(e) => setForm((f) => ({ ...f, topic: e.target.value }))}
        >
          {["Coding", "Music", "Sports", "Languages", "Art", "Other"].map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      </label>
      <label>
        Description
        <textarea
          rows={2}
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
        />
      </label>
      <button className="btn btn-primary" disabled={busy} aria-busy={busy}>
        {busy ? "Creating…" : "Create"}
      </button>
    </form>
  );
}

function CommunityDetail({ id, onBack }) {
  const { notify } = useApp();
  const [data, setData] = useState(null);
  const [body, setBody] = useState("");
  const [status, setStatus] = useState("loading");

  async function load() {
    setStatus("loading");
    try {
      setData(await api.getCommunity(id));
      setStatus("ready");
    } catch (err) {
      notify(err.message, "error");
      setStatus("error");
    }
  }
  useEffect(() => {
    load();
  }, [id]);

  async function post(e) {
    e.preventDefault();
    if (!body.trim()) return;
    try {
      await api.postToCommunity(id, body.trim());
      setBody("");
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function remove(postId) {
    try {
      await api.deletePost(id, postId);
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading community…" />;
  if (status !== "ready") return null;

  return (
    <section>
      <button type="button" className="btn back-btn" onClick={onBack}>
        ‹ All communities
      </button>
      <h1>{data.name}</h1>
      <p className="muted">
        <span className="badge">{data.topic}</span> {data.description}
      </p>

      <form className="card form post-composer" onSubmit={post}>
        <label>
          Share something
          <textarea
            rows={2}
            value={body}
            placeholder="Ask a question or share progress…"
            onChange={(e) => setBody(e.target.value)}
          />
        </label>
        <button className="btn btn-primary" disabled={!body.trim()}>
          Post
        </button>
      </form>

      {data.posts.length === 0 ? (
        <EmptyState title="No posts yet" hint="Be the first to post." />
      ) : (
        <div className="posts">
          {data.posts.map((p) => (
            <article className="card post" key={p.id}>
              <div className="row-between">
                <strong>{p.user_name}</strong>
                {p.can_delete && (
                  <button
                    type="button"
                    className="btn btn-danger post-del"
                    aria-label="Delete post"
                    onClick={() => remove(p.id)}
                  >
                    Delete
                  </button>
                )}
              </div>
              <p>{p.body}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default function Communities() {
  const { notify } = useApp();
  const [list, setList] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      setList(await api.getCommunities());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function toggleJoin(c) {
    try {
      if (c.joined) await api.leaveCommunity(c.id);
      else await api.joinCommunity(c.id);
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (selected)
    return <CommunityDetail id={selected} onBack={() => { setSelected(null); load(); }} />;

  if (status === "loading") return <SkeletonPage cards={3} label="Loading communities…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>Communities</h1>
      <p className="muted">Join topic-based groups to learn together.</p>

      <CreateForm onCreated={load} />

      {list.length === 0 ? (
        <EmptyState title="No communities yet" hint="Create the first one above." />
      ) : (
        <div className="grid">
          {list.map((c) => (
            <article className="card community-card" key={c.id}>
              <span className="badge">{c.topic}</span>
              <h3>{c.name}</h3>
              {c.description && <p className="muted">{c.description}</p>}
              <p className="muted community-meta">
                {c.member_count} member{c.member_count === 1 ? "" : "s"} ·{" "}
                {c.post_count} post{c.post_count === 1 ? "" : "s"}
              </p>
              <div className="community-actions">
                <button type="button" className="btn" onClick={() => setSelected(c.id)}>
                  Open
                </button>
                <button
                  type="button"
                  className={`btn ${c.joined ? "" : "btn-primary"}`}
                  onClick={() => toggleJoin(c)}
                >
                  {c.joined ? "Leave" : "Join"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
