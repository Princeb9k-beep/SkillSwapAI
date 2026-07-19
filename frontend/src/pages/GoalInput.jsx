// Onboarding for the signed-in user: capture the goal and generate a roadmap.

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";
import {
  formatCurrency,
  parseCurrency,
  goalMentionsIncome,
  extractIncome,
} from "../utils/mask.js";

export default function GoalInput() {
  const { user, updateUser, notify } = useApp();
  const navigate = useNavigate();
  const [goal, setGoal] = useState(user?.goal || "I want to make $80k");
  const [income, setIncome] = useState(
    user?.target_income ? formatCurrency(user.target_income) : ""
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Only reveal the income field when the goal is about money/salary.
  const showIncome = goalMentionsIncome(goal);

  // When it first becomes relevant and is still empty, prefill from the goal.
  useEffect(() => {
    if (showIncome && !income) {
      const amt = extractIncome(goal);
      if (amt) setIncome(formatCurrency(amt));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showIncome]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const profile = { goal };
      if (showIncome) profile.target_income = parseCurrency(income);
      await api.updateProfile(profile);
      updateUser(profile);
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
      <h1>
        {user?.name ? `Hi ${user.name}, w` : "W"}hat do you want to achieve?
      </h1>
      <p className="muted">
        Tell us your goal and we'll build a personalized learning roadmap, daily
        lessons, project ideas, a resume, and interview practice.
      </p>
      <form className="card form" onSubmit={submit}>
        <label>
          Your goal
          <input
            type="text"
            required
            value={goal}
            autoComplete="off"
            aria-describedby="goal-hint"
            onChange={(e) => setGoal(e.target.value)}
          />
          <span id="goal-hint" className="field-hint">
            e.g. "I want to make $80k as a backend engineer"
          </span>
        </label>

        {/* Shown only when the goal mentions money/salary */}
        {showIncome && (
          <label>
            Target income <span className="field-hint">(optional)</span>
            {/* Currency input mask: numeric keypad + live "$80,000" formatting */}
            <input
              type="text"
              inputMode="numeric"
              value={income}
              placeholder="$80,000"
              aria-describedby="income-hint"
              onChange={(e) => setIncome(formatCurrency(e.target.value))}
            />
            <span id="income-hint" className="field-hint">
              Your target yearly salary — we tailor the plan toward it.
            </span>
          </label>
        )}

        {error && <ErrorBanner message={error} />}
        <button className="btn btn-primary" disabled={busy} aria-busy={busy}>
          {busy ? "Building your plan…" : "Start learning"}
        </button>
      </form>
    </section>
  );
}
