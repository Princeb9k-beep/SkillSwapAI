// Live translation (spec §3.3): translate text into another language via Groq.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";

export default function Translate() {
  const { notify } = useApp();
  const [languages, setLanguages] = useState(["Spanish", "French", "German"]);
  const [target, setTarget] = useState("Spanish");
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.translateLanguages().then(setLanguages).catch(() => {});
  }, []);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await api.translate(text, target));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h1>Translate</h1>
      <p className="muted">
        Break the language barrier — translate notes or messages so you can learn with
        partners anywhere.
      </p>

      <form className="card form" onSubmit={submit}>
        <label>
          Text
          <textarea
            rows={5}
            required
            value={text}
            placeholder="Type or paste text to translate…"
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        <label>
          Translate to
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            {languages.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </label>
        {error && <ErrorBanner message={error} />}
        <button className="btn btn-primary" disabled={busy || !text.trim()} aria-busy={busy}>
          {busy ? "Translating…" : "Translate"}
        </button>
      </form>

      {result && (
        <div className="card">
          <div className="row-between">
            <h3>{result.target_language}</h3>
            <button
              type="button"
              className="btn"
              aria-label="Copy translation"
              onClick={() => {
                navigator.clipboard.writeText(result.translation);
                notify("Copied", "success");
              }}
            >
              Copy
            </button>
          </div>
          <p className="translation-out">{result.translation}</p>
          {result.note && <p className="field-hint">{result.note}</p>}
        </div>
      )}
    </section>
  );
}
