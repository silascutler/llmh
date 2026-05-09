import type { LogOut } from "@/lib/types";

export type TranscriptEntry =
  | {
      kind: "group";
      actor: LogOut["actor"];
      logs: LogOut[];
    }
  | {
      kind: "tool-call";
      actor: "assistant";
      call: LogOut;
      results: LogOut[];
    };

export function transcriptMessage(log: LogOut) {
  const contentText = typeof log.raw.content_text === "string" ? log.raw.content_text : "";
  return contentText || log.message;
}

function isToolCallLog(log: LogOut) {
  return log.actor === "assistant" && transcriptMessage(log).startsWith("[tool_use:");
}

export function buildTranscriptEntries(logs: LogOut[]): TranscriptEntry[] {
  const entries: TranscriptEntry[] = [];

  for (let index = 0; index < logs.length; index += 1) {
    const current = logs[index];

    if (isToolCallLog(current)) {
      const results: LogOut[] = [];
      let cursor = index + 1;
      while (cursor < logs.length && logs[cursor].actor === "tool") {
        results.push(logs[cursor]);
        cursor += 1;
      }
      entries.push({
        kind: "tool-call",
        actor: "assistant",
        call: current,
        results,
      });
      index = cursor - 1;
      continue;
    }

    const previous = entries.at(-1);
    if (
      previous &&
      previous.kind === "group" &&
      previous.actor === current.actor &&
      previous.logs.at(-1)?.tool === current.tool &&
      previous.logs.at(-1)?.source_id === current.source_id
    ) {
      previous.logs.push(current);
      continue;
    }

    entries.push({
      kind: "group",
      actor: current.actor,
      logs: [current],
    });
  }

  return entries;
}
