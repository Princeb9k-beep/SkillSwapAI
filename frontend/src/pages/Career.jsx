// Career hub — combines Portfolio, Resume builder, and Interview simulator into
// one tab with a sub-tab switcher (replaces the separate Resume/Interview tabs).

import { useState } from "react";
import Portfolio from "./Portfolio.jsx";
import ResumeBuilder from "./ResumeBuilder.jsx";
import InterviewSimulator from "./InterviewSimulator.jsx";

const TABS = [
  { key: "portfolio", label: "Portfolio" },
  { key: "resume", label: "Resume" },
  { key: "interview", label: "Interview" },
];

export default function Career({ initialTab = "portfolio" }) {
  const [tab, setTab] = useState(initialTab);

  return (
    <section>
      <h1>Career</h1>
      <div className="subtabs" role="tablist" aria-label="Career tools">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            className={`subtab${tab === t.key ? " active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="subtab-panel">
        {tab === "portfolio" && <Portfolio />}
        {tab === "resume" && <ResumeBuilder />}
        {tab === "interview" && <InterviewSimulator />}
      </div>
    </section>
  );
}
