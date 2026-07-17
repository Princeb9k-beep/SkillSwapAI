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
          <input required value={form.name} onChange={update("name")} />
        </label>
        <label>
          Target role
          <input
            required
            value={form.target_role}
            placeholder="Backend Engineer"
            onChange={update("target_role")}
          />
        </label>
        <label>
          Skills (comma-separated)
          <input
            value={form.skills}
            placeholder="Python, FastAPI, SQL"
            onChange={update("skills")}
          />
        </label>
        <label>
          Experience notes
          <textarea rows={3} value={form.experience} onChange={update("experience")} />
        </label>
        {error && <ErrorBanner message={error} />}
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Writing your resume…" : "Generate resume"}
        </button>
      </form>

      {resume && (
        <div className="card">
          <div className="row-between">
            <h3>Your resume</h3>
            <button
              className="btn"
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
