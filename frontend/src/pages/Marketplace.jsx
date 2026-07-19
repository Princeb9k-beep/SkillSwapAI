// Marketplace (spec §3.7): list paid tutoring/courses/templates, book them, and
// track orders. Payment capture is not wired yet (needs Stripe) — bookings are
// recorded as requests and a banner makes that explicit.

import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const money = (cents) => `$${(cents / 100).toFixed(2)}`;
const KINDS = ["tutoring", "coaching", "course", "template"];

function CreateListing({ onCreated }) {
  const { notify } = useApp();
  const [form, setForm] = useState({ title: "", kind: "tutoring", description: "", price: "" });
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.createListing({
        title: form.title,
        kind: form.kind,
        description: form.description || null,
        price_cents: Math.round(parseFloat(form.price || "0") * 100),
      });
      setForm({ title: "", kind: "tutoring", description: "", price: "" });
      notify("Listing published", "success");
      onCreated();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h3>Offer a service</h3>
      <label>
        Title
        <input
          required
          value={form.title}
          placeholder="1-on-1 Python tutoring"
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
        />
      </label>
      <label>
        Type
        <select
          value={form.kind}
          onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value }))}
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {k[0].toUpperCase() + k.slice(1)}
            </option>
          ))}
        </select>
      </label>
      <label>
        Price (USD)
        <input
          required
          type="number"
          min="0"
          step="0.01"
          inputMode="decimal"
          value={form.price}
          placeholder="50.00"
          onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
        />
      </label>
      <label>
        Description
        <textarea
          rows={2}
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
        />
      </label>
      <button className="btn btn-primary" disabled={busy} aria-busy={busy}>
        {busy ? "Publishing…" : "Publish listing"}
      </button>
    </form>
  );
}

function OrderRow({ o, role, onUpdate }) {
  return (
    <div className="card order-row">
      <div className="row-between">
        <strong>{o.listing_title}</strong>
        <span className={`badge status-${o.status}`}>{o.status}</span>
      </div>
      <p className="muted">
        {money(o.price_cents)}
        {role === "seller" && ` · you net ${money(o.seller_net_cents)} (fee ${money(o.commission_cents)})`}
      </p>
      <div className="community-actions">
        {role === "seller" && o.status === "requested" && (
          <button className="btn btn-primary" onClick={() => onUpdate(o.id, "confirmed")}>
            Confirm
          </button>
        )}
        {role === "seller" && o.status === "confirmed" && (
          <button className="btn btn-primary" onClick={() => onUpdate(o.id, "completed")}>
            Mark completed
          </button>
        )}
        {role === "buyer" && o.status === "requested" && (
          <button className="btn btn-danger" onClick={() => onUpdate(o.id, "cancelled")}>
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

export default function Marketplace() {
  const { notify } = useApp();
  const [listings, setListings] = useState([]);
  const [orders, setOrders] = useState({ as_buyer: [], as_seller: [] });
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const [l, o] = await Promise.all([api.getListings(), api.getOrders()]);
      setListings(l);
      setOrders(o);
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function book(id) {
    try {
      await api.bookListing(id);
      notify("Booked — payment isn't enabled yet; the seller will confirm.", "info");
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  async function updateOrder(id, s) {
    try {
      await api.updateOrder(id, s);
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (status === "loading") return <SkeletonPage cards={3} label="Loading marketplace…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>Marketplace</h1>
      <div className="card notice">
        Payments aren't enabled yet — bookings are recorded as requests. Connect a
        payment provider (e.g. Stripe) to charge cards. A 15% platform fee applies.
      </div>

      <CreateListing onCreated={load} />

      <h2>Browse</h2>
      {listings.length === 0 ? (
        <EmptyState title="No listings yet" hint="Offer a service above to get started." />
      ) : (
        <div className="grid">
          {listings.map((l) => (
            <article className="card listing-card" key={l.id}>
              <span className="badge">{l.kind}</span>
              <h3>{l.title}</h3>
              {l.description && <p className="muted">{l.description}</p>}
              <p className="listing-price">{money(l.price_cents)}</p>
              <p className="muted">by {l.seller_name}</p>
              <button className="btn btn-primary" onClick={() => book(l.id)}>
                Book
              </button>
            </article>
          ))}
        </div>
      )}

      {(orders.as_buyer.length > 0 || orders.as_seller.length > 0) && (
        <>
          <h2>Your orders</h2>
          {orders.as_seller.length > 0 && (
            <>
              <h3>Selling</h3>
              {orders.as_seller.map((o) => (
                <OrderRow key={`s${o.id}`} o={o} role="seller" onUpdate={updateOrder} />
              ))}
            </>
          )}
          {orders.as_buyer.length > 0 && (
            <>
              <h3>Buying</h3>
              {orders.as_buyer.map((o) => (
                <OrderRow key={`b${o.id}`} o={o} role="buyer" onUpdate={updateOrder} />
              ))}
            </>
          )}
        </>
      )}
    </section>
  );
}
