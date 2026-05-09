import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SourceForm } from "./source-form";

const push = vi.fn();
const refresh = vi.fn();
const back = vi.fn();
const apiMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    back,
    push,
    refresh,
  }),
}));

vi.mock("@/lib/api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
}));

describe("SourceForm", () => {
  beforeEach(() => {
    back.mockReset();
    push.mockReset();
    refresh.mockReset();
    apiMock.mockReset();
  });

  it("confirms edits and sends null when hostname is cleared", async () => {
    const user = userEvent.setup();
    apiMock.mockResolvedValue({ id: "source-1" });

    render(
      <SourceForm
        initial={{
          id: "source-1",
          name: "archive",
          hostname: "wrong-host",
          ip_address: "10.0.0.5",
          port: 22,
          tags: [],
        }}
      />,
    );

    await user.clear(screen.getByLabelText("hostname"));
    await user.click(screen.getByRole("button", { name: "save changes" }));

    expect(screen.getByRole("dialog", { name: "save source changes?" })).toBeInTheDocument();
    expect(screen.getByText("cleared")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "confirm save" }));

    await waitFor(() => {
      expect(apiMock).toHaveBeenCalledWith(
        "/sources/source-1",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            name: "archive",
            hostname: null,
            ip_address: "10.0.0.5",
            port: 22,
            notes: null,
            tags: [],
          }),
        }),
      );
    });
    expect(push).toHaveBeenCalledWith("/sources/source-1");
    expect(refresh).toHaveBeenCalled();
  });
});
