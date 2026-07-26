// Landing page for the OAuth redirect (/oauth/callback?code=…). Exchanges the
// code for our session and signs the user in. Works pre-auth (rendered by the
// Shell before the auth gate).

import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";

export default function OAuthCallback() {
  const { login, notify } = useApp();
  const [status, setStatus] = useState("working"); // working | error
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const provider = localStorage.getItem("oauth_provider");
    if (!code || !provider) {
      setStatus("error");
      return;
    }
    api
      .oauthCallback(provider, code)
      .then((data) => {
        localStorage.removeItem("oauth_provider");
        login(data.token, data.user);
        notify(data.created ? "Welcome to SkillSwap AI!" : "Signed in", "success");
        window.history.replaceState({}, "", "/");
      })
      .catch(() => setStatus("error"));
  }, [login, notify]);

  return (
    <section className="verify-email-page">
      <div className="card verify-email-card">
        <div className="brand-lg">
          SkillSwap<span className="brand-ai">AI</span>
        </div>
        {status === "working" ? (
          <p className="muted">Finishing sign-in…</p>
        ) : (
          <>
            <h1>Sign-in failed</h1>
            <p className="muted">We couldn't complete that sign-in. Please try again.</p>
            <a className="btn btn-primary" href="/">Back to sign in</a>
          </>
        )}
      </div>
    </section>
  );
}
