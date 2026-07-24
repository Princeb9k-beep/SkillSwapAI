// Landing page for the emailed verification link (/verify-email?token=…). It
// consumes the token on load and works whether or not the visitor is signed in,
// since email links can be opened on any device.

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";

export default function VerifyEmail() {
  const { isAuthed, updateUser } = useApp();
  const [status, setStatus] = useState("verifying"); // verifying | ok | error
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return; // guard React 18 double-invoke in dev
    ran.current = true;
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setStatus("error");
      return;
    }
    api
      .verifyEmail(token)
      .then(() => {
        setStatus("ok");
        if (isAuthed) updateUser({ email_verified: true });
      })
      .catch(() => setStatus("error"));
  }, [isAuthed, updateUser]);

  return (
    <section className="verify-email-page">
      <div className="card verify-email-card">
        <div className="brand-lg">
          SkillSwap<span className="brand-ai">AI</span>
        </div>
        {status === "verifying" && <p className="muted">Verifying your email…</p>}
        {status === "ok" && (
          <>
            <h1>Email verified ✓</h1>
            <p className="muted">Your email address is confirmed — you're all set.</p>
            <Link className="btn btn-primary" to="/">
              {isAuthed ? "Go to the app" : "Sign in"}
            </Link>
          </>
        )}
        {status === "error" && (
          <>
            <h1>Link expired</h1>
            <p className="muted">
              This verification link is invalid or has expired. Sign in and request a
              new one from Settings.
            </p>
            <Link className="btn btn-primary" to="/">
              Go to sign in
            </Link>
          </>
        )}
      </div>
    </section>
  );
}
