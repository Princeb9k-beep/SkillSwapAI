// A small AI-token balance shown in the top-right, but only on tabs that use AI.
// Refreshes when you navigate onto an AI tab and whenever an AI action is taken
// (the api client dispatches a "tokens:changed" event after spending a token).

import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api/client.js";

// Tabs that feature AI. "/" (goal → roadmap) is matched exactly; the rest match
// as path prefixes so their sub-routes count too.
const AI_EXACT = new Set(["/"]);
const AI_PREFIXES = [
  "/coach",
  "/twin",
  "/scanner",
  "/translate",
  "/career",
  "/resume",
  "/interview",
  "/academy",
  "/verify",
  "/lessons",
  "/flashcards",
  "/dashboard",
];

export function isAiRoute(pathname) {
  if (AI_EXACT.has(pathname)) return true;
  return AI_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export default function TokenPill() {
  const { pathname } = useLocation();
  const [wallet, setWallet] = useState(null);
  const show = isAiRoute(pathname);

  const load = useCallback(async () => {
    try {
      const data = await api.aiTokens();
      setWallet(data.wallet);
    } catch {
      /* leave the pill hidden on error */
    }
  }, []);

  // Fetch when landing on an AI tab, and refresh after any AI action.
  useEffect(() => {
    if (!show) return undefined;
    load();
    const onChange = () => load();
    window.addEventListener("tokens:changed", onChange);
    return () => window.removeEventListener("tokens:changed", onChange);
  }, [show, load]);

  if (!show || !wallet) return null;

  const label = wallet.unlimited ? "∞" : wallet.balance;
  const low = !wallet.unlimited && wallet.balance <= 5;

  return (
    <Link
      to="/plans"
      className={`token-pill${low ? " token-pill-low" : ""}`}
      title={wallet.unlimited ? "Unlimited AI tokens" : `${wallet.balance} AI tokens left`}
      aria-label={wallet.unlimited ? "Unlimited AI tokens" : `${wallet.balance} AI tokens left`}
    >
      <span className="token-pill-icon" aria-hidden="true">⚡</span>
      <span className="token-pill-count">{label}</span>
    </Link>
  );
}
