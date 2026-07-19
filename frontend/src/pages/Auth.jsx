// Sign in / sign up screen shown when the user is not authenticated.

import { useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";

export default function Auth() {
  const { login, notify } = useApp();
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const isSignup = mode === "signup";

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  function switchMode() {
    setMode(isSignup ? "login" : "signup");
    setError(null);
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
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

  return (
    <section className="hero">
      <h1>{isSignup ? "Create your account" : "Welcome back"}</h1>
      <p className="muted">
        {isSignup
          ? "Sign up to build your personalized career plan."
          : "Sign in to continue your learning journey."}
      </p>

      <form className="card form" onSubmit={submit}>
        {isSignup && (
          <label>
            Name <span className="field-hint">(optional)</span>
            <input
              type="text"
              autoComplete="name"
              value={form.name}
              onChange={update("name")}
            />
          </label>
        )}
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
        <label>
          Password
          <input
            type="password"
            required
            minLength={isSignup ? 8 : undefined}
            autoComplete={isSignup ? "new-password" : "current-password"}
            value={form.password}
            onChange={update("password")}
            aria-describedby={isSignup ? "pw-hint" : undefined}
          />
          {isSignup && (
            <span id="pw-hint" className="field-hint">
              At least 8 characters.
            </span>
          )}
        </label>

        {error && <ErrorBanner message={error} />}

        <button className="btn btn-primary" disabled={busy} aria-busy={busy}>
          {busy
            ? isSignup
              ? "Creating account…"
              : "Signing in…"
            : isSignup
              ? "Sign up"
              : "Sign in"}
        </button>
      </form>

      <p className="muted">
        {isSignup ? "Already have an account?" : "New here?"}{" "}
        <button type="button" className="link-btn" onClick={switchMode}>
          {isSignup ? "Sign in" : "Create an account"}
        </button>
      </p>
    </section>
  );
}
