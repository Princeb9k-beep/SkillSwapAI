// Single source of truth for the app's five-section navigation
// (TikTok/Instagram-style): four hub destinations — AI Hub, Learn, Connect,
// Grow — flank a center "Create" action dock. Both the mobile BottomNav and the
// desktop Nav derive from this, and each hub page renders its group's `links` as
// a card grid, so navigation never drifts apart.
//
// Control icons are inline SVG (inherit currentColor); hub cards use an `emoji`
// + `desc` for a richer, scannable grid.

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

// The four hub groups. Each `to` is the hub landing page; each link is a card.
export const NAV_GROUPS = [
  {
    key: "ai",
    label: "AI Hub",
    to: "/",
    end: true,
    Icon: AiIcon,
    tagline: "Your AI copilots and instant tools.",
    links: [
      { to: "/coach", label: "Coach", emoji: "🧠", desc: "Ask anything, get a study plan." },
      { to: "/twin", label: "AI Twin", emoji: "👤", desc: "Your teaching style, distilled.", plan: "pro" },
      { to: "/scanner", label: "Scanner", emoji: "🔍", desc: "Upload a resume or code for feedback." },
      { to: "/translate", label: "Translate", emoji: "🌐", desc: "Explain anything in plain language." },
    ],
  },
  {
    key: "learn",
    label: "Learn",
    to: "/learn",
    Icon: LearnIcon,
    tagline: "Your learning stream, gamified.",
    links: [
      { to: "/academy", label: "Academy", emoji: "🎓", desc: "Structured courses toward your goal.", plan: "pro" },
      { to: "/dashboard", label: "Dashboard", emoji: "📊", desc: "Your roadmap at a glance." },
      { to: "/lessons", label: "Lessons", emoji: "📖", desc: "AI-written daily lessons." },
      { to: "/flashcards", label: "Flashcards", emoji: "🃏", desc: "Spaced-repetition review." },
      { to: "/challenges", label: "Challenges", emoji: "⚡", desc: "Daily practice challenges." },
      { to: "/progress", label: "Progress", emoji: "🔥", desc: "Streaks, goals, and leagues." },
      { to: "/buddies", label: "Buddies", emoji: "🤝", desc: "Keep a shared streak alive." },
    ],
  },
  {
    key: "connect",
    label: "Connect",
    to: "/connect",
    Icon: ConnectIcon,
    tagline: "Meet partners and learn together.",
    links: [
      { to: "/matches", label: "Matches", emoji: "🧭", desc: "Find complementary partners." },
      { to: "/messages", label: "Messages", emoji: "💬", desc: "Chat with your partners." },
      { to: "/feed", label: "Activity", emoji: "📣", desc: "See the community's wins." },
      { to: "/rooms", label: "Rooms", emoji: "🎥", desc: "Live video practice rooms.", plan: "pro" },
      { to: "/community", label: "Community", emoji: "🌱", desc: "Topic-based groups." },
      { to: "/meetups", label: "Meetups", emoji: "📅", desc: "Group study sessions." },
      { to: "/sessions", label: "Sessions", emoji: "📆", desc: "Book 1-on-1 practice." },
      { to: "/search", label: "Search", emoji: "🔎", desc: "Find people and skills." },
    ],
  },
  {
    key: "grow",
    label: "Grow",
    to: "/grow",
    Icon: GrowIcon,
    tagline: "Level up your career and reach.",
    links: [
      { to: "/career", label: "Career", emoji: "💼", desc: "Resume, portfolio, interviews.", plan: "pro" },
      { to: "/market", label: "Market", emoji: "🏷️", desc: "Offer and book paid services." },
      { to: "/partners", label: "Partners", emoji: "🤝", desc: "Your ongoing partnerships." },
      { to: "/verify", label: "Verify", emoji: "✅", desc: "Prove your skills.", plan: "elite" },
      { to: "/plans", label: "Plans", emoji: "⭐", desc: "Upgrade to Pro or Elite." },
      { to: "/settings", label: "Settings", emoji: "⚙️", desc: "Account and preferences." },
    ],
  },
];

// The center "Create" slot opens the Action Dock (a bottom sheet), not a route.
export const CREATE_SLOT = { key: "create", label: "Create", Icon: CreateIcon };

// Quick-create actions shown in the Action Dock. Each links to the page where
// that thing gets made, so "Create" is one tap from any screen.
export const CREATE_ACTIONS = [
  { to: "/goal", emoji: "🎯", label: "Set a new goal", desc: "Generate a roadmap toward it." },
  { to: "/coach", emoji: "✨", label: "Launch an AI workflow", desc: "Coach, plan, or feedback." },
  { to: "/challenges", emoji: "⚡", label: "Take a challenge", desc: "Practice something new today." },
  { to: "/flashcards", emoji: "🃏", label: "Make a flashcard set", desc: "Turn a topic into review cards." },
  { to: "/meetups", emoji: "📅", label: "Host a meetup", desc: "Rally people around a topic." },
  { to: "/sessions", emoji: "📆", label: "Book a session", desc: "Schedule 1-on-1 practice." },
  { to: "/market", emoji: "🏷️", label: "Offer a service", desc: "List a paid skill on the market." },
];

// Convenience: hub destinations in bottom-nav order (Create sits in the middle).
export const HUBS = NAV_GROUPS.map(({ key, label, to, end, Icon }) => ({
  key,
  label,
  to,
  end,
  Icon,
}));
