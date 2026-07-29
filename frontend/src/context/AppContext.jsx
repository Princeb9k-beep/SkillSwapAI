// Global app state: the authenticated user/token + a toast notifier.
// Token and user are persisted in localStorage so a refresh keeps you signed in.

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  api,
  getToken,
  setToken,
  getRefreshToken,
  setRefreshToken,
  setUnauthorizedHandler,
} from "../api/client.js";
import { connectRealtime, disconnectRealtime } from "../realtime.js";

const AppContext = createContext(null);
const USER_KEY = "skillswap_user";

function loadUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY)) || null;
  } catch {
    return null;
  }
}

export function AppProvider({ children }) {
  const [token, setTokenState] = useState(getToken());
  const [user, setUser] = useState(loadUser());
  const [toast, setToast] = useState(null);

  const login = useCallback((newToken, newUser, refreshToken) => {
    setToken(newToken);
    setTokenState(newToken);
    if (refreshToken !== undefined) setRefreshToken(refreshToken);
    setUser(newUser);
    localStorage.setItem(USER_KEY, JSON.stringify(newUser));
  }, []);

  const logout = useCallback(() => {
    // Best-effort server-side revoke of this device's refresh token.
    const refresh = getRefreshToken();
    if (refresh) api.logout(refresh).catch(() => {});
    setToken(null);
    setTokenState(null);
    setRefreshToken(null);
    setUser(null);
    localStorage.removeItem(USER_KEY);
  }, []);

  const updateUser = useCallback((patch) => {
    setUser((prev) => {
      const next = { ...(prev || {}), ...patch };
      localStorage.setItem(USER_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const notify = useCallback((message, type = "info") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  // If any request 401s, drop the (expired) session so the UI returns to auth.
  useEffect(() => {
    setUnauthorizedHandler(() => logout());
  }, [logout]);

  // Keep a personal live-updates socket open while signed in.
  useEffect(() => {
    if (token) {
      connectRealtime();
      return () => disconnectRealtime();
    }
    disconnectRealtime();
    return undefined;
  }, [token]);

  // Keep the user's timezone in sync with their device (handles travel/DST).
  useEffect(() => {
    if (!token || !user) return;
    let tz;
    try {
      tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {
      return;
    }
    if (tz && tz !== user.timezone) {
      api.updateProfile({ timezone: tz }).then((u) => updateUser(u)).catch(() => {});
    }
  }, [token, user, updateUser]);

  return (
    <AppContext.Provider
      value={{ token, user, isAuthed: !!token, login, logout, updateUser, notify }}
    >
      {children}
      {toast && (
        <div
          className={`toast toast-${toast.type}`}
          role={toast.type === "error" ? "alert" : "status"}
          aria-live={toast.type === "error" ? "assertive" : "polite"}
        >
          {toast.message}
        </div>
      )}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
