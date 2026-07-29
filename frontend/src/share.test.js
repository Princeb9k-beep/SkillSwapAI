import { describe, it, expect, vi, afterEach } from "vitest";
import { share } from "./share.js";

afterEach(() => {
  vi.restoreAllMocks();
  delete navigator.share;
});

describe("share()", () => {
  it("uses the native share sheet when available", async () => {
    navigator.share = vi.fn().mockResolvedValue(undefined);
    const res = await share({ title: "t", text: "hi", url: "u" });
    expect(res).toBe("shared");
    expect(navigator.share).toHaveBeenCalledWith({ title: "t", text: "hi", url: "u" });
  });

  it("falls back to copying text + url when there's no share sheet", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const res = await share({ text: "I hit a streak", url: "https://x.test" });
    expect(res).toBe("copied");
    expect(writeText).toHaveBeenCalledWith("I hit a streak https://x.test");
  });
});
