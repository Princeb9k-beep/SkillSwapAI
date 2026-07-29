// Share helper: uses the native share sheet on mobile, falls back to copying a
// prefilled link on desktop. Returns "shared" | "copied" | "failed" so callers
// can show the right toast.

export async function share({ title, text, url }) {
  if (typeof navigator !== "undefined" && navigator.share) {
    try {
      await navigator.share({ title, text, url });
      return "shared";
    } catch (err) {
      // AbortError = user closed the sheet; treat as a no-op, not a failure.
      if (err && err.name === "AbortError") return "shared";
      // fall through to copy
    }
  }
  const payload = url ? `${text} ${url}` : text;
  try {
    await navigator.clipboard.writeText(payload);
    return "copied";
  } catch {
    return "failed";
  }
}
