// The moving background of a Discover skill "clip". Two modes:
//   1. If the skill has a creator-uploaded `videoUrl`, it plays a real looping,
//      muted, inline <video> — and only while the clip is the one on screen
//      (`active`), the way TikTok pauses off-screen videos to save battery/data.
//   2. Otherwise it renders an authored, self-contained animated motion loop
//      (drifting color blobs + a floating emoji) tinted to the skill's category,
//      so every clip feels like short-form video even with no uploaded file.

import { useEffect, useRef } from "react";

// A hue per category so each clip has its own identity.
const CATEGORY_HUE = {
  Coding: 255,
  Design: 330,
  Languages: 200,
  Music: 285,
  Career: 25,
  Business: 150,
  Wellness: 95,
};

export function categoryGradient(category) {
  const h = CATEGORY_HUE[category] ?? 255;
  return `radial-gradient(120% 80% at 50% 15%, hsl(${h} 70% 45%), hsl(${h + 25} 65% 28%) 70%, hsl(${h + 25} 60% 18%))`;
}

export default function SkillClip({ category, emoji, videoUrl, active }) {
  const videoRef = useRef(null);
  const h = CATEGORY_HUE[category] ?? 255;
  const gradient = categoryGradient(category);

  // Play only the on-screen clip; pause the rest (TikTok-style).
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (active) {
      const p = v.play();
      if (p && typeof p.catch === "function") p.catch(() => {});
    } else {
      v.pause();
    }
  }, [active, videoUrl]);

  if (videoUrl) {
    return (
      <video
        ref={videoRef}
        className="disco-clip disco-clip-video"
        src={videoUrl}
        muted
        loop
        playsInline
        preload="metadata"
        aria-hidden="true"
        style={{ background: gradient }}
      />
    );
  }

  // Authored motion loop. Blobs drift and the emoji bobs via CSS keyframes;
  // `active` nudges the animation to life only when the clip is in view.
  return (
    <div
      className={`disco-clip disco-clip-motion${active ? " playing" : ""}`}
      aria-hidden="true"
      style={{ background: gradient }}
    >
      <span className="clip-blob clip-blob-1" style={{ background: `hsl(${h + 40} 85% 60%)` }} />
      <span className="clip-blob clip-blob-2" style={{ background: `hsl(${h - 30} 85% 55%)` }} />
      <span className="clip-blob clip-blob-3" style={{ background: `hsl(${h + 15} 90% 65%)` }} />
      <span className="clip-emoji" aria-hidden="true">{emoji}</span>
    </div>
  );
}
