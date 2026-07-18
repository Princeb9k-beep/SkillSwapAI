// A week-by-week learning calendar derived from the roadmap milestones.
// Each milestone spans its `weeks`; its `steps` are distributed across those weeks
// and laid out on real calendar dates starting today. The current week is marked.

function addDays(date, n) {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}

function fmt(d) {
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function buildWeeks(milestones) {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const weeks = [];
  let g = 0;
  milestones.forEach((m, mi) => {
    const span = Math.max(1, Math.round(Number(m.weeks) || 1));
    const steps = Array.isArray(m.steps) ? m.steps : [];
    // Assign step k to week floor(k*span/len) — front-loaded so earlier weeks
    // (including the current one) always get concrete tasks first.
    for (let w = 0; w < span; w++) {
      const wkSteps = steps.filter(
        (_, k) => Math.floor((k * span) / steps.length) === w
      );
      weeks.push({
        index: g,
        from: addDays(start, g * 7),
        toDate: addDays(start, g * 7 + 6),
        milestoneIndex: mi,
        milestoneTitle: m.title,
        steps: wkSteps,
      });
      g += 1;
    }
  });
  return weeks;
}

export default function LearningCalendar({ milestones }) {
  if (!milestones || milestones.length === 0) return null;
  const weeks = buildWeeks(milestones);
  if (weeks.length === 0) return null;

  const end = weeks[weeks.length - 1].toDate;

  return (
    <section className="calendar-section" aria-labelledby="cal-heading">
      <div className="row-between">
        <h2 id="cal-heading">Learning calendar</h2>
        <span className="muted cal-summary">
          {weeks.length} weeks · finishes {fmt(end)}
        </span>
      </div>

      <ol className="calendar" aria-label="Weekly learning plan">
        {weeks.map((wk) => (
          <li
            key={wk.index}
            className={`cal-week${wk.index === 0 ? " current" : ""}`}
            aria-current={wk.index === 0 ? "date" : undefined}
          >
            <div className="cal-date">
              <span className="cal-weeknum">Week {wk.index + 1}</span>
              <time>
                {fmt(wk.from)} – {fmt(wk.toDate)}
              </time>
              {wk.index === 0 && <span className="badge cal-now">This week</span>}
            </div>
            <div className="cal-body">
              <span className="badge">{wk.milestoneTitle}</span>
              {wk.steps.length > 0 ? (
                <ul>
                  {wk.steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Keep building on “{wk.milestoneTitle}”.</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
