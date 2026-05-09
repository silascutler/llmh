import { useState } from "react";

import type { LogOut } from "@/lib/types";
import { formatActorLabel } from "@/lib/log-actors";

function formatTime(value: string) {
  return new Date(value).toLocaleString();
}

function fullMessageText(log: LogOut) {
  const contentText = typeof log.raw.content_text === "string" ? log.raw.content_text : "";
  return contentText || log.message;
}

export function LogRow({ log, onSelectLog }: { log: LogOut; onSelectLog?: (log: LogOut) => void }) {
  const [messageExpanded, setMessageExpanded] = useState(false);
  const expandedMessage = fullMessageText(log);

  return (
    <tr
      className={onSelectLog ? "table-row-button" : undefined}
      onClick={onSelectLog ? () => onSelectLog(log) : undefined}
      role={onSelectLog ? "button" : undefined}
      tabIndex={onSelectLog ? 0 : undefined}
      onKeyDown={
        onSelectLog
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectLog(log);
              }
            }
          : undefined
      }
    >
      <td>
        <span className={`badge ${log.level}`}>{log.level}</span>
      </td>
      <td className="mono muted">{formatTime(log.occurred_at)}</td>
      <td>{log.source_name}</td>
      <td>{log.tool}</td>
      <td className="mono muted">{formatActorLabel(log.actor, log.tool)}</td>
      <td className="log-message-cell">
        <button
          aria-expanded={messageExpanded}
          aria-label={expandedMessage}
          className={`log-message-button ${messageExpanded ? "expanded" : ""}`}
          onClick={(event) => {
            event.stopPropagation();
            setMessageExpanded((current) => !current);
          }}
          onKeyDown={(event) => {
            event.stopPropagation();
          }}
          type="button"
        >
          <span className={`log-message-text ${messageExpanded ? "expanded" : ""}`}>
            {messageExpanded ? expandedMessage : log.message}
          </span>
        </button>
      </td>
      <td className="mono muted">{log.tags.join(", ") || "—"}</td>
    </tr>
  );
}
