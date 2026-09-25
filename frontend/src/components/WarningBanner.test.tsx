import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WarningBanner } from "./WarningBanner";

 describe("WarningBanner", () => {
  it("renders structured warnings", () => {
    render(
      <WarningBanner
        warnings={[
          {
            code: "RANKING_FALLBACK",
            severity: "error",
            message: "Showing retrieval order.",
            details: {},
          },
        ]}
      />,
    );
    expect(screen.getByText("Showing retrieval order.")).toBeTruthy();
    expect(screen.getByText("Error")).toBeTruthy();
  });

  it("renders nothing without warnings", () => {
    const { container } = render(<WarningBanner warnings={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
