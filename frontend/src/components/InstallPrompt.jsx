// PWA install button. Chrome/Edge/Android fire `beforeinstallprompt` when the app
// is installable; we capture it and show a button that triggers the native prompt.
// (iOS Safari has no such event — users install via Share → "Add to Home Screen".)

import { useEffect, useState } from "react";

export default function InstallPrompt() {
  const [deferred, setDeferred] = useState(null);
  const [hidden, setHidden] = useState(
    () => localStorage.getItem("skillswap_install_dismissed") === "1"
  );

  useEffect(() => {
    function onPrompt(e) {
      e.preventDefault();
      setDeferred(e);
    }
    function onInstalled() {
      setDeferred(null);
    }
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (!deferred || hidden) return null;

  async function install() {
    deferred.prompt();
    await deferred.userChoice.catch(() => {});
    setDeferred(null);
  }

  function dismiss() {
    localStorage.setItem("skillswap_install_dismissed", "1");
    setHidden(true);
  }

  return (
    <div className="install-banner" role="dialog" aria-label="Install app">
      <span>Install SkillSwap AI for a full-screen app experience.</span>
      <div className="install-actions">
        <button type="button" className="btn btn-primary install-btn" onClick={install}>
          Install
        </button>
        <button type="button" className="btn install-dismiss" aria-label="Dismiss" onClick={dismiss}>
          ✕
        </button>
      </div>
    </div>
  );
}
