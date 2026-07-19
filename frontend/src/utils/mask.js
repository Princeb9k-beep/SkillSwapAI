// Small input-mask helpers that format a field's value as the user types,
// guiding input toward the expected shape.

// Currency: keep digits only, render as "$80,000".
export function formatCurrency(raw) {
  const digits = String(raw ?? "").replace(/\D/g, "");
  if (!digits) return "";
  return "$" + parseInt(digits, 10).toLocaleString("en-US");
}

export function parseCurrency(masked) {
  const digits = String(masked ?? "").replace(/\D/g, "");
  return digits ? parseInt(digits, 10) : null;
}

// True when a goal mentions money/salary (so we can reveal the income field).
const INCOME_HINT =
  /(\$\s*\d|\b\d[\d,]*\s*[kK]\b|salary|income|earn|wage|\bpay\b|per\s*year|annual|\/yr)/i;

export function goalMentionsIncome(goal) {
  return INCOME_HINT.test(String(goal ?? ""));
}

// Pull a dollar amount out of a goal string: "$80k" / "80,000" -> 80000.
export function extractIncome(text) {
  const m = String(text ?? "").match(/\$?\s*([\d,]+)\s*([kK])?/);
  if (!m) return null;
  const n = parseInt(m[1].replace(/,/g, ""), 10);
  if (Number.isNaN(n)) return null;
  return m[2] ? n * 1000 : n;
}
