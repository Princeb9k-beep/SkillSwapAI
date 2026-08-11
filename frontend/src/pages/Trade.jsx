// Trade Desk — the day-trading cockpit.
//
// A chart-first workspace (TradingView-style schematic, drawn as dependency-free
// inline SVG so it themes with the app and adds no bundle weight) wrapped in the
// things that make it "special": a paper account you actually trade, an AI read
// of the chart, a natural-language screener, a risk-first position sizer, and a
// journal the AI coach reviews. Every execution mode routes through the same
// backend broker abstraction, so this UI is unchanged when live trading is on.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, LoadingState } from "../components/States.jsx";

const TIMEFRAMES = ["5m", "15m", "1h", "1d"];
const money = (n) =>
  n == null ? "—" : n.toLocaleString(undefined, { style: "currency", currency: "USD" });
const pct = (n) => (n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(2)}%`);

function sma(closes, period) {
  const out = Array(closes.length).fill(null);
  for (let i = period - 1; i < closes.length; i++) {
    let s = 0;
    for (let j = i - period + 1; j <= i; j++) s += closes[j];
    out[i] = s / period;
  }
  return out;
}

// --- Candlestick chart (pure SVG) ---------------------------------------
function CandleChart({ candles, levels }) {
  const W = 760;
  const H = 360;
  const padL = 6;
  const padR = 54; // room for the price axis
  const padT = 10;
  const volH = 46;
  const priceH = H - volH - padT - 14;

  const view = useMemo(() => {
    if (!candles?.length) return null;
    const highs = candles.map((c) => c.h);
    const lows = candles.map((c) => c.l);
    const closes = candles.map((c) => c.c);
    let hi = Math.max(...highs);
    let lo = Math.min(...lows);
    const levelVals = [levels?.support, levels?.resistance].filter((v) => v != null);
    for (const v of levelVals) {
      hi = Math.max(hi, v);
      lo = Math.min(lo, v);
    }
    const pad = (hi - lo) * 0.06 || 1;
    hi += pad;
    lo -= pad;
    const maxVol = Math.max(...candles.map((c) => c.v), 1);
    const n = candles.length;
    const plotW = W - padL - padR;
    const step = plotW / n;
    const bodyW = Math.max(1.2, step * 0.62);
    const x = (i) => padL + step * i + step / 2;
    const y = (p) => padT + (hi - p) * (priceH / (hi - lo));
    const vy = (v) => padT + priceH + 12 + (volH - (v / maxVol) * volH);
    return { hi, lo, n, step, bodyW, x, y, vy, closes, plotW };
  }, [candles, levels]);

  if (!view) return <div className="state state-empty">No chart data.</div>;

  const { x, y, vy, bodyW, closes } = view;
  const s20 = sma(closes, 20);
  const s50 = sma(closes, 50);
  const line = (arr) =>
    arr
      .map((v, i) => (v == null ? null : `${x(i)},${y(v)}`))
      .filter(Boolean)
      .join(" ");
  const axisTicks = 5;
  const ticks = Array.from({ length: axisTicks }, (_, k) => {
    const p = view.lo + ((view.hi - view.lo) * k) / (axisTicks - 1);
    return { p, y: y(p) };
  });

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      role="img"
      aria-label="Price candlestick chart"
      style={{ display: "block", background: "var(--surface)", borderRadius: "var(--radius)" }}
    >
      {/* horizontal gridlines + price axis */}
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={W - padR} y1={t.y} y2={t.y} stroke="var(--border)" strokeWidth="1" opacity="0.5" />
          <text x={W - padR + 4} y={t.y + 3} fontSize="10" fill="var(--muted)">
            {t.p.toFixed(2)}
          </text>
        </g>
      ))}

      {/* support / resistance */}
      {levels?.support != null && (
        <line x1={padL} x2={W - padR} y1={y(levels.support)} y2={y(levels.support)}
          stroke="var(--success)" strokeWidth="1" strokeDasharray="5 4" opacity="0.8" />
      )}
      {levels?.resistance != null && (
        <line x1={padL} x2={W - padR} y1={y(levels.resistance)} y2={y(levels.resistance)}
          stroke="var(--error)" strokeWidth="1" strokeDasharray="5 4" opacity="0.8" />
      )}

      {/* candles */}
      {candles.map((c, i) => {
        const up = c.c >= c.o;
        const col = up ? "#16a34a" : "#dc2626";
        const bodyTop = y(Math.max(c.o, c.c));
        const bodyBot = y(Math.min(c.o, c.c));
        return (
          <g key={i}>
            <line x1={x(i)} x2={x(i)} y1={y(c.h)} y2={y(c.l)} stroke={col} strokeWidth="1" />
            <rect x={x(i) - bodyW / 2} y={bodyTop} width={bodyW} height={Math.max(1, bodyBot - bodyTop)} fill={col} />
            <rect x={x(i) - bodyW / 2} y={vy(c.v)} width={bodyW} height={padT + priceHVol(view) - vy(c.v)} fill={col} opacity="0.35" />
          </g>
        );
      })}

      {/* moving averages */}
      <polyline points={line(s20)} fill="none" stroke="#f59e0b" strokeWidth="1.5" opacity="0.9" />
      <polyline points={line(s50)} fill="none" stroke="#3b82f6" strokeWidth="1.5" opacity="0.9" />
    </svg>
  );

  function priceHVol() {
    return H - volH - padT - 14 + 12 + volH; // bottom of the volume strip
  }
}

// --- Small UI helpers ----------------------------------------------------
function Stat({ label, value, tone }) {
  const color = tone === "up" ? "#16a34a" : tone === "down" ? "#dc2626" : "var(--text)";
  return (
    <div style={{ minWidth: 90 }}>
      <div className="muted" style={{ fontSize: ".72rem", textTransform: "uppercase", letterSpacing: ".04em" }}>{label}</div>
      <div style={{ fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function BiasChip({ bias }) {
  const map = { bullish: "#16a34a", bearish: "#dc2626", neutral: "var(--muted)" };
  return (
    <span style={{
      background: map[bias] || "var(--muted)", color: "#fff", borderRadius: 999,
      padding: "2px 12px", fontWeight: 700, fontSize: ".8rem", textTransform: "capitalize",
    }}>{bias}</span>
  );
}

export default function Trade() {
  const { notify } = useApp();
  const [symbol, setSymbol] = useState("AAPL");
  const [symbolInput, setSymbolInput] = useState("AAPL");
  const [timeframe, setTimeframe] = useState("1d");
  const [candles, setCandles] = useState(null);
  const [quote, setQuote] = useState(null);
  const [account, setAccount] = useState(null);
  const [watch, setWatch] = useState({ symbols: [], quotes: [] });
  const [analysis, setAnalysis] = useState(null);
  const [tab, setTab] = useState("chart");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  const loadChart = useCallback(async (sym, tf) => {
    setLoading(true);
    setError(null);
    setAnalysis(null);
    try {
      const [c, q] = await Promise.all([api.tradeCandles(sym, tf, 120), api.tradeQuote(sym)]);
      setCandles(c.candles);
      setQuote(q);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAccount = useCallback(async () => {
    try {
      setAccount(await api.tradeAccount());
    } catch (err) {
      notify(err.message, "error");
    }
  }, [notify]);

  const loadWatch = useCallback(async () => {
    try {
      setWatch(await api.tradeWatchlist());
    } catch {
      /* non-fatal */
    }
  }, []);

  useEffect(() => {
    loadChart(symbol, timeframe);
  }, [symbol, timeframe, loadChart]);
  useEffect(() => {
    loadAccount();
    loadWatch();
  }, [loadAccount, loadWatch]);

  function pickSymbol(sym) {
    const s = sym.trim().toUpperCase();
    if (!s) return;
    setSymbol(s);
    setSymbolInput(s);
    setTab("chart");
  }

  async function runAnalyze() {
    setAnalyzing(true);
    try {
      setAnalysis(await api.tradeAnalyze(symbol, timeframe));
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <section>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "baseline", justifyContent: "space-between" }}>
        <h1 style={{ marginBottom: 0 }}>Trade Desk</h1>
        {account && (
          <div style={{ display: "flex", gap: 18 }}>
            <Stat label="Cash" value={money(account.cash)} />
            <Stat label="Equity" value={money(account.equity)} />
            <Stat label="Mode" value={account.live_trading_enabled ? "Live-ready" : "Paper"} />
          </div>
        )}
      </div>
      <p className="muted" style={{ marginTop: 4 }}>
        Practice with virtual money on real-shaped market data. Educational only — not financial advice.
      </p>

      {/* symbol + timeframe controls */}
      <form
        className="card"
        onSubmit={(e) => { e.preventDefault(); pickSymbol(symbolInput); }}
        style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}
      >
        <input
          value={symbolInput}
          onChange={(e) => setSymbolInput(e.target.value.toUpperCase())}
          placeholder="Symbol (AAPL, BTC/USD…)"
          aria-label="Symbol"
          style={{ maxWidth: 180 }}
        />
        <button className="btn btn-primary" type="submit">Load</button>
        <div style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              type="button"
              className={`btn ${tf === timeframe ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setTimeframe(tf)}
              style={{ padding: "4px 10px" }}
            >{tf}</button>
          ))}
        </div>
      </form>

      {/* tab bar */}
      <div style={{ display: "flex", gap: 6, margin: "14px 0", flexWrap: "wrap" }}>
        {[["chart", "Chart & Trade"], ["screen", "Screener"], ["journal", "Journal"], ["learn", "Academy"]].map(([k, label]) => (
          <button key={k} className={`btn ${tab === k ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "chart" && (
        <div className="trade-grid" style={{ display: "grid", gap: 16, gridTemplateColumns: "minmax(0, 2.2fr) minmax(240px, 1fr)" }}>
          <div>
            {/* quote header */}
            {quote && (
              <div style={{ display: "flex", gap: 20, alignItems: "baseline", marginBottom: 8 }}>
                <strong style={{ fontSize: "1.4rem" }}>{quote.symbol}</strong>
                <span style={{ fontSize: "1.4rem", fontWeight: 700 }}>{money(quote.price)}</span>
                <span style={{ color: quote.change >= 0 ? "#16a34a" : "#dc2626", fontWeight: 600 }}>
                  {quote.change >= 0 ? "▲" : "▼"} {pct(quote.change_pct)}
                </span>
              </div>
            )}
            {error && <ErrorBanner message={error} onRetry={() => loadChart(symbol, timeframe)} />}
            {loading ? <LoadingState label="Loading chart…" /> : (
              <>
                <CandleChart candles={candles} levels={analysis?.levels} />
                <div className="muted" style={{ fontSize: ".75rem", marginTop: 4, display: "flex", gap: 14 }}>
                  <span><span style={{ color: "#f59e0b" }}>—</span> SMA20</span>
                  <span><span style={{ color: "#3b82f6" }}>—</span> SMA50</span>
                  {analysis?.levels?.support != null && <span><span style={{ color: "#16a34a" }}>┈</span> support</span>}
                  {analysis?.levels?.resistance != null && <span><span style={{ color: "#dc2626" }}>┈</span> resistance</span>}
                </div>
              </>
            )}

            {/* AI analysis */}
            <div className="card" style={{ marginTop: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>AI read</h3>
                <button className="btn btn-primary" onClick={runAnalyze} disabled={analyzing} aria-busy={analyzing}>
                  {analyzing ? "Analyzing…" : "Analyze chart"}
                </button>
              </div>
              {analysis && (
                <div style={{ marginTop: 10 }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 8 }}>
                    <BiasChip bias={analysis.bias} />
                    <span className="muted">
                      RSI {analysis.indicators?.rsi14 ?? "—"} · trend {analysis.indicators?.trend ?? "—"}
                    </span>
                  </div>
                  <p>{analysis.summary}</p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginTop: 8 }}>
                    <Stat label="Support" value={money(analysis.levels?.support)} tone="up" />
                    <Stat label="Resistance" value={money(analysis.levels?.resistance)} tone="down" />
                    <Stat label="SMA20" value={money(analysis.indicators?.sma20)} />
                    <Stat label="SMA50" value={money(analysis.indicators?.sma50)} />
                    <Stat label="ATR14" value={analysis.indicators?.atr14 ?? "—"} />
                  </div>
                  <p className="muted" style={{ fontSize: ".72rem", marginTop: 8 }}>{analysis.disclaimer}</p>
                </div>
              )}
            </div>
          </div>

          {/* right rail: ticket + positions + watchlist + sizer */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <OrderTicket symbol={symbol} price={quote?.price} account={account} onFilled={(acct) => { setAccount(acct); }} notify={notify} />
            <Positions account={account} onPick={pickSymbol} onSold={loadAccount} notify={notify} />
            <PositionSizer defaultEquity={account?.equity} price={quote?.price} />
            <Watchlist watch={watch} current={symbol} onPick={pickSymbol} reload={loadWatch} notify={notify} />
          </div>
        </div>
      )}

      {tab === "screen" && <Screener universe={watch.symbols} onPick={pickSymbol} notify={notify} />}
      {tab === "journal" && <Journal notify={notify} defaultSymbol={symbol} />}
      {tab === "learn" && <Academy />}
    </section>
  );
}

// --- Order ticket --------------------------------------------------------
function OrderTicket({ symbol, price, account, onFilled, notify }) {
  const [qty, setQty] = useState(10);
  const [busy, setBusy] = useState(false);
  const cost = price ? price * (Number(qty) || 0) : null;
  const locked = account?.locked;

  async function submit(side) {
    if (!qty || qty <= 0) return;
    setBusy(true);
    try {
      const res = await api.tradeOrder(symbol, side, Number(qty));
      onFilled(res.account);
      notify(`${side === "buy" ? "Bought" : "Sold"} ${qty} ${symbol} @ ${money(res.order.price)}`, "success");
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Order ticket</h3>
      <div className="muted" style={{ fontSize: ".82rem", marginBottom: 8 }}>{symbol} @ {money(price)}</div>
      <label style={{ display: "block" }}>
        Quantity
        <input type="number" min="0" step="1" value={qty} onChange={(e) => setQty(e.target.value)} />
      </label>
      <div className="muted" style={{ fontSize: ".8rem", margin: "6px 0" }}>Est. cost {money(cost)}</div>
      {locked && <p style={{ color: "#dc2626", fontSize: ".8rem" }}>Account locked — daily loss limit hit.</p>}
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn" style={{ flex: 1, background: "#16a34a", color: "#fff" }} disabled={busy || locked} onClick={() => submit("buy")}>Buy</button>
        <button className="btn" style={{ flex: 1, background: "#dc2626", color: "#fff" }} disabled={busy || locked} onClick={() => submit("sell")}>Sell</button>
      </div>
    </div>
  );
}

// --- Positions -----------------------------------------------------------
function Positions({ account, onPick, onSold, notify }) {
  const positions = account?.positions || [];
  async function sellAll(p) {
    try {
      await api.tradeOrder(p.symbol, "sell", p.quantity);
      notify(`Closed ${p.symbol}`, "success");
      onSold();
    } catch (err) {
      notify(err.message, "error");
    }
  }
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Positions</h3>
      {positions.length === 0 ? (
        <p className="muted" style={{ fontSize: ".85rem" }}>No open positions yet.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {positions.map((p) => (
            <div key={p.symbol} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
              <button className="btn btn-ghost" style={{ padding: "2px 6px" }} onClick={() => onPick(p.symbol)}>
                <strong>{p.symbol}</strong> ×{p.quantity}
              </button>
              <span style={{ color: p.unrealized_pnl >= 0 ? "#16a34a" : "#dc2626", fontWeight: 600, fontSize: ".85rem" }}>
                {money(p.unrealized_pnl)} ({pct(p.unrealized_pct)})
              </span>
              <button className="btn" style={{ padding: "2px 8px" }} onClick={() => sellAll(p)}>Close</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Position sizer (risk guardrail) -------------------------------------
function PositionSizer({ defaultEquity, price }) {
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");
  const [risk, setRisk] = useState(1);
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (price && entry === "") setEntry(String(price));
  }, [price, entry]);

  async function compute(e) {
    e.preventDefault();
    setBusy(true);
    try {
      setPlan(await api.tradePositionSize({
        entry: Number(entry), stop: Number(stop), risk_pct: Number(risk),
        equity: defaultEquity || undefined,
      }));
    } catch {
      setPlan(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Position sizer</h3>
      <form onSubmit={compute} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <label>Entry<input type="number" step="0.01" value={entry} onChange={(e) => setEntry(e.target.value)} required /></label>
        <label>Stop<input type="number" step="0.01" value={stop} onChange={(e) => setStop(e.target.value)} required /></label>
        <label>Risk %<input type="number" step="0.1" value={risk} onChange={(e) => setRisk(e.target.value)} required /></label>
        <button className="btn btn-primary" style={{ alignSelf: "end" }} disabled={busy}>Size it</button>
      </form>
      {plan && (
        plan.valid ? (
          <div style={{ marginTop: 10 }}>
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              <Stat label="Shares" value={plan.shares} />
              <Stat label="Risk $" value={money(plan.risk_amount)} tone="down" />
              <Stat label="Notional" value={money(plan.notional)} />
              <Stat label="% equity" value={`${plan.pct_of_equity}%`} />
            </div>
            <div className="muted" style={{ fontSize: ".78rem", marginTop: 8 }}>
              Targets: {plan.targets.map((t) => `${t.r}R ${money(t.price)}`).join(" · ")}
            </div>
          </div>
        ) : (
          <p className="muted" style={{ fontSize: ".8rem", marginTop: 8 }}>{plan.reason}</p>
        )
      )}
    </div>
  );
}

// --- Watchlist -----------------------------------------------------------
function Watchlist({ watch, current, onPick, reload, notify }) {
  const [add, setAdd] = useState("");
  async function addSym(e) {
    e.preventDefault();
    if (!add.trim()) return;
    try {
      await api.tradeAddWatch(add.trim().toUpperCase());
      setAdd("");
      reload();
    } catch (err) {
      notify(err.message, "error");
    }
  }
  async function remove(sym) {
    try {
      await api.tradeRemoveWatch(sym);
      reload();
    } catch (err) {
      notify(err.message, "error");
    }
  }
  const quoteFor = (sym) => watch.quotes?.find((q) => q.symbol === sym);
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Watchlist</h3>
      <form onSubmit={addSym} style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        <input value={add} onChange={(e) => setAdd(e.target.value.toUpperCase())} placeholder="Add symbol" />
        <button className="btn btn-ghost" type="submit">+</button>
      </form>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {watch.symbols.map((sym) => {
          const q = quoteFor(sym);
          return (
            <div key={sym} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6,
              background: sym === current ? "var(--chip)" : "transparent", borderRadius: 8, padding: "2px 6px" }}>
              <button className="btn btn-ghost" style={{ padding: "2px 6px", flex: 1, textAlign: "left" }} onClick={() => onPick(sym)}>
                <strong>{sym}</strong>
              </button>
              {q && (
                <span style={{ fontSize: ".8rem", color: q.change >= 0 ? "#16a34a" : "#dc2626" }}>
                  {money(q.price)} {pct(q.change_pct)}
                </span>
              )}
              <button className="btn btn-ghost" style={{ padding: "0 6px" }} aria-label={`Remove ${sym}`} onClick={() => remove(sym)}>×</button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// --- Screener ------------------------------------------------------------
function Screener({ universe, onPick, notify }) {
  const [query, setQuery] = useState("oversold stocks in an uptrend");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  async function run(e) {
    e.preventDefault();
    setBusy(true);
    try {
      setRes(await api.tradeScreen(query, universe || []));
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Natural-language screener</h3>
        <p className="muted" style={{ fontSize: ".85rem" }}>
          Describe what you're looking for — e.g. “oversold names reclaiming the 200-day with momentum”.
        </p>
        <form onSubmit={run} style={{ display: "flex", gap: 8 }}>
          <input value={query} onChange={(e) => setQuery(e.target.value)} style={{ flex: 1 }} />
          <button className="btn btn-primary" disabled={busy}>{busy ? "Scanning…" : "Scan"}</button>
        </form>
      </div>
      {res && (
        <div className="card">
          <div className="muted" style={{ fontSize: ".8rem", marginBottom: 8 }}>
            {res.count} match{res.count === 1 ? "" : "es"} · filters: {JSON.stringify(res.filters)}
          </div>
          {res.results.length === 0 ? (
            <p className="muted">Nothing matched. Try broadening the query.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: ".9rem" }}>
                <thead>
                  <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                    <th style={{ padding: "4px 6px" }}>Symbol</th><th>Price</th><th>RSI</th><th>Trend</th><th>20d</th><th>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {res.results.map((r) => (
                    <tr key={r.symbol} style={{ borderTop: "1px solid var(--border)" }}>
                      <td style={{ padding: "4px 6px" }}>
                        <button className="btn btn-ghost" style={{ padding: "2px 6px" }} onClick={() => onPick(r.symbol)}><strong>{r.symbol}</strong></button>
                      </td>
                      <td>{money(r.price)}</td>
                      <td>{r.rsi14 ?? "—"}</td>
                      <td>{r.trend}</td>
                      <td style={{ color: r.change_pct_20 >= 0 ? "#16a34a" : "#dc2626" }}>{pct(r.change_pct_20)}</td>
                      <td>{r.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="muted" style={{ fontSize: ".72rem", marginTop: 8 }}>{res.disclaimer}</p>
        </div>
      )}
    </div>
  );
}

// --- Journal + AI coach --------------------------------------------------
function Journal({ notify, defaultSymbol }) {
  const [entries, setEntries] = useState(null);
  const [form, setForm] = useState({ symbol: defaultSymbol || "", side: "buy", entry_price: "", exit_price: "", stop_price: "", quantity: "", thesis: "", emotion: "" });
  const [busy, setBusy] = useState(false);
  const [reviewing, setReviewing] = useState(null);

  const load = useCallback(async () => {
    try {
      const d = await api.tradeJournal();
      setEntries(d.entries);
    } catch (err) {
      notify(err.message, "error");
    }
  }, [notify]);
  useEffect(() => { load(); }, [load]);

  function set(k, v) { setForm((f) => ({ ...f, [k]: v })); }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const num = (v) => (v === "" ? null : Number(v));
      await api.tradeAddJournal({
        symbol: form.symbol, side: form.side,
        entry_price: num(form.entry_price), exit_price: num(form.exit_price),
        stop_price: num(form.stop_price), quantity: num(form.quantity),
        thesis: form.thesis || null, emotion: form.emotion || null, tags: [],
      });
      setForm((f) => ({ ...f, thesis: "", emotion: "" }));
      notify("Trade logged", "success");
      load();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function review(id) {
    setReviewing(id);
    try {
      const d = await api.tradeReviewJournal(id);
      setEntries((es) => es.map((e) => (e.id === id ? d.entry : e)));
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setReviewing(null);
    }
  }

  return (
    <div>
      <form className="card" onSubmit={submit}>
        <h3 style={{ marginTop: 0 }}>Log a trade</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8 }}>
          <label>Symbol<input value={form.symbol} onChange={(e) => set("symbol", e.target.value.toUpperCase())} required /></label>
          <label>Side
            <select value={form.side} onChange={(e) => set("side", e.target.value)}>
              <option value="buy">Buy / Long</option>
              <option value="sell">Sell / Short</option>
            </select>
          </label>
          <label>Entry<input type="number" step="0.01" value={form.entry_price} onChange={(e) => set("entry_price", e.target.value)} /></label>
          <label>Exit<input type="number" step="0.01" value={form.exit_price} onChange={(e) => set("exit_price", e.target.value)} /></label>
          <label>Stop<input type="number" step="0.01" value={form.stop_price} onChange={(e) => set("stop_price", e.target.value)} /></label>
          <label>Qty<input type="number" step="1" value={form.quantity} onChange={(e) => set("quantity", e.target.value)} /></label>
          <label>Emotion<input value={form.emotion} onChange={(e) => set("emotion", e.target.value)} placeholder="calm, fomo…" /></label>
        </div>
        <label style={{ display: "block", marginTop: 8 }}>Thesis (why this trade?)
          <textarea rows={2} value={form.thesis} onChange={(e) => set("thesis", e.target.value)} />
        </label>
        <button className="btn btn-primary" style={{ marginTop: 8 }} disabled={busy}>Log trade</button>
      </form>

      {entries == null ? <LoadingState /> : entries.length === 0 ? (
        <div className="card"><p className="muted">No trades logged yet. Your journal builds the record the AI coach reviews.</p></div>
      ) : entries.map((e) => (
        <div key={e.id} className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <div>
              <strong>{e.symbol}</strong> <span className="muted">{e.side}</span>
              {e.pnl != null && <span style={{ marginLeft: 8, color: e.pnl >= 0 ? "#16a34a" : "#dc2626", fontWeight: 600 }}>{money(e.pnl)}</span>}
            </div>
            <button className="btn btn-ghost" onClick={() => review(e.id)} disabled={reviewing === e.id}>
              {reviewing === e.id ? "Reviewing…" : e.ai_review ? "Re-review" : "AI review"}
            </button>
          </div>
          {e.thesis && <p style={{ margin: "6px 0", fontSize: ".9rem" }}>{e.thesis}</p>}
          {e.ai_review && (
            <div style={{ borderLeft: "3px solid var(--primary)", paddingLeft: 10, marginTop: 8 }}>
              <div className="muted" style={{ fontSize: ".72rem", textTransform: "uppercase" }}>Coach</div>
              <p style={{ margin: "2px 0", fontSize: ".9rem" }}>{e.ai_review}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// --- Academy -------------------------------------------------------------
function Academy() {
  const [modules, setModules] = useState(null);
  const [open, setOpen] = useState(null);
  useEffect(() => {
    api.tradeAcademy().then((d) => setModules(d.modules)).catch(() => setModules([]));
  }, []);
  if (modules == null) return <LoadingState />;
  return (
    <div>
      <p className="muted">Learn by doing — each module pairs with the paper simulator on the Chart tab.</p>
      {modules.map((m) => (
        <div key={m.slug} className="card">
          <button className="btn btn-ghost" style={{ width: "100%", textAlign: "left", display: "flex", justifyContent: "space-between" }}
            onClick={() => setOpen(open === m.slug ? null : m.slug)}>
            <span><strong>{m.title}</strong> <span className="muted">· {m.level} · {m.minutes} min</span></span>
            <span>{open === m.slug ? "−" : "+"}</span>
          </button>
          {open === m.slug && (
            <div style={{ marginTop: 8 }}>
              <p className="muted" style={{ fontSize: ".9rem" }}>{m.summary}</p>
              {m.lessons.map((l) => (
                <div key={l.key} style={{ marginTop: 10 }}>
                  <strong style={{ fontSize: ".95rem" }}>{l.title}</strong>
                  <p style={{ margin: "2px 0", fontSize: ".9rem" }}>{l.body}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
