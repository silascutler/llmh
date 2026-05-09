import type { LogOut } from "@/lib/types";

import { LogRow } from "./log-row";

export type LogSortKey = "level" | "occurred_at" | "source_name" | "tool" | "message" | "tags";
export type LogSortDirection = "asc" | "desc";

const columns: Array<{ key?: LogSortKey; label: string }> = [
  { key: "level", label: "level" },
  { key: "occurred_at", label: "time" },
  { key: "source_name", label: "source" },
  { key: "tool", label: "tool" },
  { label: "actor" },
  { key: "message", label: "message" },
  { key: "tags", label: "tags" },
];

export function LogTable({
  logs,
  onSelectLog,
  sortKey,
  sortDirection,
  sortHrefs,
}: {
  logs: LogOut[];
  onSelectLog?: (log: LogOut) => void;
  sortKey?: LogSortKey;
  sortDirection?: LogSortDirection;
  sortHrefs?: Partial<Record<LogSortKey, string>>;
}) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {columns.map((column) => {
              const active = column.key ? sortKey === column.key : false;
              const indicator = !active ? "↕" : sortDirection === "asc" ? "↑" : "↓";
              return (
                <th key={column.label}>
                  {column.key && sortHrefs?.[column.key] ? (
                    <a
                      className={`table-sort ${active ? "active" : ""}`}
                      href={sortHrefs[column.key]}
                    >
                      <span>{column.label}</span>
                      <span className="table-sort-indicator">{indicator}</span>
                    </a>
                  ) : (
                    column.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {logs.length === 0 ? (
            <tr>
              <td colSpan={7} className="muted">
                no logs
              </td>
            </tr>
          ) : (
            logs.map((log) => <LogRow key={log.id} log={log} onSelectLog={onSelectLog} />)
          )}
        </tbody>
      </table>
    </div>
  );
}
