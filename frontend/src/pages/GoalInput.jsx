// Onboarding: capture the user's goal ("I want to make $80k") and create/generate.

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";

export default function GoalInput() {
  const { login, notify } = useApp();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [goal, setGoal] = useState("I want to make $80k");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await api.createUser({ email, goal });
      login(user.id);
      await api.generateRoadmap({ goal, current_skills: [] });
      notify("Your roadmap is ready!", "success");
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="hero">
      <h1>What do you want to achieve?</h1>
      <p className="muted">
        Tell us your goal and we'll build a personalized learning roadmap, daily
        lessons, project ideas, a resume, and interview practice.
      </p>
      <form className="card form" onSubmit={submit}>
        <label>
          Email
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            placeholder="you@example.com"
            aria-describedby="email-hint"
            onChange={(e) => setEmail(e.target.value)}
          />
          <span id="email-hint" className="field-hint">
            We use this only to save your progress.
          </span>
        </label>
        <label>
          Your goal
          <input
            type="text"
            required
            value={goal}
            aria-describedby="goal-hint"
            onChange={(e) => setGoal(e.target.value)}
          />
          <span id="goal-hint" className="field-hint">
            e.g. "I want to make $80k as a backend engineer"
          </span>
        </label>
        {error && <ErrorBanner message={error} />}
        <button className="btn btn-primary" disabled={busy} aria-busy={busy}>
          {busy ? "Building your plan…" : "Start learning"}
        </button>
      </form>
    </section>
  );
}
