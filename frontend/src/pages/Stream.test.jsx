import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Stream from "./Stream.jsx";

const dailyLessons = vi.fn();
const completeLesson = vi.fn();
const notify = vi.fn();

vi.mock("../api/client.js", () => ({
  api: {
    dailyLessons: () => dailyLessons(),
    completeLesson: (id) => completeLesson(id),
  },
}));
vi.mock("../context/AppContext.jsx", () => ({
  useApp: () => ({ notify }),
}));

// jsdom has no real layout; stub scroll APIs the component calls.
beforeEach(() => {
  Element.prototype.scrollTo = vi.fn();
  dailyLessons.mockReset();
  completeLesson.mockReset();
  notify.mockReset();
});

function wrap() {
  return render(
    <MemoryRouter>
      <Stream />
    </MemoryRouter>,
  );
}

describe("Stream (Academy Reels)", () => {
  it("renders each lesson as a panel plus a wrap-up", async () => {
    dailyLessons.mockResolvedValue([
      { id: 1, day: 1, title: "Variables", content: "Basics", completed: false },
      { id: 2, day: 2, title: "Loops", content: "Iterate", completed: true },
    ]);
    wrap();
    expect(await screen.findByText("Variables")).toBeInTheDocument();
    expect(screen.getByText("Loops")).toBeInTheDocument();
    // Wrap-up panel mentions progress (1 of 2 done).
    expect(screen.getByText(/1 of 2 lessons done/i)).toBeInTheDocument();
  });

  it("completes a lesson and shows XP feedback", async () => {
    dailyLessons.mockResolvedValue([
      { id: 1, day: 1, title: "Variables", content: "Basics", completed: false },
    ]);
    completeLesson.mockResolvedValue({ level: 2, streak: 3, new_achievements: [] });
    wrap();
    const btn = await screen.findByRole("button", { name: /mark complete/i });
    fireEvent.click(btn);
    await waitFor(() => expect(completeLesson).toHaveBeenCalledWith(1));
    expect(notify).toHaveBeenCalledWith(expect.stringContaining("level 2"), "success");
  });

  it("shows an empty state with no lessons", async () => {
    dailyLessons.mockResolvedValue([]);
    wrap();
    expect(await screen.findByText(/no lessons in your stream yet/i)).toBeInTheDocument();
  });
});
