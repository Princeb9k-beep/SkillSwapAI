// Personal live-updates WebSocket client. Opens one connection to /ws/user,
// auto-reconnects with backoff, sends periodic pings, and fans incoming events
// out to any subscribers. A tiny pub/sub so multiple components (Messages,
// NotificationBell) can react to the same socket.

import { userSocketUrl, getToken } from "./api/client.js";

let socket = null;
let pingTimer = null;
let reconnectTimer = null;
let attempts = 0;
let closedByUs = false;
const listeners = new Set();

function emit(event) {
  listeners.forEach((fn) => {
    try {
      fn(event);
    } catch {
      /* a bad listener shouldn't break delivery to the others */
    }
  });
}

function open() {
  if (!getToken()) return;
  closedByUs = false;
  try {
    socket = new WebSocket(userSocketUrl());
  } catch {
    scheduleReconnect();
    return;
  }

  socket.onopen = () => {
    attempts = 0;
    clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) socket.send("ping");
    }, 25000);
  };
  socket.onmessage = (e) => {
    let data;
    try {
      data = JSON.parse(e.data);
    } catch {
      return;
    }
    if (data.type === "pong" || data.type === "ready") return;
    emit(data);
  };
  socket.onclose = () => {
    clearInterval(pingTimer);
    if (!closedByUs) scheduleReconnect();
  };
  socket.onerror = () => {
    try {
      socket?.close();
    } catch {
      /* ignore */
    }
  };
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  const delay = Math.min(30000, 1000 * 2 ** attempts);
  attempts += 1;
  reconnectTimer = setTimeout(open, delay);
}

export function connectRealtime() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  open();
}

export function disconnectRealtime() {
  closedByUs = true;
  clearTimeout(reconnectTimer);
  clearInterval(pingTimer);
  try {
    socket?.close();
  } catch {
    /* ignore */
  }
  socket = null;
  attempts = 0;
}

// Subscribe to realtime events; returns an unsubscribe function.
export function onRealtime(handler) {
  listeners.add(handler);
  return () => listeners.delete(handler);
}

// Send a small JSON message up the socket (e.g. typing signals). No-op if closed.
export function sendRealtime(payload) {
  if (socket?.readyState === WebSocket.OPEN) {
    try {
      socket.send(JSON.stringify(payload));
    } catch {
      /* ignore */
    }
  }
}
