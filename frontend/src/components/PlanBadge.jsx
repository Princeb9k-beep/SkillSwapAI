// Tiny "PRO" / "ELITE" tag shown next to nav tabs that require a paid plan, so
// it's obvious at a glance which features are gated and at what tier.

export default function PlanBadge({ plan }) {
  if (plan !== "pro" && plan !== "elite") return null;
  return (
    <span className={`plan-badge plan-badge-${plan}`} aria-label={`${plan} feature`}>
      {plan === "elite" ? "ELITE" : "PRO"}
    </span>
  );
}
