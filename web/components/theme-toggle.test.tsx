import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ThemeToggle } from "./theme-toggle";

describe("ThemeToggle", () => {
  it("switches from dark to light mode and persists the selection", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    const button = screen.getByRole("button", { name: "light view" });
    await user.click(button);

    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(localStorage.getItem("llmh-theme")).toBe("light");
    expect(screen.getByRole("button", { name: "dark view" })).toBeInTheDocument();
  });
});
