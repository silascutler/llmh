import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { LogTable } from "./log-table";
import { LogTableClient } from "./log-list-client";

function normalizeWhitespace(value: string) {
  return value.replace(/\s+/g, " ").trim();
}

describe("LogTable", () => {
  it("shows an empty state when there are no logs", () => {
    render(<LogTable logs={[]} />);

    expect(screen.getByText("no logs")).toBeInTheDocument();
  });

  it("renders provided log rows", () => {
    render(
      <LogTable
        logs={[
          {
            id: "8de08a7b-b7ad-4ff9-8a3c-26f9d42a7c8e",
            source_id: "1a9fc253-f6c9-49c2-a548-8f0eb55d199f",
            source_name: "prod-api",
            tool: "claude-code",
            actor: "assistant",
            sender: "assistant",
            session_id: "sess-1",
            level: "error",
            message: "queue stalled",
            raw: {},
            tags: ["critical", "queue"],
            occurred_at: "2026-04-27T10:00:00Z",
            received_at: "2026-04-27T10:00:01Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("queue stalled")).toBeInTheDocument();
    expect(screen.getByText("prod-api")).toBeInTheDocument();
    expect(screen.getByText("claude-code")).toBeInTheDocument();
    expect(screen.getByText("claude")).toBeInTheDocument();
    expect(screen.getByText("critical, queue")).toBeInTheDocument();
  });

  it("calls the row selection handler when a log is clicked", async () => {
    const user = userEvent.setup();
    const onSelectLog = vi.fn();

    render(
      <LogTable
        logs={[
          {
            id: "8de08a7b-b7ad-4ff9-8a3c-26f9d42a7c8e",
            source_id: "1a9fc253-f6c9-49c2-a548-8f0eb55d199f",
            source_name: "prod-api",
            tool: "worker",
            actor: "assistant",
            sender: "assistant",
            session_id: "sess-1",
            level: "error",
            message: "queue stalled",
            raw: {},
            tags: ["critical", "queue"],
            occurred_at: "2026-04-27T10:00:00Z",
            received_at: "2026-04-27T10:00:01Z",
          },
        ]}
        onSelectLog={onSelectLog}
      />,
    );

    await user.click(screen.getAllByRole("button")[0]);
    expect(onSelectLog).toHaveBeenCalledTimes(1);
    expect(onSelectLog.mock.calls[0][0].message).toBe("queue stalled");
  });

  it("expands the full message text without opening the row modal when the message cell is clicked", async () => {
    const user = userEvent.setup();
    const onSelectLog = vi.fn();
    const summaryMessage =
      "user: This session is being continued from a previous conversation that ran out of context. The conversation is summarized below: Analysis: 1...";
    const rawContentText =
      "This session is being continued from a previous conversation that ran out of context.\nThe conversation is summarized below:\nAnalysis:\n1. This is the full imported transcript text.";

    render(
      <LogTable
        logs={[
          {
            id: "8de08a7b-b7ad-4ff9-8a3c-26f9d42a7c8f",
            source_id: "1a9fc253-f6c9-49c2-a548-8f0eb55d199f",
            source_name: "prod-api",
            tool: "worker",
            actor: "human",
            sender: "user",
            session_id: "sess-1",
            level: "info",
            message: summaryMessage,
            raw: { content_text: rawContentText },
            tags: ["transcript"],
            occurred_at: "2026-04-27T10:00:00Z",
            received_at: "2026-04-27T10:00:01Z",
          },
        ]}
        onSelectLog={onSelectLog}
      />,
    );

    const messageButton = screen.getByRole("button", { name: rawContentText });
    expect(messageButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText(summaryMessage)).toBeInTheDocument();

    await user.click(messageButton);

    expect(messageButton).toHaveAttribute("aria-expanded", "true");
    expect(normalizeWhitespace(messageButton.textContent ?? "")).toBe(normalizeWhitespace(rawContentText));
    expect(onSelectLog).not.toHaveBeenCalled();
  });

  it("renders sortable header links for server-side sorting", () => {
    render(
      <LogTableClient
        logs={[
          {
            id: "1",
            source_id: "1a9fc253-f6c9-49c2-a548-8f0eb55d199f",
            source_name: "zeta",
            tool: "worker",
            actor: "assistant",
            sender: "assistant",
            session_id: "sess-1",
            level: "info",
            message: "older row",
            raw: {},
            tags: ["one"],
            occurred_at: "2026-04-27T09:00:00Z",
            received_at: "2026-04-27T09:00:01Z",
          },
          {
            id: "2",
            source_id: "1a9fc253-f6c9-49c2-a548-8f0eb55d199f",
            source_name: "alpha",
            tool: "api",
            actor: "human",
            sender: "user",
            session_id: "sess-2",
            level: "error",
            message: "newer row",
            raw: {},
            tags: ["two"],
            occurred_at: "2026-04-27T10:00:00Z",
            received_at: "2026-04-27T10:00:01Z",
          },
        ]}
        sortHrefs={{
          level: "/logs?sort_by=level&sort_dir=asc",
          occurred_at: "/logs?sort_by=occurred_at&sort_dir=asc",
          source_name: "/logs?sort_by=source_name&sort_dir=asc",
          tool: "/logs?sort_by=tool&sort_dir=asc",
          message: "/logs?sort_by=message&sort_dir=asc",
          tags: "/logs?sort_by=tags&sort_dir=asc",
        }}
        sortDirection="desc"
        sortKey="occurred_at"
      />,
    );

    expect(screen.getByRole("link", { name: /time ↓/i })).toHaveAttribute("href", "/logs?sort_by=occurred_at&sort_dir=asc");
    expect(screen.getByRole("link", { name: /source ↕/i })).toHaveAttribute("href", "/logs?sort_by=source_name&sort_dir=asc");
  });
});
