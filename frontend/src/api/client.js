// Central API client.
//
// The backend always responds with the UX/UI Pro Max envelope
// { success, data, message, meta }. This wrapper unwraps it, throwing an Error
// (carrying the human-readable message) on failure so callers/components can
// render a single, consistent error state. The stubbed auth user id is sent via
// the X-User-Id header.

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function getUserId() {
  return localStorage.getItem("skillswap_user_id");
}

export function setUserId(id) {
  localStorage.setItem("skillswap_user_id", String(id));
}

async function request(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const uid = getUserId();
  if (uid) headers["X-User-Id"] = uid;

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

  if (!res.ok || payload.success === false) {
    throw new Error(payload?.message || "Something went wrong.");
  }
  return payload.data;
}

export const api = {
  createUser: (data) => request("/users", { method: "POST", body: data }),
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
