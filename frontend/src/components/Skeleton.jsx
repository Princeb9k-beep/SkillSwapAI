// Skeleton loading placeholders — shown while data loads instead of a spinner,
// so the layout is reserved and perceived speed improves (less layout shift).

export function Skeleton({ w = "100%", h = "1rem", radius, style }) {
  return (
    <span
      className="skeleton"
      aria-hidden="true"
      style={{ width: w, height: h, borderRadius: radius, ...style }}
    />
  );
}

// A card shaped like a roadmap milestone / lesson card.
export function SkeletonCard() {
  return (
    <div className="card" aria-hidden="true">
      <Skeleton w="70px" h="1.1rem" radius="999px" />
      <Skeleton w="60%" h="1.3rem" style={{ marginTop: "0.75rem" }} />
      <Skeleton w="40%" h="0.9rem" style={{ marginTop: "0.5rem" }} />
      <Skeleton w="90%" h="0.9rem" style={{ marginTop: "0.9rem" }} />
      <Skeleton w="80%" h="0.9rem" style={{ marginTop: "0.4rem" }} />
    </div>
  );
}

// A full-page loading skeleton (heading + a grid of cards).
export function SkeletonPage({ cards = 3, label = "Loading…" }) {
  return (
    <section role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}</span>
      <Skeleton w="220px" h="2rem" />
      <Skeleton w="55%" h="1rem" style={{ marginTop: "0.75rem" }} />
      <div className="grid" style={{ marginTop: "1.25rem" }}>
        {Array.from({ length: cards }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </section>
  );
}
