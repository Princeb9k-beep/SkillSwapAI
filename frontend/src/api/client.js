// Central API client.
//
// The backend always responds with the UX/UI Pro Max envelope
// { success, data, message, meta }. This wrapper unwraps it, throwing an Error
// (carrying the human-readable message) on failure so callers/components can
// render a single, consistent error state. Auth is a JWT sent as a Bearer token.

// Default to same-origin ("") so the single-app deploy (FastAPI serving this
// SPA) just calls /health, /roadmap, etc. on its own host. For split local dev
// (Vite on :5173, API on :8000), set VITE_API_BASE_URL=http://localhost:8000.
const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

const TOKEN_KEY = "skillswap_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

// Optional hook so the app can react to auth expiry (401) globally.
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (auth && token) headers["Authorization"] = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Can't reach the server. Check your connection and try again.");
  }

  let payload;
  try {
    payload = await res.json();
  } catch {
    throw new Error("Unexpected response from the server.");
  }

  if (res.status === 401 && auth && onUnauthorized) {
    onUnauthorized();
  }

  if (!res.ok || payload.success === false) {
    throw new Error(payload?.message || "Something went wrong.");
  }
  return payload.data;
}

export const api = {
  // auth
  signup: (data) => request("/auth/signup", { method: "POST", body: data, auth: false }),
  login: (data) => request("/auth/login", { method: "POST", body: data, auth: false }),
  me: () => request("/users/me"),
  updateProfile: (data) => request("/users/me", { method: "PATCH", body: data }),
  // skills + matching
  getSkills: () => request("/skills"),
  addSkill: (data) => request("/skills", { method: "POST", body: data }),
  deleteSkill: (id) => request(`/skills/${id}`, { method: "DELETE" }),
  getMatches: () => request("/matches"),
  // features
  getRoadmap: () => request("/roadmap"),
  generateRoadmap: (data) => request("/roadmap", { method: "POST", body: data }),
  suggestProjects: (data) => request("/projects/suggest", { method: "POST", body: data }),
  listProjects: () => request("/projects"),
  buildResume: (data) => request("/resume/build", { method: "POST", body: data }),
  startInterview: (data) => request("/interview/start", { method: "POST", body: data }),
  answerInterview: (data) => request("/interview/answer", { method: "POST", body: data }),
  dailyLessons: () => request("/lessons/daily"),
  completeLesson: (id) => request(`/lessons/${id}/complete`, { method: "POST" }),
};
