// Global app state: the authenticated user/token + a toast notifier.
// Token and user are persisted in localStorage so a refresh keeps you signed in.

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getToken, setToken, setUnauthorizedHandler } from "../api/client.js";

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

  const login = useCallback((newToken, newUser) => {
    setToken(newToken);
    setTokenState(newToken);
    setUser(newUser);
    localStorage.setItem(USER_KEY, JSON.stringify(newUser));
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setTokenState(null);
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
