// Lightweight global UI state: the stubbed current user + a toast notifier.
// Mirrors ui-ux-pro-max guidance to centralize UI state and give every screen a
// consistent way to surface success/error feedback.

import { createContext, useCallback, useContext, useState } from "react";
import { getUserId, setUserId } from "../api/client.js";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [userId, setUserIdState] = useState(getUserId());
  const [toast, setToast] = useState(null);

  const login = useCallback((id) => {
    setUserId(id);
    setUserIdState(String(id));
  }, []);

  const notify = useCallback((message, type = "info") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  return (
    <AppContext.Provider value={{ userId, login, notify }}>
      {children}
      {toast && <div className={`toast toast-${toast.type}`}>{toast.message}</div>}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
