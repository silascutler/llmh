export type LogActor = "human" | "assistant" | "tool" | "system" | "other";

export function formatActorLabel(actor: LogActor, tool: string) {
  if (actor === "human") {
    return "human";
  }
  if (actor === "assistant") {
    if (tool === "claude-code") {
      return "claude";
    }
    if (tool.toLowerCase().includes("codex")) {
      return "codex";
    }
    return "assistant";
  }
  if (actor === "tool") {
    return "tool output";
  }
  if (actor === "system") {
    return "system";
  }
  return "other";
}

export function formatSenderLabel(sender: string | null) {
  if (!sender) {
    return "n/a";
  }
  if (sender === "user") {
    return "user";
  }
  if (sender === "assistant") {
    return "assistant";
  }
  if (sender === "tool_result") {
    return "tool_result";
  }
  return sender;
}
