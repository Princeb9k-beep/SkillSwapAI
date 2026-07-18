// A real calendar view of the learning plan, with Day / Week / Month views.
//
// Roadmap milestones are scheduled onto real dates starting today: each milestone
// spans its `weeks`, and its steps are spread across that span. The result is a
// date-keyed map of "events" (a step to study that day) rendered as a month grid,
// a 7-day week, or a single day — switchable from the corner control.

import { useMemo, useState } from "react";

const PALETTE = ["#4f46e5", "#0ea5e9", "#16a34a", "#d97706", "#db2777", "#7c3aed"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function startOfDay(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}
function addDays(d, n) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}
function addMonths(d, n) {
  const x = new Date(d);
  x.setMonth(x.getMonth() + n);
  return x;
}
function sameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}
function key(d) {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

// Build the schedule: assign each roadmap step to a real date.
function buildEventMap(milestones) {
  const start = startOfDay(new Date());
  const map = new Map();
  let dayCursor = 0;

  milestones.forEach((m, mi) => {
    const span = Math.max(1, Math.round(Number(m.weeks) || 1));
    const days = span * 7;
    const steps = Array.isArray(m.steps) ? m.steps : [];
    const push = (date, step) => {
      const k = key(date);
      if (!map.has(k)) map.set(k, []);
      map.get(k).push({ milestoneIndex: mi, milestoneTitle: m.title, step });
    };

    if (steps.length === 0) {
      push(addDays(start, dayCursor), `Focus: ${m.title}`);
    } else {
      steps.forEach((step, s) => {
        const offset =
          steps.length === 1
            ? 0
            : Math.round((s * (days - 1)) / (steps.length - 1));
        push(addDays(start, dayCursor + offset), step);
      });
    }
    dayCursor += days;
  });

  return map;
}

function Event({ ev }) {
  const color = PALETTE[ev.milestoneIndex % PALETTE.length];
  return (
    <span className="lcal-event" style={{ borderLeftColor: color }} title={ev.step}>
      {ev.step}
    </span>
  );
}

export default function LearningCalendar({ milestones }) {
  const [view, setView] = useState("month");
  const [focus, setFocus] = useState(() => startOfDay(new Date()));
  const today = startOfDay(new Date());

  const events = useMemo(() => buildEventMap(milestones || []), [milestones]);
  const eventsFor = (d) => events.get(key(d)) || [];

  if (!milestones || milestones.length === 0) return null;

  function step(dir) {
    if (view === "month") setFocus((f) => addMonths(f, dir));
    else if (view === "week") setFocus((f) => addDays(f, dir * 7));
    else setFocus((f) => addDays(f, dir));
  }

  const title =
    view === "month"
      ? focus.toLocaleDateString(undefined, { month: "long", year: "numeric" })
      : view === "week"
        ? `Week of ${addDays(focus, -focus.getDay()).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })}`
        : focus.toLocaleDateString(undefined, {
            weekday: "long",
            month: "long",
            day: "numeric",
          });

  return (
    <section className="calendar-section" aria-labelledby="cal-heading">
      <div className="lcal-header">
        <h2 id="cal-heading">Learning calendar</h2>
        <div
          className="lcal-view-switch"
          role="group"
          aria-label="Calendar view"
        >
          {["day", "week", "month"].map((v) => (
            <button
              key={v}
              type="button"
              className={`lcal-view-btn${view === v ? " active" : ""}`}
              aria-pressed={view === v}
              onClick={() => setView(v)}
            >
              {v[0].toUpperCase() + v.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="lcal-toolbar">
        <div className="lcal-nav">
          <button
            type="button"
            className="btn lcal-arrow"
            aria-label="Previous"
            onClick={() => step(-1)}
          >
            ‹
          </button>
          <button
            type="button"
            className="btn lcal-arrow"
            aria-label="Next"
            onClick={() => step(1)}
          >
            ›
          </button>
          <button
            type="button"
            className="btn lcal-today"
            onClick={() => setFocus(startOfDay(new Date()))}
          >
            Today
          </button>
        </div>
        <strong className="lcal-title">{title}</strong>
      </div>

      {view === "month" && (
        <MonthView focus={focus} today={today} eventsFor={eventsFor} />
      )}
      {view === "week" && (
        <WeekView focus={focus} today={today} eventsFor={eventsFor} />
      )}
      {view === "day" && (
        <DayView focus={focus} today={today} eventsFor={eventsFor} />
      )}
    </section>
  );
}

function MonthView({ focus, today, eventsFor }) {
  const first = new Date(focus.getFullYear(), focus.getMonth(), 1);
  const last = new Date(focus.getFullYear(), focus.getMonth() + 1, 0);
  const weeks = [];
  let cur = addDays(first, -first.getDay());
  while (true) {
    const row = [];
    for (let i = 0; i < 7; i++) {
      row.push(cur);
      cur = addDays(cur, 1);
    }
    weeks.push(row);
    if (cur > last) break;
  }

  return (
    <div className="lcal-scroll">
      <div className="lcal-grid month">
        {WEEKDAYS.map((w) => (
          <div key={w} className="lcal-weekday" aria-hidden="true">
            {w}
          </div>
        ))}
        {weeks.flat().map((d) => {
          const evs = eventsFor(d);
          const other = d.getMonth() !== focus.getMonth();
          return (
            <div
              key={key(d)}
              className={`lcal-cell${other ? " other-month" : ""}${
                sameDay(d, today) ? " today" : ""
              }`}
            >
              <span className="lcal-daynum">{d.getDate()}</span>
              {evs.slice(0, 3).map((ev, i) => (
                <Event key={i} ev={ev} />
              ))}
              {evs.length > 3 && (
                <span className="lcal-more">+{evs.length - 3} more</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WeekView({ focus, today, eventsFor }) {
  const start = addDays(focus, -focus.getDay());
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  return (
    <div className="lcal-scroll">
      <div className="lcal-grid week">
        {days.map((d) => {
          const evs = eventsFor(d);
          return (
            <div
              key={key(d)}
              className={`lcal-cell week-cell${sameDay(d, today) ? " today" : ""}`}
            >
              <span className="lcal-daynum">
                {WEEKDAYS[d.getDay()]} {d.getDate()}
              </span>
              {evs.length === 0 ? (
                <span className="muted lcal-empty">—</span>
              ) : (
                evs.map((ev, i) => <Event key={i} ev={ev} />)
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DayView({ focus, today, eventsFor }) {
  const evs = eventsFor(focus);
  return (
    <div className={`lcal-day${sameDay(focus, today) ? " today" : ""}`}>
      {evs.length === 0 ? (
        <p className="muted">Nothing scheduled for this day — a good day to review.</p>
      ) : (
        <ul className="lcal-day-list">
          {evs.map((ev, i) => {
            const color = PALETTE[ev.milestoneIndex % PALETTE.length];
            return (
              <li key={i} style={{ borderLeftColor: color }}>
                <span className="badge">{ev.milestoneTitle}</span>
                <span>{ev.step}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
