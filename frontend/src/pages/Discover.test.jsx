import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Discover from "./Discover.jsx";

const discoverSkills = vi.fn();
const addSkill = vi.fn();
const notify = vi.fn();

vi.mock("../api/client.js", () => ({
  api: {
    discoverSkills: () => discoverSkills(),
    addSkill: (data) => addSkill(data),
  },
}));
vi.mock("../context/AppContext.jsx", () => ({
  useApp: () => ({ notify }),
}));

beforeEach(() => {
  Element.prototype.scrollTo = vi.fn();
  discoverSkills.mockReset();
  addSkill.mockReset();
  notify.mockReset();
});

function wrap() {
  return render(
    <MemoryRouter>
      <Discover />
    </MemoryRouter>,
  );
}

const SAMPLE = [
  { name: "Python", category: "Coding", emoji: "🐍", blurb: "Automate things.",
    hook: "In demand.", difficulty: "beginner", learners: 3, status: null },
  { name: "Guitar", category: "Music", emoji: "🎸", blurb: "Play songs.",
    hook: "Fun.", difficulty: "beginner", learners: 0, status: "want" },
];

describe("Discover (skill feed)", () => {
  it("renders a clip per skill with the three actions", async () => {
    discoverSkills.mockResolvedValue(SAMPLE);
    wrap();
    expect(await screen.findByText("Python")).toBeInTheDocument();
    expect(screen.getAllByText("Get the course").length).toBe(2);
    expect(screen.getByText("Learn it")).toBeInTheDocument();
    // "3 learners here can teach it" for Python.
    expect(screen.getByText(/3 learners here can teach it/i)).toBeInTheDocument();
  });

  it("adds a skill as 'have' when you tap I know this", async () => {
    discoverSkills.mockResolvedValue(SAMPLE);
    addSkill.mockResolvedValue({});
    wrap();
    await screen.findByText("Python");
    fireEvent.click(screen.getAllByText("I know this")[0]);
    await waitFor(() =>
      expect(addSkill).toHaveBeenCalledWith({ name: "Python", kind: "have", category: "Coding" }),
    );
    expect(notify).toHaveBeenCalledWith(expect.stringContaining("teach"), "success");
  });

  it("shows a skill already on the learning list as disabled", async () => {
    discoverSkills.mockResolvedValue(SAMPLE);
    wrap();
    await screen.findByText("Guitar");
    // Guitar has status 'want', so its Learn button reads "On your list".
    expect(screen.getByText("On your list")).toBeInTheDocument();
  });
});
