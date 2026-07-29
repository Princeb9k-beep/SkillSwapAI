import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";
import RequirePlan from "./RequirePlan.jsx";

// Mock the app context so we can drive the user's tier.
const mockUser = vi.fn();
vi.mock("../context/AppContext.jsx", () => ({
  useApp: () => ({ user: mockUser() }),
}));

function wrap(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("RequirePlan", () => {
  it("blocks a free user from a pro feature", () => {
    mockUser.mockReturnValue({ tier: "free" });
    wrap(
      <RequirePlan need="pro" name="AI Twin">
        <div>secret</div>
      </RequirePlan>,
    );
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(screen.getByText("AI Twin")).toBeInTheDocument();
    expect(screen.getByText(/Upgrade to Pro/i)).toBeInTheDocument();
  });

  it("lets a pro user through to a pro feature", () => {
    mockUser.mockReturnValue({ tier: "pro" });
    wrap(
      <RequirePlan need="pro" name="AI Twin">
        <div>secret</div>
      </RequirePlan>,
    );
    expect(screen.getByText("secret")).toBeInTheDocument();
  });

  it("treats admins as elite", () => {
    mockUser.mockReturnValue({ tier: "free", is_admin: true });
    wrap(
      <RequirePlan need="elite" name="Verify">
        <div>secret</div>
      </RequirePlan>,
    );
    expect(screen.getByText("secret")).toBeInTheDocument();
  });

  it("blocks a pro user from an elite feature", () => {
    mockUser.mockReturnValue({ tier: "pro" });
    wrap(
      <RequirePlan need="elite" name="Verify">
        <div>secret</div>
      </RequirePlan>,
    );
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(screen.getByText(/Upgrade to Elite/i)).toBeInTheDocument();
  });
});
