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
