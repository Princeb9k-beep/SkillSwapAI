// Single source of truth for how the app's tabs are organized into the five
// bottom-navigation slots (spec: mobile app-style nav). Four category groups
// plus a center "Create" (+) slot that jumps to goal/plan creation.
//
// Icons are inline SVG (no emoji for controls) and inherit currentColor.

function Icon({ children, ...rest }) {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

const AiIcon = () => (
  <Icon>
    <path d="M12 3l1.6 4.6L18 9.2l-4.4 1.6L12 15l-1.6-4.2L6 9.2l4.4-1.6L12 3z" />
    <path d="M18 14l.8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8L18 14z" />
  </Icon>
);
const LearnIcon = () => (
  <Icon>
    <path d="M4 5a2 2 0 0 1 2-2h6v16H6a2 2 0 0 0-2 2V5z" />
    <path d="M20 5a2 2 0 0 0-2-2h-6v16h6a2 2 0 0 1 2 2V5z" />
  </Icon>
);
const CreateIcon = () => (
  <Icon strokeWidth="2.5">
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </Icon>
);
const ConnectIcon = () => (
  <Icon>
    <circle cx="9" cy="8" r="3" />
    <path d="M3 20a6 6 0 0 1 12 0" />
    <path d="M16 6a3 3 0 0 1 0 6" />
    <path d="M18 14a6 6 0 0 1 3 6" />
  </Icon>
);
const GrowIcon = () => (
  <Icon>
    <path d="M3 17l6-6 4 4 7-7" />
    <path d="M14 8h6v6" />
  </Icon>
);

// The four category groups (left → right around the center "+").
export const NAV_GROUPS = [
  {
    key: "ai",
    label: "AI",
    Icon: AiIcon,
    links: [
      { to: "/coach", label: "Coach" },
      { to: "/twin", label: "AI Twin" },
      { to: "/scanner", label: "Scanner" },
      { to: "/translate", label: "Translate" },
    ],
  },
  {
    key: "learn",
    label: "Learn",
    Icon: LearnIcon,
    links: [
      { to: "/dashboard", label: "Dashboard" },
      { to: "/lessons", label: "Lessons" },
      { to: "/challenges", label: "Challenges" },
      { to: "/progress", label: "Progress" },
    ],
  },
  {
    key: "connect",
    label: "Connect",
    Icon: ConnectIcon,
    links: [
      { to: "/matches", label: "Matches" },
      { to: "/messages", label: "Messages" },
      { to: "/rooms", label: "Rooms" },
      { to: "/community", label: "Community" },
      { to: "/meetups", label: "Meetups" },
    ],
  },
  {
    key: "grow",
    label: "Grow",
    Icon: GrowIcon,
    links: [
      { to: "/career", label: "Career" },
      { to: "/market", label: "Market" },
      { to: "/partners", label: "Partners" },
      { to: "/verify", label: "Verify" },
      { to: "/settings", label: "Settings" },
    ],
  },
];

// The center "+" slot: where you create goals and plans.
export const CREATE_SLOT = { to: "/", label: "Create", Icon: CreateIcon };
