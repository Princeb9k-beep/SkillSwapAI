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

// Build the signaling WebSocket URL for a practice room. Browsers can't set
// Authorization headers on a WebSocket, so the JWT rides as a query param.
export function roomSocketUrl(code) {
  const origin = BASE || window.location.origin;
  const wsBase = origin.replace(/^http/, "ws");
  const token = getToken();
  return `${wsBase}/rooms/ws/${encodeURIComponent(code)}?token=${encodeURIComponent(token || "")}`;
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
  deleteAccount: () => request("/users/me", { method: "DELETE" }),
  // billing / subscription
  billingPlans: () => request("/billing/plans"),
  billingMe: () => request("/billing/me"),
  subscribe: (tier) => request("/billing/subscribe", { method: "POST", body: { tier } }),
  aiTokens: () => request("/billing/tokens"),
  buyTokens: (pack) => request("/billing/tokens/buy", { method: "POST", body: { pack } }),
  verifyEmail: (token) => request("/auth/verify-email", { method: "POST", body: { token }, auth: false }),
  resendVerification: () => request("/auth/resend-verification", { method: "POST" }),
  forgotPassword: (email) =>
    request("/auth/forgot-password", { method: "POST", body: { email }, auth: false }),
  resetPassword: (token, password) =>
    request("/auth/reset-password", { method: "POST", body: { token, password }, auth: false }),
  // skills + matching
  getSkills: () => request("/skills"),
  addSkill: (data) => request("/skills", { method: "POST", body: data }),
  deleteSkill: (id) => request(`/skills/${id}`, { method: "DELETE" }),
  getMatches: () => request("/matches"),
  matchFeedback: (partnerId, signal) =>
    request(`/matches/${partnerId}/feedback`, { method: "POST", body: { signal } }),
  // safety / moderation
  listBlocks: () => request("/blocks"),
  blockUser: (userId) => request(`/blocks/${userId}`, { method: "POST" }),
  unblockUser: (userId) => request(`/blocks/${userId}`, { method: "DELETE" }),
  reportContent: (target_type, target_id, reason) =>
    request("/reports", { method: "POST", body: { target_type, target_id, reason } }),
  adminReports: (status = "open") => request(`/admin/reports?status=${status}`),
  resolveReport: (id) => request(`/admin/reports/${id}/resolve`, { method: "POST" }),
  // gamification
  getProgress: () => request("/progress"),
  getLeaderboard: () => request("/leaderboard"),
  // communities
  getCommunities: () => request("/communities"),
  createCommunity: (data) => request("/communities", { method: "POST", body: data }),
  getCommunity: (id) => request(`/communities/${id}`),
  joinCommunity: (id) => request(`/communities/${id}/join`, { method: "POST" }),
  leaveCommunity: (id) => request(`/communities/${id}/leave`, { method: "POST" }),
  postToCommunity: (id, body) =>
    request(`/communities/${id}/posts`, { method: "POST", body: { body } }),
  deletePost: (id, postId) =>
    request(`/communities/${id}/posts/${postId}`, { method: "DELETE" }),
  // skill verification
  requestVerification: (data) => request("/verifications", { method: "POST", body: data }),
  myVerifications: () => request("/verifications/mine"),
  verificationQueue: () => request("/verifications/queue"),
  reviewVerification: (id, data) =>
    request(`/verifications/${id}/review`, { method: "POST", body: data }),
  // portfolio + reputation
  getPortfolio: () => request("/portfolio"),
  getReputation: (userId) => request(`/reputation/${userId}`),
  reviewReputation: (userId, data) =>
    request(`/reputation/${userId}/review`, { method: "POST", body: data }),
  // ai coach
  coachHistory: () => request("/coach/history"),
  coachChat: (message) => request("/coach/chat", { method: "POST", body: { message } }),
  clearCoach: () => request("/coach/history", { method: "DELETE" }),
  // ai skill scanner
  scanSkills: (text) => request("/scanner/analyze", { method: "POST", body: { text } }),
  // live translation
  translateLanguages: () => request("/translate/languages"),
  translate: (text, target_language) =>
    request("/translate", { method: "POST", body: { text, target_language } }),
  // daily challenges
  todayChallenge: () => request("/challenges/today"),
  completeChallenge: (id) => request(`/challenges/${id}/complete`, { method: "POST" }),
  // ai twin
  myTwin: () => request("/twin/me"),
  trainTwin: (samples) => request("/twin/train", { method: "POST", body: { samples } }),
  availableTwins: () => request("/twin/available"),
  twinHistory: (ownerId) => request(`/twin/${ownerId}/history`),
  twinChat: (ownerId, message) =>
    request(`/twin/${ownerId}/chat`, { method: "POST", body: { message } }),
  twinQuiz: (ownerId, topic) =>
    request(`/twin/${ownerId}/quiz`, { method: "POST", body: { topic } }),
  // marketplace
  getListings: () => request("/marketplace/listings"),
  myListings: () => request("/marketplace/listings/mine"),
  createListing: (data) => request("/marketplace/listings", { method: "POST", body: data }),
  bookListing: (id) => request(`/marketplace/listings/${id}/book`, { method: "POST" }),
  getOrders: () => request("/marketplace/orders"),
  updateOrder: (id, status) =>
    request(`/marketplace/orders/${id}`, { method: "PATCH", body: { status } }),
  // local meetups
  listMeetups: () => request("/meetups"),
  createMeetup: (data) => request("/meetups", { method: "POST", body: data }),
  rsvpMeetup: (id) => request(`/meetups/${id}/rsvp`, { method: "POST" }),
  cancelMeetup: (id) => request(`/meetups/${id}/cancel`, { method: "POST" }),
  deleteMeetup: (id) => request(`/meetups/${id}`, { method: "DELETE" }),
  // company partnerships
  listCompanies: () => request("/partnerships/companies"),
  createCompany: (data) => request("/partnerships/companies", { method: "POST", body: data }),
  postChallenge: (companyId, data) =>
    request(`/partnerships/companies/${companyId}/challenges`, { method: "POST", body: data }),
  listOpportunities: () => request("/partnerships/challenges"),
  submitToChallenge: (id, content) =>
    request(`/partnerships/challenges/${id}/submit`, { method: "POST", body: { content } }),
  challengeSubmissions: (id) => request(`/partnerships/challenges/${id}/submissions`),
  reviewSubmission: (id, status) =>
    request(`/partnerships/submissions/${id}/review`, { method: "POST", body: { status } }),
  // web push
  vapidKey: () => request("/push/vapid-public-key"),
  pushSubscribe: (sub) => request("/push/subscribe", { method: "POST", body: sub }),
  pushUnsubscribe: (endpoint) =>
    request("/push/unsubscribe", { method: "POST", body: { endpoint } }),
  // notifications
  notifications: () => request("/notifications"),
  notificationsUnread: () => request("/notifications/unread/count"),
  readNotification: (id) => request(`/notifications/${id}/read`, { method: "POST" }),
  readAllNotifications: () => request("/notifications/read-all", { method: "POST" }),
  // skill academy
  academyCategories: () => request("/academy/categories"),
  academyPaths: (category) =>
    request(`/academy/paths${category && category !== "All" ? `?category=${encodeURIComponent(category)}` : ""}`),
  academyPath: (slug) => request(`/academy/paths/${slug}`),
  academyContent: (slug, key) => request(`/academy/paths/${slug}/lessons/${key}/content`),
  academyEnroll: (slug) => request(`/academy/paths/${slug}/enroll`, { method: "POST" }),
  academyComplete: (slug, key) =>
    request(`/academy/paths/${slug}/lessons/${key}/complete`, { method: "POST" }),
  academyAssist: (slug, key, mode, question) =>
    request(`/academy/paths/${slug}/lessons/${key}/assist`, {
      method: "POST",
      body: { mode, question },
    }),
  // direct messaging
  messageThreads: () => request("/messages/threads"),
  conversation: (partnerId) => request(`/messages/${partnerId}`),
  sendMessage: (partnerId, body) =>
    request(`/messages/${partnerId}`, { method: "POST", body: { body } }),
  unreadCount: () => request("/messages/unread/count"),
  // video practice rooms
  listRooms: () => request("/rooms"),
  createRoom: (data) => request("/rooms", { method: "POST", body: data }),
  getRoom: (code) => request(`/rooms/${code}`),
  saveRoomNotes: (code, notes) =>
    request(`/rooms/${code}/notes`, { method: "PUT", body: { notes } }),
  closeRoom: (code) => request(`/rooms/${code}/close`, { method: "POST" }),
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
