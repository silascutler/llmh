import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SourceActions } from "./source-actions";

const push = vi.fn();
const refresh = vi.fn();
const apiMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push,
    refresh,
  }),
}));

vi.mock("@/lib/api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
}));

describe("SourceActions", () => {
  beforeEach(() => {
    push.mockReset();
    refresh.mockReset();
    apiMock.mockReset();
  });

  it("deletes a source after confirmation and returns to the sources page", async () => {
    const user = userEvent.setup();
    let resolveDelete: (() => void) | undefined;
    apiMock.mockReturnValue(new Promise<void>((resolve) => {
      resolveDelete = resolve;
    }));
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<SourceActions canDelete returnHref="/sources" sourceId="source-1" sourceName="archive-prod" />);

    const deleteButton = screen.getByRole("button", { name: "remove" });
    await user.click(deleteButton);

    expect(apiMock).toHaveBeenCalledWith("/sources/source-1", { method: "DELETE" });
    expect(screen.getByRole("button", { name: "deleting..." })).toBeDisabled();

    resolveDelete?.();

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/sources");
      expect(refresh).toHaveBeenCalled();
    });
  });
});
