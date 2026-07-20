// Settings: profile, appearance (theme), notification preferences, and account.
// The Sign out button lives here, pinned to the bottom of the page.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { getTheme, setTheme, THEMES } from "../theme.js";

const PREFS_KEY = "skillswap_prefs";
const DEFAULT_PREFS = {
  challengeReminders: true,
  messageAlerts: true,
  productUpdates: false,
};

function loadPrefs() {
  try {
    return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem(PREFS_KEY) || "{}") };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

const THEME_LABELS = { system: "System", light: "Light", dark: "Dark" };

function Toggle({ label, hint, checked, onChange }) {
  return (
    <label className="setting-row">
      <span className="setting-row-text">
        <span className="setting-row-label">{label}</span>
        {hint && <span className="setting-row-hint muted">{hint}</span>}
      </span>
      <input
        type="checkbox"
        className="switch"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
    </label>
  );
}

export default function Settings() {
  const { user, logout, updateUser, notify } = useApp();

  const [form, setForm] = useState({
    name: user?.name || "",
    goal: user?.goal || "",
    target_income: user?.target_income ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [theme, setThemeState] = useState(getTheme());
  const [prefs, setPrefs] = useState(loadPrefs);

  useEffect(() => {
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  }, [prefs]);

  async function saveProfile(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim() || null,
        goal: form.goal.trim() || null,
        target_income:
          form.target_income === "" ? null : Number(form.target_income),
      };
      const updated = await api.updateProfile(payload);
      updateUser(updated);
      notify("Profile saved", "success");
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setSaving(false);
    }
  }

  function chooseTheme(pref) {
    setThemeState(setTheme(pref));
  }

  function signOut() {
    logout();
    notify("Signed out", "info");
  }

  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : null;

  return (
    <section className="settings">
      <h1>Settings</h1>
      <p className="muted">Manage your profile, appearance, and account.</p>

      {/* Profile */}
      <form className="card settings-card" onSubmit={saveProfile}>
        <h3>Profile</h3>
        <label>
          Name
          <input
            type="text"
            maxLength={255}
            value={form.name}
            placeholder="Your name"
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
        </label>
        <label>
          Email
          <input type="email" value={user?.email || ""} disabled readOnly />
          <span className="field-hint">Email can't be changed.</span>
        </label>
        <label>
          Goal
          <input
            type="text"
            value={form.goal}
            placeholder='e.g. "Make $80k as a backend engineer"'
            onChange={(e) => setForm((f) => ({ ...f, goal: e.target.value }))}
          />
        </label>
        <label>
          Target income
          <input
            type="number"
            min={0}
            value={form.target_income}
            placeholder="80000"
            onChange={(e) => setForm((f) => ({ ...f, target_income: e.target.value }))}
          />
        </label>
        <button className="btn btn-primary" disabled={saving} aria-busy={saving}>
          {saving ? "Saving…" : "Save profile"}
        </button>
      </form>

      {/* Appearance */}
      <div className="card settings-card">
        <h3>Appearance</h3>
        <p className="field-hint">Choose how SkillSwap AI looks.</p>
        <div className="theme-options">
          {THEMES.map((t) => (
            <button
              key={t}
              type="button"
              className={`theme-option${theme === t ? " active" : ""}`}
              aria-pressed={theme === t}
              onClick={() => chooseTheme(t)}
            >
              {THEME_LABELS[t]}
            </button>
          ))}
        </div>
      </div>

      {/* Notifications */}
      <div className="card settings-card">
        <h3>Notifications</h3>
        <Toggle
          label="Daily challenge reminders"
          hint="Nudge me to keep my streak going."
          checked={prefs.challengeReminders}
          onChange={(v) => setPrefs((p) => ({ ...p, challengeReminders: v }))}
        />
        <Toggle
          label="Message alerts"
          hint="Notify me when a partner messages me."
          checked={prefs.messageAlerts}
          onChange={(v) => setPrefs((p) => ({ ...p, messageAlerts: v }))}
        />
        <Toggle
          label="Product updates"
          hint="Occasional news about new features."
          checked={prefs.productUpdates}
          onChange={(v) => setPrefs((p) => ({ ...p, productUpdates: v }))}
        />
        <p className="field-hint">Preferences are saved to this device.</p>
      </div>

      {/* About */}
      <div className="card settings-card">
        <h3>About</h3>
        <p className="muted setting-about">SkillSwap AI · v1.0.0</p>
        {memberSince && <p className="muted setting-about">Member since {memberSince}</p>}
      </div>

      {/* Account — pinned to the bottom */}
      <div className="card settings-card settings-account">
        <h3>Account</h3>
        <p className="field-hint">You'll need to sign in again to return.</p>
        <button type="button" className="btn btn-danger settings-signout" onClick={signOut}>
          Sign out
        </button>
      </div>
    </section>
  );
}
