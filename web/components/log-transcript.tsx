"use client";

import { useState } from "react";

import { formatActorLabel } from "@/lib/log-actors";
import { buildTranscriptEntries, transcriptMessage } from "@/lib/log-transcript";
import type { LogOut } from "@/lib/types";

import { LogDetailModal } from "./log-detail-modal";

function formatTime(value: string) {
  return new Date(value).toLocaleString();
}

function toolName(log: LogOut) {
  const match = transcriptMessage(log).match(/^\[tool_use:([^\]]+)\]/);
  return match?.[1] ?? "tool";
}

export function LogTranscript({ logs }: { logs: LogOut[] }) {
  const [selectedLog, setSelectedLog] = useState<LogOut | null>(null);
  const entries = buildTranscriptEntries(logs);

  return (
    <>
      <div className="transcript-shell">
        {entries.length === 0 ? <div className="muted">no logs</div> : null}
        {entries.map((entry, index) =>
          entry.kind === "tool-call" ? (
            <section className="transcript-entry tool-call-entry" key={`${entry.call.id}:${index}`}>
              <div className="transcript-rail">
                <span className="eyebrow">tool call</span>
                <span className="title-small">{toolName(entry.call)}</span>
                <span className="muted mono">{formatTime(entry.call.occurred_at)}</span>
              </div>
              <div className="transcript-body stack-tight">
                <button className="transcript-card transcript-card-call" onClick={() => setSelectedLog(entry.call)} type="button">
                  <div className="cluster muted">
                    <span>{entry.call.source_name}</span>
                    <span>{entry.call.tool}</span>
                    <span>{formatActorLabel(entry.call.actor, entry.call.tool)}</span>
                  </div>
                  <pre className="transcript-text">{transcriptMessage(entry.call)}</pre>
                </button>
                {entry.results.map((result) => (
                  <button className="transcript-card transcript-card-result" key={result.id} onClick={() => setSelectedLog(result)} type="button">
                    <div className="cluster muted">
                      <span>tool output</span>
                      <span>{formatTime(result.occurred_at)}</span>
                    </div>
                    <pre className="transcript-text">{transcriptMessage(result)}</pre>
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <section className={`transcript-entry actor-${entry.actor}`} key={`${entry.logs[0].id}:${index}`}>
              <div className="transcript-rail">
                <span className="eyebrow">{formatActorLabel(entry.actor, entry.logs[0].tool)}</span>
                <span className="title-small">{entry.logs[0].source_name}</span>
                <span className="muted mono">{formatTime(entry.logs[0].occurred_at)}</span>
              </div>
              <div className="transcript-body stack-tight">
                {entry.logs.map((log) => (
                  <button className="transcript-card" key={log.id} onClick={() => setSelectedLog(log)} type="button">
                    <div className="cluster muted">
                      <span>{log.tool}</span>
                      <span>{formatTime(log.occurred_at)}</span>
                    </div>
                    <pre className="transcript-text">{transcriptMessage(log)}</pre>
                  </button>
                ))}
              </div>
            </section>
          ),
        )}
      </div>
      <LogDetailModal log={selectedLog} onClose={() => setSelectedLog(null)} />
    </>
  );
}
