// Catches render/lazy-load errors so the app shows a recovery screen instead of
// a blank (black) page. The common trigger is a *stale chunk* after a deploy:
// a cached index.html references a code-split file whose hash changed, so the
// dynamic import 404s. We reload once (fetching the fresh build); a timestamp
// guard prevents reload loops if a reload doesn't fix it (broken deploy).

import { Component } from "react";

const CHUNK_RE =
  /(dynamically imported module|Loading chunk|Importing a module script failed|Failed to fetch dynamically|error loading dynamically)/i;

const RELOAD_GUARD = "ssai_chunk_reload_at";
const RELOAD_COOLDOWN_MS = 10000;

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    if (!CHUNK_RE.test(error?.message || "")) return;
    const last = Number(sessionStorage.getItem(RELOAD_GUARD) || 0);
    // Auto-reload for a stale chunk, but not if we just reloaded (avoid a loop).
    if (Date.now() - last > RELOAD_COOLDOWN_MS) {
      sessionStorage.setItem(RELOAD_GUARD, String(Date.now()));
      window.location.reload();
    }
  }

  reload = () => {
    sessionStorage.removeItem(RELOAD_GUARD);
    window.location.reload();
  };

  render() {
    if (this.state.error) {
      const isChunk = CHUNK_RE.test(this.state.error?.message || "");
      return (
        <div className="app-error">
          <h1>{isChunk ? "Update ready" : "Something went wrong"}</h1>
          <p className="muted">
            {isChunk
              ? "A newer version of the app is available."
              : "The app ran into an unexpected error."}
          </p>
          <button className="btn btn-primary" onClick={this.reload}>
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
