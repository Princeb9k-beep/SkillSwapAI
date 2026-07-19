// Resume builder: collect details, generate markdown, show + copy.

import { useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";

export default function ResumeBuilder() {
  const { notify } = useApp();
  const [form, setForm] = useState({
    name: "",
    target_role: "",
    skills: "",
    experience: "",
  });
  const [resume, setResume] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await api.buildResume({
        name: form.name,
        target_role: form.target_role,
        skills: form.skills.split(",").map((s) => s.trim()).filter(Boolean),
        experience: form.experience || null,
      });
      setResume(data.resume_markdown);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h1>Resume Builder</h1>
      <form className="card form" onSubmit={submit}>
        <label>
          Full name
          <input
            required
            type="text"
            autoComplete="name"
            placeholder="Jane Doe"
            value={form.name}
            onChange={update("name")}
          />
        </label>
        <label>
          Target role
          <input
            required
            type="text"
            autoComplete="organization-title"
            value={form.target_role}
            placeholder="Backend Engineer"
            onChange={update("target_role")}
          />
        </label>
        <label>
          Skills
          <input
            type="text"
            autoComplete="off"
            value={form.skills}
            placeholder="Python, FastAPI, SQL"
            aria-describedby="skills-hint"
            onChange={update("skills")}
          />
          <span id="skills-hint" className="field-hint">
            Separate skills with commas.
          </span>
        </label>
        <label>
          Experience notes
          <textarea rows={3} value={form.experience} onChange={update("experience")} />
        </label>
        {error && <ErrorBanner message={error} />}
        <button className="btn btn-primary" disabled={busy} aria-busy={busy}>
          {busy ? "Writing your resume…" : "Generate resume"}
        </button>
      </form>

      {resume && (
        <div className="card">
          <div className="row-between">
            <h3>Your resume</h3>
            <button
              type="button"
              className="btn"
              aria-label="Copy resume to clipboard"
              onClick={() => {
                navigator.clipboard.writeText(resume);
                notify("Copied to clipboard", "success");
              }}
            >
              Copy
            </button>
          </div>
          <pre className="resume-md">{resume}</pre>
        </div>
      )}
    </section>
  );
}
