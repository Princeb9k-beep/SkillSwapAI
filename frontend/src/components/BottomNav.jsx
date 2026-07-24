// Mobile app-style bottom navigation (spec: 5-slot nav). Four category groups
// flank a raised center "+" that opens goal/plan creation. Tapping a group pops
// a sheet listing that group's tabs. Hidden on desktop (see CSS), where the top
// bar shows every tab inline.

import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { NAV_GROUPS, CREATE_SLOT } from "./navGroups.jsx";
import PlanBadge from "./PlanBadge.jsx";

export default function BottomNav() {
  const location = useLocation();
  const [openKey, setOpenKey] = useState(null);

  // Close the sheet whenever the route changes (a link was followed).
  useEffect(() => {
    setOpenKey(null);
  }, [location.pathname]);

  const activeGroupKey = NAV_GROUPS.find((g) =>
    g.links.some((l) => l.to === location.pathname),
  )?.key;

  // Render order: first two groups, the center "+", then the last two groups.
  const left = NAV_GROUPS.slice(0, 2);
  const right = NAV_GROUPS.slice(2);
  const openGroup = NAV_GROUPS.find((g) => g.key === openKey);

  function GroupButton({ group }) {
    const { Icon } = group;
    const isOpen = openKey === group.key;
    const isActive = activeGroupKey === group.key;
    return (
      <button
        type="button"
        className={`bottomnav-item${isActive ? " active" : ""}${isOpen ? " open" : ""}`}
        aria-haspopup="true"
        aria-expanded={isOpen}
        onClick={() => setOpenKey((k) => (k === group.key ? null : group.key))}
      >
        <Icon />
        <span>{group.label}</span>
      </button>
    );
  }

  return (
    <>
      {openGroup && (
        <>
          <div className="bottomnav-scrim" onClick={() => setOpenKey(null)} />
          <div className="bottomnav-sheet" role="menu" aria-label={openGroup.label}>
            <p className="bottomnav-sheet-title">{openGroup.label}</p>
            {openGroup.links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                role="menuitem"
                className="bottomnav-sheet-link"
                onClick={() => setOpenKey(null)}
              >
                <span>{l.label}</span>
                <PlanBadge plan={l.plan} />
              </NavLink>
            ))}
          </div>
        </>
      )}

      <nav className="bottomnav" aria-label="Primary">
        {left.map((g) => (
          <GroupButton key={g.key} group={g} />
        ))}

        <NavLink
          to={CREATE_SLOT.to}
          end
          className="bottomnav-create"
          aria-label="Create a goal or plan"
          onClick={() => setOpenKey(null)}
        >
          <CREATE_SLOT.Icon />
        </NavLink>

        {right.map((g) => (
          <GroupButton key={g.key} group={g} />
        ))}
      </nav>
    </>
  );
}
