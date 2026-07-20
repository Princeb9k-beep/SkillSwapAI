import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { initTheme } from "./theme.js";
import "./styles/index.css";

initTheme(); // apply the saved theme before first paint

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);

// Register the service worker for offline caching of the app shell (progressive
// enhancement — the app works fine without it).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/serviceWorker.js").catch(() => {
      /* offline support is best-effort */
    });
  });
}
