// A single daily-lesson card (Duolingo-style), with a complete toggle.

// Inline SVG check (skill rule: use vector icons, not emoji glyphs).
function CheckIcon() {
  return (
    <svg
      className="check"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      role="img"
      aria-label="Completed"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

export default function LessonCard({ lesson, onComplete }) {
  return (
    <article className={`card lesson ${lesson.completed ? "done" : ""}`}>
      <header className="lesson-head">
        <span className="badge">Day {lesson.day}</span>
        {lesson.completed && <CheckIcon />}
      </header>
      <h3>{lesson.title}</h3>
      {lesson.content && <p className="muted">{lesson.content}</p>}
      {!lesson.completed && (
        <button
          className="btn btn-primary"
          onClick={() => onComplete(lesson.id)}
          aria-label={`Mark lesson "${lesson.title}" complete`}
        >
          Mark complete
        </button>
      )}
    </article>
  );
}
