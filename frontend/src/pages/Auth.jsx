// Sign in / sign up / forgot-password screen shown when not authenticated.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";

export default function Auth() {
  const { login, notify } = useApp();
  const [mode, setMode] = useState("login"); // login | signup | forgot | reset
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [resetToken, setResetToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const isSignup = mode === "signup";

  // Support real reset links (/reset-password?token=… or ?reset_token=…).
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const t = p.get("token") || p.get("reset_token");
    if (t && window.location.pathname.includes("reset")) {
      setResetToken(t);
      setMode("reset");
    }
  }, []);

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "forgot") {
        const data = await api.forgotPassword(form.email);
        if (data?.dev_token) {
          setResetToken(data.dev_token);
          setMode("reset");
          notify("Enter a new password to finish.", "info");
        } else {
          notify("If that email exists, a reset link is on its way.", "info");
          setMode("login");
        }
        return;
      }
      if (mode === "reset") {
        await api.resetPassword(resetToken, form.password);
        notify("Password updated — please sign in.", "success");
        setForm((f) => ({ ...f, password: "" }));
        setMode("login");
        return;
      }
      const data = isSignup
        ? await api.signup({
            email: form.email,
            password: form.password,
            name: form.name || null,
          })
        : await api.login({ email: form.email, password: form.password });
      login(data.token, data.user);
      notify(isSignup ? "Welcome to SkillSwap AI!" : "Signed in", "success");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const titles = {
    login: "Welcome back",
    signup: "Create your account",
    forgot: "Reset your password",
    reset: "Choose a new password",
  };
  const subtitles = {
    login: "Sign in to continue your learning journey.",
    signup: "Sign up to build your personalized career plan.",
    forgot: "We'll send a reset link to your email.",
    reset: "Enter a new password for your account.",
  };

  return (
    <section className="hero">
      <h1>{titles[mode]}</h1>
      <p className="muted">{subtitles[mode]}</p>

      <form className="card form" onSubmit={submit}>
        {isSignup && (
          <label>
            Name <span className="field-hint">(optional)</span>
            <input type="text" autoComplete="name" value={form.name} onChange={update("name")} />
          </label>
        )}

        {mode !== "reset" && (
          <label>
            Email
            <input
              type="email"
              required
              inputMode="email"
              autoComplete="email"
              value={form.email}
              placeholder="you@example.com"
              onChange={update("email")}
            />
          </label>
        )}

        {mode !== "forgot" && (
          <label>
            Password
            <input
              type="password"
              required
              minLength={isSignup || mode === "reset" ? 8 : undefined}
              autoComplete={isSignup || mode === "reset" ? "new-password" : "current-password"}
              value={form.password}
              onChange={update("password")}
            />
            {(isSignup || mode === "reset") && (
              <span className="field-hint">At least 8 characters.</span>
            )}
          </label>
        )}

        {error && <ErrorBanner message={error} />}

        <button className="btn btn-primary" disabled={busy} aria-busy={busy}>
          {busy
            ? "Working…"
            : mode === "login"
              ? "Sign in"
              : mode === "signup"
                ? "Sign up"
                : mode === "forgot"
                  ? "Send reset link"
                  : "Update password"}
        </button>
      </form>

      <p className="muted auth-links">
        {mode === "login" && (
          <>
            <button type="button" className="link-btn" onClick={() => { setMode("forgot"); setError(null); }}>
              Forgot password?
            </button>
            {" · "}
            <button type="button" className="link-btn" onClick={() => { setMode("signup"); setError(null); }}>
              Create an account
            </button>
          </>
        )}
        {mode === "signup" && (
          <>
            Already have an account?{" "}
            <button type="button" className="link-btn" onClick={() => { setMode("login"); setError(null); }}>
              Sign in
            </button>
          </>
        )}
        {(mode === "forgot" || mode === "reset") && (
          <button type="button" className="link-btn" onClick={() => { setMode("login"); setError(null); }}>
            Back to sign in
          </button>
        )}
      </p>
    </section>
  );
}
