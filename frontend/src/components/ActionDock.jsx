// The "Create" action dock — a TikTok-style bottom sheet of quick-create
// actions, opened from the center "+" in the bottom nav (and the desktop nav).
// Each action routes to the page where that thing gets made.

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { CREATE_ACTIONS } from "./navGroups.jsx";

export default function ActionDock({ open, onClose }) {
  const navigate = useNavigate();

  // Close on Escape and lock body scroll while the sheet is open.
  useEffect(() => {
    if (!open) return;
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  function go(to) {
    onClose();
    navigate(to);
  }

  return (
    <div className="dock-overlay" role="dialog" aria-modal="true" aria-label="Create">
      <div className="dock-scrim" onClick={onClose} />
      <div className="dock-sheet">
        <div className="dock-handle" aria-hidden="true" />
        <h2 className="dock-title">Create</h2>
        <p className="dock-sub muted">Start something new — one tap from anywhere.</p>
        <div className="dock-actions">
          {CREATE_ACTIONS.map((a) => (
            <button key={a.to + a.label} type="button" className="dock-action" onClick={() => go(a.to)}>
              <span className="dock-action-emoji" aria-hidden="true">{a.emoji}</span>
              <span className="dock-action-body">
                <span className="dock-action-label">{a.label}</span>
                <span className="dock-action-desc muted">{a.desc}</span>
              </span>
            </button>
          ))}
        </div>
        <button type="button" className="btn dock-close" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
