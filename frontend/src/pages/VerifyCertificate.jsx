// Public certificate verification (/verify-cert?code=…). Works signed-out so a
// shared link is verifiable by anyone.

import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import Icon from "../components/icons.jsx";

export default function VerifyCertificate() {
  const [state, setState] = useState({ status: "loading", cert: null });
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const code = new URLSearchParams(window.location.search).get("code");
    if (!code) {
      setState({ status: "invalid", cert: null });
      return;
    }
    api
      .verifyCertificate(code)
      .then((cert) => setState({ status: "valid", cert }))
      .catch(() => setState({ status: "invalid", cert: null }));
  }, []);

  return (
    <section className="verify-email-page">
      <div className="card verify-email-card cert-verify">
        <div className="brand-lg">
          SkillSwap<span className="brand-ai">AI</span>
        </div>
        {state.status === "loading" && <p className="muted">Verifying certificate…</p>}
        {state.status === "invalid" && (
          <>
            <h1>Not found</h1>
            <p className="muted">We couldn't verify that certificate code.</p>
          </>
        )}
        {state.status === "valid" && (
          <>
            <div className="cert-seal" aria-hidden="true"><Icon name="graduation" size={40} /></div>
            <h1>Verified certificate</h1>
            <p className="cert-holder"><strong>{state.cert.holder}</strong></p>
            <p className="muted">completed</p>
            <p className="cert-title">{state.cert.title}</p>
            {state.cert.issued_at && (
              <p className="field-hint">
                Issued {new Date(state.cert.issued_at).toLocaleDateString()}
              </p>
            )}
            <a className="btn btn-primary" href="/">Go to SkillSwap AI</a>
          </>
        )}
      </div>
    </section>
  );
}
