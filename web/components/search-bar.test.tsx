import { render, screen } from "@testing-library/react";

import { SearchBar } from "./search-bar";

describe("SearchBar", () => {
  it("renders a query input with the provided defaults", () => {
    render(<SearchBar action="/logs" defaultValue="panic" placeholder="search logs" />);

    const input = screen.getByPlaceholderText("search logs");
    expect(input).toHaveAttribute("name", "q");
    expect(input).toHaveValue("panic");

    const form = input.closest("form");
    expect(form).toHaveAttribute("action", "/logs");
  });

  it("uses a custom parameter name when provided", () => {
    render(<SearchBar action="/alerts" name="rule_id" placeholder="rule id" />);

    expect(screen.getByPlaceholderText("rule id")).toHaveAttribute("name", "rule_id");
  });

  it("renders hidden fields when provided", () => {
    render(
      <SearchBar
        action="/logs"
        defaultValue="panic"
        hiddenFields={{ session_id: "sess-1", tool: "claude-code" }}
        placeholder="search logs"
      />,
    );

    expect(screen.getByDisplayValue("sess-1")).toHaveAttribute("type", "hidden");
    expect(screen.getByDisplayValue("claude-code")).toHaveAttribute("type", "hidden");
  });
});
