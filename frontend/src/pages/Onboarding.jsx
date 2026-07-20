// First-run onboarding wizard. Shown once (until user.onboarded is true): a
// short guided path — welcome → add skills → set a goal → done — so a brand-new
// user leaves with skills entered and a match to look at, not an empty app.

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";

function SkillInput({ kind, placeholder, skills, onAdd, onRemove }) {
  const [value, setValue] = useState("");
  const list = skills.filter((s) => s.kind === kind);
  async function submit(e) {
    e.preventDefault();
    const name = value.trim();
    if (!name) return;
    setValue("");
    await onAdd(name, kind);
  }
  return (
    <div>
      <form className="skill-add" onSubmit={submit}>
        <input
          type="text"
          value={value}
          placeholder={placeholder}
          onChange={(e) => setValue(e.target.value)}
        />
        <button type="submit" className="btn btn-primary">
          Add
        </button>
      </form>
      <div className="tags skill-tags">
        {list.length === 0 ? (
          <span className="muted">None yet.</span>
        ) : (
          list.map((s) => (
            <span key={s.id} className={`tag skill-tag skill-${kind}`}>
              {s.name}
              <button
                type="button"
                className="skill-remove"
                aria-label={`Remove ${s.name}`}
                onClick={() => onRemove(s.id)}
              >
                ×
              </button>
            </span>
          ))
        )}
      </div>
    </div>
  );
}

export default function Onboarding() {
  const { user, updateUser, notify } = useApp();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [skills, setSkills] = useState([]);
  const [goal, setGoal] = useState(user?.goal || "");
  const [income, setIncome] = useState(user?.target_income ?? "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getSkills().then(setSkills).catch(() => {});
  }, []);

  async function addSkill(name, kind) {
    try {
      await api.addSkill({ name, kind });
      setSkills(await api.getSkills());
    } catch (err) {
      notify(err.message, "error");
    }
  }
  async function removeSkill(id) {
    try {
      await api.deleteSkill(id);
      setSkills((s) => s.filter((x) => x.id !== id));
    } catch (err) {
      notify(err.message, "error");
    }
  }

  const haveCount = skills.filter((s) => s.kind === "have").length;
  const wantCount = skills.filter((s) => s.kind === "want").length;

  async function generatePlan() {
    setBusy(true);
    try {
      if (goal.trim() || income !== "") {
        await api.updateProfile({
          goal: goal.trim() || null,
          target_income: income === "" ? null : Number(income),
        });
        updateUser({ goal: goal.trim() || null, target_income: income === "" ? null : Number(income) });
      }
      if (goal.trim()) {
        await api.generateRoadmap({
          goal: goal.trim(),
          current_skills: skills.filter((s) => s.kind === "have").map((s) => s.name),
        });
      }
      setStep(3);
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function finish(dest = "/matches") {
    setBusy(true);
    try {
      await api.updateProfile({ onboarded: true });
      updateUser({ onboarded: true });
      navigate(dest);
    } catch (err) {
      // Even if the flag write fails, don't trap the user in onboarding.
      updateUser({ onboarded: true });
      navigate(dest);
    } finally {
      setBusy(false);
    }
  }

  const steps = ["Welcome", "Skills", "Goal", "Done"];

  return (
    <div className="onboarding">
      <div className="onboarding-card">
        <div className="onboarding-progress" aria-hidden="true">
          {steps.map((_, i) => (
            <span key={i} className={`onboarding-dot${i <= step ? " on" : ""}`} />
          ))}
        </div>

        {step === 0 && (
          <div className="onboarding-step">
            <h1>
              Welcome to SkillSwap<span className="brand-ai">AI</span>
            </h1>
            <p className="muted">
              Swap skills with people who want what you know — and learn what they know.
              Let's set you up in under a minute.
            </p>
            <div className="onboarding-actions">
              <button className="btn btn-primary" onClick={() => setStep(1)}>
                Get started
              </button>
              <button className="btn" onClick={() => finish("/")} disabled={busy}>
                Skip for now
              </button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="onboarding-step">
            <h2>What can you teach, and what do you want to learn?</h2>
            <p className="muted">
              Add a few of each — this is how we find complementary partners.
            </p>
            <label className="onboarding-label">Skills I can teach</label>
            <SkillInput
              kind="have"
              placeholder="e.g. Python"
              skills={skills}
              onAdd={addSkill}
              onRemove={removeSkill}
            />
            <label className="onboarding-label">Skills I want to learn</label>
            <SkillInput
              kind="want"
              placeholder="e.g. Guitar"
              skills={skills}
              onAdd={addSkill}
              onRemove={removeSkill}
            />
            <div className="onboarding-actions">
              <button
                className="btn btn-primary"
                onClick={() => setStep(2)}
                disabled={haveCount === 0 && wantCount === 0}
              >
                Continue
              </button>
              <button className="btn" onClick={() => setStep(2)}>
                Skip
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="onboarding-step">
            <h2>What's your goal?</h2>
            <p className="muted">
              Optional — we'll build a personalized learning roadmap toward it.
            </p>
            <label className="onboarding-label">Your goal</label>
            <input
              type="text"
              value={goal}
              placeholder='e.g. "Become a backend engineer"'
              onChange={(e) => setGoal(e.target.value)}
            />
            <label className="onboarding-label">Target income (optional)</label>
            <input
              type="number"
              min={0}
              value={income}
              placeholder="80000"
              onChange={(e) => setIncome(e.target.value)}
            />
            <div className="onboarding-actions">
              <button className="btn btn-primary" onClick={generatePlan} disabled={busy} aria-busy={busy}>
                {busy ? "Building…" : goal.trim() ? "Build my plan" : "Continue"}
              </button>
              <button className="btn" onClick={() => setStep(3)} disabled={busy}>
                Skip
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="onboarding-step">
            <h2>You're all set{user?.name ? `, ${user.name}` : ""}! 🎉</h2>
            <p className="muted">
              {haveCount > 0 || wantCount > 0
                ? "Let's find people to swap skills with."
                : "Add skills any time from the Matches tab to find partners."}
            </p>
            <div className="onboarding-actions">
              <button className="btn btn-primary" onClick={() => finish("/matches")} disabled={busy}>
                See my matches
              </button>
              <button className="btn" onClick={() => finish("/")} disabled={busy}>
                Go to my goal
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
