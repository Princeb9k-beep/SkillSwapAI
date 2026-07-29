// Mobile app-style bottom navigation (TikTok/Instagram five-slot layout):
// AI Hub · Learn · [Create] · Connect · Grow. The four hubs are direct links to
// their landing pages; the raised center button opens the Create action dock.
// Hidden on desktop (see CSS), where the top bar carries the same destinations.

import { NavLink } from "react-router-dom";
import { HUBS, CREATE_SLOT } from "./navGroups.jsx";

export default function BottomNav({ onCreate }) {
  // Render order: first two hubs, the center Create, then the last two hubs.
  const left = HUBS.slice(0, 2);
  const right = HUBS.slice(2);

  function HubButton({ hub }) {
    const { Icon } = hub;
    return (
      <NavLink
        to={hub.to}
        end={hub.end}
        className={({ isActive }) => `bottomnav-item${isActive ? " active" : ""}`}
      >
        <Icon />
        <span>{hub.label}</span>
      </NavLink>
    );
  }

  return (
    <nav className="bottomnav" aria-label="Primary">
      {left.map((h) => (
        <HubButton key={h.key} hub={h} />
      ))}

      <button
        type="button"
        className="bottomnav-create"
        aria-label="Create"
        onClick={onCreate}
      >
        <CREATE_SLOT.Icon />
      </button>

      {right.map((h) => (
        <HubButton key={h.key} hub={h} />
      ))}
    </nav>
  );
}
