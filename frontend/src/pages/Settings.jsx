// Settings: profile, appearance (theme), notification preferences, and account.
// The Sign out button lives here, pinned to the bottom of the page.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { getTheme, setTheme, THEMES } from "../theme.js";
import {
  pushSupported,
  permission,
  getExistingSubscription,
  enablePush,
  disablePush,
} from "../push.js";

const PUSH_REASONS = {
  unsupported: "This browser doesn't support push notifications.",
  "server-unconfigured": "Push isn't configured on the server yet.",
  denied: "Notifications are blocked — allow them in your browser settings.",
};

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
    availability_note: user?.availability_note || "",
  });
  const [saving, setSaving] = useState(false);
  const [theme, setThemeState] = useState(getTheme());

  // Browser push state for this device.
  const [pushOn, setPushOn] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushMsg, setPushMsg] = useState(null);
  const supported = pushSupported();

  useEffect(() => {
    if (!supported) return;
    getExistingSubscription()
      .then((sub) => setPushOn(!!sub))
      .catch(() => {});
  }, [supported]);

  // Referral / invite.
  const [referral, setReferral] = useState(null);
  useEffect(() => {
    api.referralMe().then(setReferral).catch(() => {});
  }, []);
  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(referral.link);
      notify("Invite link copied", "success");
    } catch {
      notify("Couldn't copy — link is shown below.", "info");
    }
  }

  // Blocked users.
  const [blocked, setBlocked] = useState([]);
  useEffect(() => {
    api.listBlocks().then(setBlocked).catch(() => {});
  }, []);
  async function unblock(id) {
    try {
      await api.unblockUser(id);
      setBlocked((b) => b.filter((x) => x.user_id !== id));
      notify("Unblocked", "success");
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function togglePush(v) {
    setPushBusy(true);
    setPushMsg(null);
    try {
      const res = v ? await enablePush() : await disablePush();
      if (res.ok) {
        setPushOn(v);
        notify(v ? "Push notifications on" : "Push notifications off", "success");
      } else {
        setPushMsg(PUSH_REASONS[res.reason] || "Couldn't enable push notifications.");
      }
    } catch (err) {
      setPushMsg(err.message);
    } finally {
      setPushBusy(false);
    }
  }

  // Notification prefs are real, server-backed settings on the user.
  const notif = {
    notify_messages: user?.notify_messages ?? true,
    notify_achievements: user?.notify_achievements ?? true,
    notify_product: user?.notify_product ?? false,
    daily_reminder: user?.daily_reminder ?? false,
  };

  async function setPref(key, value) {
    updateUser({ [key]: value }); // optimistic
    try {
      const updated = await api.updateProfile({ [key]: value });
      updateUser(updated);
    } catch (err) {
      updateUser({ [key]: !value }); // revert
      notify(err.message, "error");
    }
  }

  async function saveProfile(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim() || null,
        goal: form.goal.trim() || null,
        target_income:
          form.target_income === "" ? null : Number(form.target_income),
        availability_note: form.availability_note.trim() || null,
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

  async function signOutEverywhere() {
    try {
      await api.logoutAll();
      logout();
      notify("Signed out of all devices", "info");
    } catch (err) {
      notify(err.message, "error");
    }
  }

  const [verifying, setVerifying] = useState(false);
  async function verifyEmail() {
    setVerifying(true);
    try {
      const res = await api.resendVerification();
      if (res?.dev_token) {
        // Off-production without a provider — finish verifying with the token.
        await api.verifyEmail(res.dev_token);
        updateUser({ email_verified: true });
        notify("Email verified", "success");
      } else if (res?.verified) {
        // Server can't send email, so it confirmed the address directly.
        updateUser({ email_verified: true });
        notify("Email confirmed — this server isn't set up to send email, so we verified you directly.", "success");
      } else {
        notify("Verification email sent — check your inbox and spam.", "success");
      }
    } catch (err) {
      // A failed send (bad SMTP settings) now surfaces here instead of silently.
      notify(err.message, "error");
    } finally {
      setVerifying(false);
    }
  }

  async function deleteAccount() {
    if (
      !window.confirm(
        "Delete your account permanently? This removes all your data and can't be undone.",
      )
    ) {
      return;
    }
    try {
      await api.deleteAccount();
      logout();
      notify("Your account has been deleted.", "info");
    } catch (err) {
      notify(err.message, "error");
    }
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
      <p className="muted">Manage your profile, plan, appearance, and account.</p>

      {/* Plan */}
      <div className="card settings-card">
        <h3>Plan</h3>
        <div className="row-between plan-row">
          <span>
            You're on the <strong className={`tier-pill tier-${user?.tier || "free"}`}>
              {(user?.tier || "free").toUpperCase()}
            </strong> plan.
          </span>
          <a className="btn btn-primary" href="/plans">
            {user?.tier === "elite" ? "Manage plan" : "Upgrade"}
          </a>
        </div>
      </div>

      {/* Invite friends */}
      {referral && (
        <div className="card settings-card">
          <h3>Invite friends</h3>
          <p className="field-hint">
            Share your code — you and your friend each get {referral.bonus_tokens} bonus
            AI tokens when they join.
          </p>
          <div className="invite-row">
            <code className="invite-code">{referral.code}</code>
            <button type="button" className="btn btn-primary" onClick={copyInvite}>
              Copy invite link
            </button>
          </div>
          <p className="muted invite-stats">
            {referral.referred_count} joined · {referral.tokens_earned} tokens earned
          </p>
        </div>
      )}

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
          <span className="field-hint email-status">
            {user?.email_verified ? (
              <span className="verified-ok">Verified ✓</span>
            ) : (
              <>
                Not verified.{" "}
                <button
                  type="button"
                  className="link-btn"
                  onClick={verifyEmail}
                  disabled={verifying}
                >
                  {verifying ? "Verifying…" : "Verify email"}
                </button>
              </>
            )}
          </span>
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
        <label>
          Availability <span className="field-hint">(shown to partners when booking)</span>
          <input
            type="text"
            maxLength={255}
            value={form.availability_note}
            placeholder="e.g. Weekday evenings ET"
            onChange={(e) => setForm((f) => ({ ...f, availability_note: e.target.value }))}
          />
        </label>
        {user?.timezone && (
          <p className="field-hint">
            Times are shown in your time zone (<strong>{user.timezone}</strong>), detected
            automatically from this device.
          </p>
        )}
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
          label="Message alerts"
          hint="Notify me when a partner sends me a message."
          checked={notif.notify_messages}
          onChange={(v) => setPref("notify_messages", v)}
        />
        <Toggle
          label="Achievement alerts"
          hint="Celebrate when I unlock an achievement."
          checked={notif.notify_achievements}
          onChange={(v) => setPref("notify_achievements", v)}
        />
        <Toggle
          label="Product updates"
          hint="Occasional news about new features."
          checked={notif.notify_product}
          onChange={(v) => setPref("notify_product", v)}
        />
        <Toggle
          label="Daily learning reminder"
          hint="A once-a-day nudge to do your lesson and keep your streak."
          checked={notif.daily_reminder}
          onChange={(v) => setPref("daily_reminder", v)}
        />
        <p className="field-hint">Message and achievement alerts control your in-app notifications.</p>

        <div className="setting-row" style={{ borderTop: "1px solid var(--border)" }}>
          <span className="setting-row-text">
            <span className="setting-row-label">Browser push on this device</span>
            <span className="setting-row-hint muted">
              Get message alerts even when the app is closed.
            </span>
          </span>
          <input
            type="checkbox"
            className="switch"
            disabled={!supported || pushBusy}
            checked={pushOn}
            onChange={(e) => togglePush(e.target.checked)}
          />
        </div>
        {permission() === "denied" && supported && (
          <p className="field-hint">Notifications are blocked in your browser settings.</p>
        )}
        {pushMsg && <p className="field-hint">{pushMsg}</p>}
      </div>

      {/* About */}
      <div className="card settings-card">
        <h3>About</h3>
        <p className="muted setting-about">SkillSwap AI · v1.0.0</p>
        {memberSince && <p className="muted setting-about">Member since {memberSince}</p>}
        <p className="setting-about">
          <a href="/privacy">Privacy Policy</a> · <a href="/terms">Terms of Service</a>
        </p>
      </div>

      {/* Moderation (admins only) */}
      {user?.is_admin && (
        <div className="card settings-card">
          <h3>Moderation</h3>
          <p className="field-hint">Review reported content and users.</p>
          <a className="btn btn-primary" href="/admin">
            Open moderation dashboard
          </a>
        </div>
      )}

      {/* Blocked users */}
      <div className="card settings-card">
        <h3>Blocked users</h3>
        {blocked.length === 0 ? (
          <p className="field-hint">You haven't blocked anyone.</p>
        ) : (
          <ul className="blocked-list">
            {blocked.map((u) => (
              <li key={u.user_id} className="row-between">
                <span>{u.name}</span>
                <button type="button" className="btn" onClick={() => unblock(u.user_id)}>
                  Unblock
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Account — pinned to the bottom */}
      <div className="card settings-card settings-account">
        <h3>Account</h3>
        <p className="field-hint">You'll need to sign in again to return.</p>
        <div className="account-actions">
          <button type="button" className="btn settings-signout" onClick={signOut}>
            Sign out
          </button>
          <button type="button" className="btn" onClick={signOutEverywhere}>
            Sign out of all devices
          </button>
          <button type="button" className="btn btn-danger" onClick={deleteAccount}>
            Delete account
          </button>
        </div>
      </div>
    </section>
  );
}
