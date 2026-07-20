// Theme preference: "system" (follow OS), "light", or "dark". Persisted in
// localStorage and applied by setting `data-theme` on <html>. "system" removes
// the attribute so the prefers-color-scheme media query takes over.

const THEME_KEY = "skillswap_theme";
export const THEMES = ["system", "light", "dark"];

export function getTheme() {
  const t = localStorage.getItem(THEME_KEY);
  return THEMES.includes(t) ? t : "system";
}

export function applyTheme(pref) {
  const root = document.documentElement;
  if (pref === "light" || pref === "dark") {
    root.dataset.theme = pref;
  } else {
    delete root.dataset.theme;
  }
}

export function setTheme(pref) {
  const value = THEMES.includes(pref) ? pref : "system";
  localStorage.setItem(THEME_KEY, value);
  applyTheme(value);
  return value;
}

// Apply the saved theme as early as possible (called from main.jsx) to avoid a flash.
export function initTheme() {
  applyTheme(getTheme());
}
