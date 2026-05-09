"use client";

import { useState } from "react";

import type { LogOut } from "@/lib/types";

import { LogDetailModal } from "./log-detail-modal";
import { LogTranscript } from "./log-transcript";
import { LogSortDirection, LogSortKey, LogTable } from "./log-table";

function formatTime(value: string) {
  return new Date(value).toLocaleString();
}

export function RecentLogCards({ logs }: { logs: LogOut[] }) {
  const [selectedLog, setSelectedLog] = useState<LogOut | null>(null);

  return (
    <>
      <div className="row-list">
        {logs.map((log) => (
          <button className="row-card stack log-card-button" key={log.id} onClick={() => setSelectedLog(log)} type="button">
            <div className="split">
              <div className="cluster log-card-heading">
                <span className={`badge ${log.level}`}>{log.level}</span>
                <span className="muted log-card-source">{log.source_name}</span>
              </div>
              <span className="eyebrow">{formatTime(log.occurred_at)}</span>
            </div>
            <div className="title-small">{log.message}</div>
          </button>
        ))}
      </div>
      <LogDetailModal log={selectedLog} onClose={() => setSelectedLog(null)} />
    </>
  );
}

export function LogTableClient({
  logs,
  sortKey,
  sortDirection,
  sortHrefs,
  viewMode,
}: {
  logs: LogOut[];
  sortKey: LogSortKey;
  sortDirection: LogSortDirection;
  sortHrefs: Partial<Record<LogSortKey, string>>;
  viewMode: "table" | "transcript";
}) {
  const [selectedLog, setSelectedLog] = useState<LogOut | null>(null);

  if (viewMode === "transcript") {
    return <LogTranscript logs={logs} />;
  }

  return (
    <>
      <LogTable
        logs={logs}
        onSelectLog={setSelectedLog}
        sortHrefs={sortHrefs}
        sortDirection={sortDirection}
        sortKey={sortKey}
      />
      <LogDetailModal log={selectedLog} onClose={() => setSelectedLog(null)} />
    </>
  );
}
