// Browser push (Web Push API) helpers. Subscribes this device with the server's
// VAPID public key and registers the subscription with the backend. Everything
// feature-detects and fails loudly enough for the UI to explain what happened.

import { api } from "./api/client.js";

export function pushSupported() {
  return (
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export function permission() {
  return typeof Notification !== "undefined" ? Notification.permission : "denied";
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) output[i] = raw.charCodeAt(i);
  return output;
}

async function readyRegistration() {
  // Ensure the SW is registered (main.jsx registers it on load), then wait ready.
  if (!navigator.serviceWorker.controller) {
    try {
      await navigator.serviceWorker.register("/serviceWorker.js");
    } catch {
      /* already registered or blocked */
    }
  }
  return navigator.serviceWorker.ready;
}

export async function getExistingSubscription() {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
}

// Subscribe this device. Returns { ok: true } or { ok: false, reason }.
export async function enablePush() {
  if (!pushSupported()) return { ok: false, reason: "unsupported" };

  const { public_key } = await api.vapidKey();
  if (!public_key) return { ok: false, reason: "server-unconfigured" };

  const perm = await Notification.requestPermission();
  if (perm !== "granted") return { ok: false, reason: "denied" };

  const reg = await readyRegistration();
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key),
    });
  }

  const json = sub.toJSON();
  await api.pushSubscribe({ endpoint: json.endpoint, keys: json.keys });
  return { ok: true };
}

export async function disablePush() {
  const sub = await getExistingSubscription();
  if (sub) {
    const endpoint = sub.endpoint;
    try {
      await sub.unsubscribe();
    } catch {
      /* ignore */
    }
    try {
      await api.pushUnsubscribe(endpoint);
    } catch {
      /* ignore */
    }
  }
  return { ok: true };
}
