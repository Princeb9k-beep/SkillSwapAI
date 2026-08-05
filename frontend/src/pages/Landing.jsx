// Public marketing landing page shown to logged-out visitors. Sells the product
// before the sign-in wall. CTAs flip the logged-out shell into the Auth form.

import Icon from "../components/icons.jsx";

const FEATURES = [
  { icon: "handshake", title: "AI skill matching", text: "Get paired with people who can teach what you want — and learn what you can teach. A dating app for learning." },
  { icon: "brain", title: "Your 24/7 AI coach", text: "Ask anything, get study plans, and upload your resume or code for instant, specific feedback." },
  { icon: "video", title: "Live practice rooms", text: "Video sessions with screen-share and shared notes — practice with a real partner, not just an app." },
  { icon: "flame", title: "Streaks, leagues & buddies", text: "Daily goals, weekly leagues, and a shared streak with a partner keep you showing up." },
  { icon: "shieldCheck", title: "Get verified & certified", text: "Prove your skills with peer or AI assessments, and earn shareable course certificates." },
  { icon: "cards", title: "AI flashcards & lessons", text: "Turn anything into spaced-repetition flashcards and AI-written daily lessons toward your goal." },
];

const STEPS = [
  { n: 1, title: "Add your skills", text: "List what you can teach and what you want to learn." },
  { n: 2, title: "Meet your match", text: "We rank complementary partners by compatibility." },
  { n: 3, title: "Learn & level up", text: "Swap skills, chat, book sessions, and build a streak." },
];

export default function Landing({ onSignup, onLogin }) {
  return (
    <div className="landing">
      <header className="landing-nav">
        <span className="landing-brand">SkillSwap<span className="brand-ai">AI</span></span>
        <button type="button" className="btn btn-ghost" onClick={onLogin}>Sign in</button>
      </header>

      <section className="landing-hero">
        <h1 className="landing-title">Swap skills, <span className="landing-accent">not cash.</span></h1>
        <p className="landing-sub">
          Teach what you know, learn what you want — with AI matching, a personal AI coach,
          live practice, and a community that keeps you going. Free to start.
        </p>
        <div className="landing-cta">
          <button type="button" className="btn btn-primary btn-lg" onClick={onSignup}>
            Get started free
          </button>
          <button type="button" className="btn btn-lg" onClick={onLogin}>
            I already have an account
          </button>
        </div>
        <p className="landing-note muted">No credit card. Learn your first skill this week.</p>
      </section>

      <section className="landing-steps">
        {STEPS.map((s) => (
          <div key={s.n} className="landing-step">
            <span className="landing-step-n">{s.n}</span>
            <h3>{s.title}</h3>
            <p className="muted">{s.text}</p>
          </div>
        ))}
      </section>

      <section className="landing-features">
        <h2>Everything you need to actually follow through</h2>
        <div className="landing-feature-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="landing-feature card">
              <span className="landing-feature-icon" aria-hidden="true"><Icon name={f.icon} size={26} /></span>
              <h3>{f.title}</h3>
              <p className="muted">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-final">
        <h2>Start learning by teaching.</h2>
        <button type="button" className="btn btn-primary btn-lg" onClick={onSignup}>
          Create your free account
        </button>
      </section>

      <footer className="landing-footer muted">
        <div>SkillSwap AI · Swap skills, not cash.</div>
        <div className="landing-footer-links">
          <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a>
        </div>
      </footer>
    </div>
  );
}
