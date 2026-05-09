import { render, screen } from "@testing-library/react";

import { LoginForm } from "./login-form";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    refresh: vi.fn(),
  }),
}));

vi.mock("@/lib/api", () => ({
  api: vi.fn(),
}));

describe("LoginForm", () => {
  it("renders a reset password link", () => {
    render(<LoginForm />);

    expect(screen.getByRole("link", { name: "reset password" })).toHaveAttribute("href", "/reset-password");
  });
});
