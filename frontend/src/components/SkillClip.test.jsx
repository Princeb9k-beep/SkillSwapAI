import { render } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SkillClip from "./SkillClip.jsx";

// jsdom doesn't implement media playback; stub so effects don't throw.
beforeEach(() => {
  HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  HTMLMediaElement.prototype.pause = vi.fn();
});

describe("SkillClip", () => {
  it("renders an authored motion loop when there is no video", () => {
    const { container } = render(
      <SkillClip category="Coding" emoji="🐍" videoUrl={null} active />,
    );
    expect(container.querySelector("video")).toBeNull();
    expect(container.querySelector(".disco-clip-motion")).toBeTruthy();
    // Blobs + emoji make up the motion scene.
    expect(container.querySelectorAll(".clip-blob").length).toBe(3);
  });

  it("plays a real video (only while active) when a videoUrl is set", () => {
    const { container, rerender } = render(
      <SkillClip category="Music" emoji="🎸" videoUrl="/clips/x.mp4" active />,
    );
    const video = container.querySelector("video");
    expect(video).toBeTruthy();
    expect(video).toHaveAttribute("loop");
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalled();
    // Scrolling it off-screen pauses it.
    rerender(<SkillClip category="Music" emoji="🎸" videoUrl="/clips/x.mp4" active={false} />);
    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled();
  });
});
