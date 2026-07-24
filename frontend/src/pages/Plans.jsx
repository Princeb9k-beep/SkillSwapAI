// Plans & pricing: the 3-tier subscription page (Free / Pro / Elite). Upgrades
// apply immediately (payment is stubbed like the rest of the app).

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const price = (cents) => (cents === 0 ? "$0" : `$${(cents / 100).toFixed(0)}`);
const per = (cents) => (cents === 0 ? "forever" : "month");
const fmt = (n) => n.toLocaleString();

// AI-token wallet: current balance, monthly allowance, and buyable top-ups.
function TokenWallet() {
  const { notify } = useApp();
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading");
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setData(await api.aiTokens());
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function buy(pack) {
    setBusy(pack.id);
    try {
      const res = await api.buyTokens(pack.id);
      setData((d) => ({ ...d, wallet: res.wallet }));
      notify(res.message || "Tokens added", "success");
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(null);
    }
  }

  if (status !== "ready" || !data) return null;
  const { wallet, packs } = data;
  const pct =
    wallet.unlimited || !wallet.allowance
      ? 0
      : Math.round((wallet.allowance_used / wallet.allowance) * 100);

  return (
    <div className="card token-wallet">
      <div className="row-between">
        <h3>AI tokens</h3>
        <span className="token-balance">
          {wallet.unlimited ? "Unlimited" : fmt(wallet.balance)}
        </span>
      </div>
      <p className="field-hint">
        Every AI action — Coach, Scanner, Translate and more — costs 1 token.
      </p>

      {wallet.unlimited ? (
        <p className="muted">Your Elite plan includes unlimited AI tokens. 🎉</p>
      ) : (
        <>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <p className="muted token-breakdown">
            {fmt(wallet.allowance_remaining)} of {fmt(wallet.allowance)} monthly tokens left
            {wallet.purchased > 0 && ` · +${fmt(wallet.purchased)} top-up`}
          </p>

          <p className="field-hint token-buy-title">Need more? Buy a top-up:</p>
          <div className="token-packs">
            {packs.map((p) => (
              <button
                key={p.id}
                type="button"
                className="btn token-pack"
                disabled={busy === p.id}
                onClick={() => buy(p)}
              >
                <span className="token-pack-amt">+{fmt(p.tokens)}</span>
                <span className="muted">{price(p.price_cents)}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Check() {
  return (
    <svg className="plan-check" width="18" height="18" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

export default function Plans() {
  const { user, updateUser, notify } = useApp();
  const [plans, setPlans] = useState([]);
  const [current, setCurrent] = useState(user?.tier || "free");
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const data = await api.billingPlans();
      setPlans(data.plans);
      setCurrent(data.current);
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function choose(tier) {
    if (tier === current) return;
    setBusy(tier);
    try {
      const res = await api.subscribe(tier);
      setCurrent(tier);
      updateUser({ tier });
      notify(res.message || "Plan updated", "success");
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(null);
    }
  }

  if (status === "loading") return <SkeletonPage cards={3} label="Loading plans…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  const isAdmin = user?.is_admin;

  return (
    <section className="plans">
      <h1>Plans &amp; pricing</h1>
      <p className="muted">
        Start free and level up when you're ready. Messaging, community, meetups, and daily
        learning are always free — paid plans unlock the AI tools, video rooms, and the full
        Skill Academy.
      </p>
      {isAdmin && (
        <p className="field-hint">You're an admin — treated as Elite for testing regardless of the plan below.</p>
      )}

      <div className="plan-grid">
        {plans.map((p) => {
          const isCurrent = p.tier === current;
          return (
            <article key={p.tier} className={`card plan-card${p.popular ? " popular" : ""}${isCurrent ? " current" : ""}`}>
              {p.popular && <span className="plan-ribbon">Most popular</span>}
              <div className="plan-name">{p.name}</div>
              <div className="plan-price">
                <span className="plan-amt">{price(p.price_cents)}</span>
                <span className="plan-per">/ {per(p.price_cents)}</span>
              </div>
              <p className="plan-tagline">{p.tagline}</p>
              <button
                className={`btn ${p.popular ? "btn-primary" : ""} plan-cta`}
                disabled={isCurrent || busy === p.tier}
                onClick={() => choose(p.tier)}
              >
                {isCurrent
                  ? "Current plan"
                  : busy === p.tier
                    ? "Updating…"
                    : p.tier === "free"
                      ? "Downgrade to Free"
                      : `Choose ${p.name}`}
              </button>
              <ul className="plan-feats">
                {p.features.map((f, i) => (
                  <li key={i}>
                    <Check />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </article>
          );
        })}
      </div>

      {/* Remount on plan change so the allowance reflects the new tier. */}
      <TokenWallet key={current} />

      <p className="field-hint plans-foot">
        Upgrades apply instantly. Payments are not charged yet (Stripe checkout is a planned
        add-on) — you can switch plans freely.
      </p>
    </section>
  );
}
