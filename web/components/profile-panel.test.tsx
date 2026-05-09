import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ProfilePanel } from "./profile-panel";

vi.mock("@/lib/api", () => ({
  api: vi.fn(async () => ({ status: "ok" })),
}));

describe("ProfilePanel", () => {
  it("shows the ingest token controls for admin users", () => {
    render(
      <ProfilePanel
        user={{ id: "1", username: "admin", role: "admin", created_at: "2026-04-27T10:00:00Z" }}
        ingestToken="secret-token"
      />,
    );

    expect(screen.getByText("ingest token")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /show token/i })).toBeInTheDocument();
  });

  it("validates password confirmation client-side", async () => {
    const user = userEvent.setup();

    render(
      <ProfilePanel
        user={{ id: "1", username: "viewer", role: "viewer", created_at: "2026-04-27T10:00:00Z" }}
        ingestToken={null}
      />,
    );

    await user.type(screen.getByLabelText(/current password/i), "secret");
    await user.type(screen.getByLabelText(/^new password$/i), "secret-123");
    await user.type(screen.getByLabelText(/confirm password/i), "secret-456");
    await user.click(screen.getByRole("button", { name: /update password/i }));

    expect(screen.getByText("new passwords do not match")).toBeInTheDocument();
  });
});
