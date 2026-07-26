import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import PlanBadge from "./PlanBadge.jsx";

describe("PlanBadge", () => {
  it("renders PRO for a pro feature", () => {
    render(<PlanBadge plan="pro" />);
    expect(screen.getByText("PRO")).toBeInTheDocument();
  });

  it("renders ELITE for an elite feature", () => {
    render(<PlanBadge plan="elite" />);
    expect(screen.getByText("ELITE")).toBeInTheDocument();
  });

  it("renders nothing for a free/absent plan", () => {
    const { container } = render(<PlanBadge plan={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
