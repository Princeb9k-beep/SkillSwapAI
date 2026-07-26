import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import UpgradeNotice from "./UpgradeNotice.jsx";

const wrap = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe("UpgradeNotice", () => {
  it("prompts a free user to upgrade to Pro", () => {
    wrap(<UpgradeNotice tier="free" need="pro" />);
    expect(screen.getByText(/Upgrade to Pro/i)).toBeInTheDocument();
  });

  it("prompts a pro user to upgrade to Elite for an elite feature", () => {
    wrap(<UpgradeNotice tier="pro" need="elite" />);
    expect(screen.getByText(/Upgrade to Elite/i)).toBeInTheDocument();
  });

  it("renders nothing when the user already meets the tier", () => {
    const { container } = wrap(<UpgradeNotice tier="elite" need="pro" />);
    expect(container).toBeEmptyDOMElement();
  });
});
