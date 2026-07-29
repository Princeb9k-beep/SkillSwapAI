// Learning buddies: a shared streak that grows only when both partners check in.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

export default function Buddies() {
  const { notify } = useApp();
  const [list, setList] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setList(await api.buddies());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function act(fn, id, okMsg) {
    try {
      const res = await fn(id);
      if (res?.message || okMsg) notify(res?.message || okMsg, "success");
      load();
    } catch (err) {
      notify(err.message, "error");
    }
  }

  if (status === "loading") return <SkeletonPage cards={2} label="Loading buddies…" />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>Learning buddies</h1>
      <p className="muted">
        Team up with a partner and keep a shared streak alive — it only grows on days
        you <em>both</em> check in. Invite someone from their profile.
      </p>

      {list.length === 0 ? (
        <EmptyState icon="🤝" title="No buddies yet" hint="Team up with someone to keep a shared streak alive. Find a partner, then add them as a learning buddy from their profile.">
          <Link className="btn btn-primary" to="/matches">Find a partner</Link>
        </EmptyState>
      ) : (
        <div className="grid">
          {list.map((b) => (
            <div className="card buddy-card" key={b.id}>
              <div className="row-between">
                <h3><Link className="lb-name" to={`/u/${b.partner_id}`}>{b.partner_name}</Link></h3>
                <span className="buddy-streak">{b.streak}🔥</span>
              </div>

              {b.status === "pending" ? (
                b.is_inviter ? (
                  <p className="muted">Waiting for {b.partner_name} to accept…</p>
                ) : (
                  <div className="community-actions">
                    <button className="btn btn-primary" onClick={() => act(api.acceptBuddy, b.id, "You're buddies!")}>
                      Accept
                    </button>
                    <button className="btn" onClick={() => act(api.endBuddy, b.id, "Declined")}>
                      Decline
                    </button>
                  </div>
                )
              ) : (
                <>
                  <p className="muted">
                    {b.i_checked_in ? "You've checked in today ✓" : "You haven't checked in today"} ·{" "}
                    {b.partner_checked_in ? `${b.partner_name} has ✓` : `${b.partner_name} hasn't yet`}
                  </p>
                  <div className="community-actions">
                    <button
                      className="btn btn-primary"
                      disabled={b.i_checked_in}
                      onClick={() => act(api.buddyCheckin, b.id)}
                    >
                      {b.i_checked_in ? "Checked in" : "Check in"}
                    </button>
                    <button className="btn" onClick={() => act(api.endBuddy, b.id, "Ended")}>
                      End
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
