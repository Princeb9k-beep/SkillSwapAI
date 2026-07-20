// Company Partnerships (spec §3.10): browse company challenges / scholarships /
// internships and submit; register a company to post opportunities and review
// submissions.

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const KIND_LABEL = { challenge: "Challenge", scholarship: "Scholarship", internship: "Internship" };

function SubmitBox({ challenge, onDone }) {
  const { notify } = useApp();
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.submitToChallenge(challenge.id, content);
      notify("Submitted", "success");
      setOpen(false);
      setContent("");
      onDone();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  if (challenge.my_status) {
    return <span className="badge">Your submission: {challenge.my_status}</span>;
  }
  return open ? (
    <form className="submit-box" onSubmit={submit}>
      <textarea
        rows={3}
        required
        value={content}
        placeholder="Your submission (link, pitch, or answer)…"
        onChange={(e) => setContent(e.target.value)}
      />
      <div className="community-actions">
        <button className="btn btn-primary" disabled={busy || !content.trim()}>
          {busy ? "Submitting…" : "Submit"}
        </button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  ) : (
    <button className="btn btn-primary" onClick={() => setOpen(true)}>
      Apply / Submit
    </button>
  );
}

function Reviewer({ challenge }) {
  const { notify } = useApp();
  const [open, setOpen] = useState(false);
  const [subs, setSubs] = useState([]);

  async function load() {
    try {
      setSubs(await api.challengeSubmissions(challenge.id));
      setOpen(true);
    } catch (err) {
      notify(err.message, "error");
    }
  }
  async function review(id, status) {
    try {
      await api.reviewSubmission(id, status);
      setSubs((s) => s.map((x) => (x.id === id ? { ...x, status } : x)));
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (!open) {
    return (
      <button className="btn" onClick={load}>
        Review submissions ({challenge.submission_count})
      </button>
    );
  }
  return (
    <div className="reviewer">
      {subs.length === 0 ? (
        <p className="muted">No submissions yet.</p>
      ) : (
        subs.map((s) => (
          <div key={s.id} className="review-row">
            <div>
              <strong>{s.user_name}</strong> <span className="badge">{s.status}</span>
              <p className="muted">{s.content}</p>
            </div>
            <div className="community-actions">
              <button className="btn btn-primary" onClick={() => review(s.id, "accepted")}>
                Accept
              </button>
              <button className="btn btn-ghost" onClick={() => review(s.id, "rejected")}>
                Reject
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default function Partners() {
  const [opps, setOpps] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const { notify } = useApp();

  const [company, setCompany] = useState({ name: "", description: "", website: "" });
  const [postFor, setPostFor] = useState(null); // company id we're posting a challenge for
  const [challenge, setChallenge] = useState({ title: "", kind: "challenge", reward: "", deadline: "", description: "" });

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const [o, c] = await Promise.all([api.listOpportunities(), api.listCompanies()]);
      setOpps(o);
      setCompanies(c);
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function createCompany(e) {
    e.preventDefault();
    try {
      await api.createCompany(company);
      notify("Company registered", "success");
      setCompany({ name: "", description: "", website: "" });
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function postChallenge(e) {
    e.preventDefault();
    try {
      await api.postChallenge(postFor, {
        title: challenge.title,
        kind: challenge.kind,
        reward: challenge.reward || null,
        deadline: challenge.deadline || null,
        description: challenge.description || null,
      });
      notify("Opportunity posted", "success");
      setChallenge({ title: "", kind: "challenge", reward: "", deadline: "", description: "" });
      setPostFor(null);
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading opportunities…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  const myCompanies = companies.filter((c) => c.is_owner);

  return (
    <section>
      <h1>Partners</h1>
      <p className="muted">
        Company challenges, scholarships, and internships — build your portfolio and
        get noticed by employers.
      </p>

      <h3>Open opportunities</h3>
      {opps.length === 0 ? (
        <EmptyState
          title="No opportunities yet"
          hint="Register a company below to post the first one."
        />
      ) : (
        <div className="grid">
          {opps.map((ch) => (
            <div key={ch.id} className="card">
              <div className="row-between">
                <h3>{ch.title}</h3>
                <span className="pill">{KIND_LABEL[ch.kind] || ch.kind}</span>
              </div>
              <p className="muted">
                {ch.company_name}
                {ch.reward ? ` · ${ch.reward}` : ""}
                {ch.deadline ? ` · by ${ch.deadline}` : ""}
              </p>
              {ch.description && <p>{ch.description}</p>}
              <div className="match-actions">
                {ch.is_owner ? <Reviewer challenge={ch} /> : <SubmitBox challenge={ch} onDone={load} />}
              </div>
            </div>
          ))}
        </div>
      )}

      <h3 style={{ marginTop: "1.5rem" }}>For companies</h3>
      <form className="card form" onSubmit={createCompany}>
        <h4>Register a company</h4>
        <label>
          Name
          <input
            required
            value={company.name}
            placeholder="Acme Inc."
            onChange={(e) => setCompany((c) => ({ ...c, name: e.target.value }))}
          />
        </label>
        <label>
          Website
          <input
            value={company.website}
            placeholder="https://…"
            onChange={(e) => setCompany((c) => ({ ...c, website: e.target.value }))}
          />
        </label>
        <label>
          About
          <textarea
            rows={2}
            value={company.description}
            onChange={(e) => setCompany((c) => ({ ...c, description: e.target.value }))}
          />
        </label>
        <button className="btn btn-primary" disabled={!company.name.trim()}>
          Register company
        </button>
      </form>

      {myCompanies.map((c) => (
        <div key={c.id} className="card">
          <div className="row-between">
            <h4>{c.name}</h4>
            <span className="muted">{c.challenge_count} posted</span>
          </div>
          {postFor === c.id ? (
            <form className="form" onSubmit={postChallenge}>
              <label>
                Title
                <input
                  required
                  value={challenge.title}
                  onChange={(e) => setChallenge((x) => ({ ...x, title: e.target.value }))}
                />
              </label>
              <div className="grid-2">
                <label>
                  Type
                  <select
                    value={challenge.kind}
                    onChange={(e) => setChallenge((x) => ({ ...x, kind: e.target.value }))}
                  >
                    <option value="challenge">Challenge</option>
                    <option value="scholarship">Scholarship</option>
                    <option value="internship">Internship</option>
                  </select>
                </label>
                <label>
                  Reward
                  <input
                    value={challenge.reward}
                    placeholder="$500, interview, …"
                    onChange={(e) => setChallenge((x) => ({ ...x, reward: e.target.value }))}
                  />
                </label>
              </div>
              <label>
                Deadline
                <input
                  value={challenge.deadline}
                  placeholder="e.g. Aug 30"
                  onChange={(e) => setChallenge((x) => ({ ...x, deadline: e.target.value }))}
                />
              </label>
              <label>
                Description
                <textarea
                  rows={2}
                  value={challenge.description}
                  onChange={(e) => setChallenge((x) => ({ ...x, description: e.target.value }))}
                />
              </label>
              <div className="community-actions">
                <button className="btn btn-primary" disabled={!challenge.title.trim()}>
                  Post
                </button>
                <button type="button" className="btn" onClick={() => setPostFor(null)}>
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <button className="btn" onClick={() => setPostFor(c.id)}>
              Post an opportunity
            </button>
          )}
        </div>
      ))}
    </section>
  );
}
