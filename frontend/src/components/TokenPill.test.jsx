import { describe, it, expect } from "vitest";
import { isAiRoute } from "./TokenPill.jsx";

describe("isAiRoute", () => {
  it("matches AI tabs", () => {
    expect(isAiRoute("/")).toBe(true); // goal → roadmap
    expect(isAiRoute("/coach")).toBe(true);
    expect(isAiRoute("/twin")).toBe(true);
    expect(isAiRoute("/scanner")).toBe(true);
    expect(isAiRoute("/academy")).toBe(true);
    expect(isAiRoute("/interview")).toBe(true);
  });

  it("does not match non-AI tabs", () => {
    expect(isAiRoute("/messages")).toBe(false);
    expect(isAiRoute("/settings")).toBe(false);
    expect(isAiRoute("/community")).toBe(false);
    expect(isAiRoute("/plans")).toBe(false);
  });
});
