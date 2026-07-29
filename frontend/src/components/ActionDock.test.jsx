import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";
import ActionDock from "./ActionDock.jsx";

function wrap(open, onClose) {
  return render(
    <MemoryRouter>
      <ActionDock open={open} onClose={onClose} />
    </MemoryRouter>,
  );
}

describe("ActionDock", () => {
  it("renders nothing when closed", () => {
    const { container } = wrap(false, () => {});
    expect(container).toBeEmptyDOMElement();
  });

  it("shows create actions when open", () => {
    wrap(true, () => {});
    expect(screen.getByRole("dialog", { name: "Create" })).toBeInTheDocument();
    expect(screen.getByText("Set a new goal")).toBeInTheDocument();
    expect(screen.getByText("Host a meetup")).toBeInTheDocument();
  });

  it("closes when the scrim is clicked", () => {
    const onClose = vi.fn();
    const { container } = wrap(true, onClose);
    fireEvent.click(container.querySelector(".dock-scrim"));
    expect(onClose).toHaveBeenCalled();
  });
});
