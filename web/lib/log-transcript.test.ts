import { buildTranscriptEntries, transcriptMessage } from "./log-transcript";
import type { LogOut } from "./types";

function makeLog(overrides: Partial<LogOut> & Pick<LogOut, "id" | "actor" | "message">): LogOut {
  return {
    id: overrides.id,
    source_id: overrides.source_id ?? "source-1",
    source_name: overrides.source_name ?? "archive-host",
    tool: overrides.tool ?? "claude-code",
    actor: overrides.actor,
    sender: overrides.sender ?? null,
    session_id: overrides.session_id ?? "session-1",
    level: overrides.level ?? "info",
    message: overrides.message,
    raw: overrides.raw ?? {},
    tags: overrides.tags ?? [],
    occurred_at: overrides.occurred_at ?? "2026-04-27T10:00:00Z",
    received_at: overrides.received_at ?? "2026-04-27T10:00:01Z",
  };
}

describe("log-transcript", () => {
  it("prefers raw content text for transcript display", () => {
    const log = makeLog({
      id: "1",
      actor: "human",
      message: "user: shortened summary",
      raw: { content_text: "original imported body" },
    });

    expect(transcriptMessage(log)).toBe("original imported body");
  });

  it("groups consecutive actor messages and pairs tool calls with following tool output", () => {
    const entries = buildTranscriptEntries([
      makeLog({ id: "1", actor: "human", sender: "user", message: "user: first question" }),
      makeLog({ id: "2", actor: "human", sender: "user", message: "user: second question" }),
      makeLog({
        id: "3",
        actor: "assistant",
        sender: "assistant",
        message: "assistant: [tool_use:Bash] <truncated-depth>",
        raw: { content_text: "[tool_use:Bash] ls -la" },
      }),
      makeLog({
        id: "4",
        actor: "tool",
        sender: "tool_result",
        message: "tool_result: output",
        raw: { content_text: "README.md\nsrc" },
      }),
      makeLog({ id: "5", actor: "assistant", sender: "assistant", message: "assistant: here is what I found" }),
    ]);

    expect(entries).toHaveLength(3);
    expect(entries[0]).toMatchObject({ kind: "group", actor: "human" });
    if (entries[0].kind !== "group") {
      throw new Error("expected group");
    }
    expect(entries[0].logs).toHaveLength(2);

    expect(entries[1]).toMatchObject({ kind: "tool-call" });
    if (entries[1].kind !== "tool-call") {
      throw new Error("expected tool-call");
    }
    expect(entries[1].results).toHaveLength(1);
    expect(entries[1].results[0].id).toBe("4");

    expect(entries[2]).toMatchObject({ kind: "group", actor: "assistant" });
  });
});
