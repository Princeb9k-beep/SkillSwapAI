// Reusable UI-state primitives (loading / error / empty) — the consistent set of
// states ui-ux-pro-max recommends every data view should render.

export function LoadingState({ label = "Loading…" }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function ErrorBanner({ message, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <p>{message}</p>
      {onRetry && (
        <button className="btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, hint }) {
  return (
    <div className="state">
      <h3>{title}</h3>
      {hint && <p className="muted">{hint}</p>}
    </div>
  );
}
