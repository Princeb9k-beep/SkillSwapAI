// Interview simulator: start -> answer questions -> get score + feedback.

import { useState } from "react";
import { api } from "../api/client.js";
import { ErrorBanner, LoadingState } from "../components/States.jsx";

export default function InterviewSimulator() {
  const [role, setRole] = useState("Backend Engineer");
  const [interview, setInterview] = useState(null);
  const [answers, setAnswers] = useState([]);
  const [result, setResult] = useState(null);
  const [phase, setPhase] = useState("setup"); // setup | answering | scoring | done
  const [error, setError] = useState(null);

  async function start(e) {
    e.preventDefault();
    setError(null);
    setPhase("loading");
    try {
      const data = await api.startInterview({ role, count: 5 });
      setInterview(data);
      setAnswers(new Array(data.questions.length).fill(""));
      setResult(null);
      setPhase("answering");
    } catch (err) {
      setError(err.message);
      setPhase("setup");
    }
  }

  async function submit(e) {
    e.preventDefault();
    setPhase("scoring");
    setError(null);
    try {
      const data = await api.answerInterview({
        interview_id: interview.interview_id,
        answers,
      });
      setResult(data);
      setPhase("done");
    } catch (err) {
      setError(err.message);
      setPhase("answering");
    }
  }

  if (phase === "loading") return <LoadingState label="Preparing your interview…" />;
  if (phase === "scoring") return <LoadingState label="Evaluating your answers…" />;

  return (
    <section>
      <h2>Interview Simulator</h2>

      {phase === "setup" && (
        <form className="card form" onSubmit={start}>
          <label>
            Role
            <input value={role} onChange={(e) => setRole(e.target.value)} required />
          </label>
          {error && <ErrorBanner message={error} />}
          <button className="btn btn-primary">Start interview</button>
        </form>
      )}

      {phase === "answering" && interview && (
        <form className="card form" onSubmit={submit}>
          <p className="muted" aria-live="polite">
            {answers.filter((a) => a.trim()).length} of {interview.questions.length}{" "}
            answered
          </p>
          {interview.questions.map((q, i) => (
            <label key={i}>
              {i + 1}. {q}
              <textarea
                rows={2}
                value={answers[i]}
                onChange={(e) =>
                  setAnswers((a) => a.map((v, j) => (j === i ? e.target.value : v)))
                }
              />
            </label>
          ))}
          {error && <ErrorBanner message={error} />}
          <button className="btn btn-primary">Submit answers</button>
        </form>
      )}

      {phase === "done" && result && (
        <div className="card">
          <h3
            className={`score ${
              result.score >= 70
                ? "score-good"
                : result.score >= 40
                  ? "score-mid"
                  : "score-low"
            }`}
          >
            {result.score}
            <span className="score-max">/100</span>
          </h3>
          <p>{result.feedback}</p>
          <button type="button" className="btn" onClick={() => setPhase("setup")}>
            Practice again
          </button>
        </div>
      )}
    </section>
  );
}
