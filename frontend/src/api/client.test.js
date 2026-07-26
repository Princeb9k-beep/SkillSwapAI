import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, setToken } from "./client.js";

function mockFetch(status, payload) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
}

describe("api client envelope handling", () => {
  beforeEach(() => {
    setToken(null);
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("unwraps the {success, data} envelope on success", async () => {
    globalThis.fetch = mockFetch(200, {
      success: true,
      data: { plans: [{ tier: "free" }], current: "free" },
      message: "ok",
      meta: {},
    });
    const data = await api.billingPlans();
    expect(data.current).toBe("free");
    expect(data.plans[0].tier).toBe("free");
  });

  it("throws the server message when success is false", async () => {
    globalThis.fetch = mockFetch(400, {
      success: false,
      data: null,
      message: "Nope.",
      meta: {},
    });
    await expect(api.billingPlans()).rejects.toThrow("Nope.");
  });

  it("sends the bearer token when one is set", async () => {
    setToken("abc123");
    const spy = mockFetch(200, { success: true, data: {}, message: "", meta: {} });
    globalThis.fetch = spy;
    await api.billingMe();
    const [, opts] = spy.mock.calls[0];
    expect(opts.headers.Authorization).toBe("Bearer abc123");
  });
});
