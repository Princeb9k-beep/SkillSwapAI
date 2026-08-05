// Reusable UI-state primitives (loading / error / empty) — the consistent set of
// states ui-ux-pro-max recommends every data view should render.

import { Skeleton } from "./Skeleton.jsx";
import Icon from "./icons.jsx";

// Skeleton placeholder (replaces the old spinner) — reserves space and reads as
// "content is coming", which feels faster than a spinning circle.
export function LoadingState({ label = "Loading…" }) {
  return (
    <div className="state state-loading" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      <Skeleton w="70%" h="1rem" />
      <Skeleton w="55%" h="1rem" style={{ marginTop: "0.6rem" }} />
      <Skeleton w="62%" h="1rem" style={{ marginTop: "0.6rem" }} />
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

// A friendly cold-start state. `icon` is a line-icon name (see icons.jsx) shown
// in a soft badge; `children` holds one or more call-to-action buttons that give
// a brand-new user an obvious next move instead of a dead end.
export function EmptyState({ icon, title, hint, children }) {
  return (
    <div className="state state-empty">
      {icon && (
        <div className="state-empty-icon" aria-hidden="true">
          <Icon name={icon} size={26} />
        </div>
      )}
      <h3>{title}</h3>
      {hint && <p className="muted">{hint}</p>}
      {children && <div className="state-action">{children}</div>}
    </div>
  );
}
