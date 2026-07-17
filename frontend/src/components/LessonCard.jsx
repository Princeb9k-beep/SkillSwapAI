// A single daily-lesson card (Duolingo-style), with a complete toggle.

export default function LessonCard({ lesson, onComplete }) {
  return (
    <article className={`card lesson ${lesson.completed ? "done" : ""}`}>
      <header className="lesson-head">
        <span className="badge">Day {lesson.day}</span>
        {lesson.completed && <span className="check" aria-label="Completed">✓</span>}
      </header>
      <h3>{lesson.title}</h3>
      {lesson.content && <p className="muted">{lesson.content}</p>}
      {!lesson.completed && (
        <button className="btn btn-primary" onClick={() => onComplete(lesson.id)}>
          Mark complete
        </button>
      )}
    </article>
  );
}
