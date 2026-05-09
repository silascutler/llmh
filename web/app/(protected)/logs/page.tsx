import { LogTableClient } from "@/components/log-list-client";
import { SearchBar } from "@/components/search-bar";
import type { LogActor } from "@/lib/log-actors";
import { serverApi } from "@/lib/server-api";
import type { LogsPage, SessionSummaryPage } from "@/lib/types";
import type { LogSortDirection, LogSortKey } from "@/components/log-table";

const sortKeys: LogSortKey[] = ["level", "occurred_at", "source_name", "tool", "message", "tags"];
const actorFilters: Array<{ value: LogActor; label: string }> = [
  { value: "human", label: "user" },
  { value: "assistant", label: "assistant" },
  { value: "tool", label: "tool output" },
  { value: "system", label: "system" },
  { value: "other", label: "other" },
];

function formatTime(value: string) {
  return new Date(value).toLocaleString();
}

function appendParams(
  query: URLSearchParams,
  params: Record<string, string | string[] | undefined>,
  excluded: string[],
) {
  for (const [key, value] of Object.entries(params)) {
    if (excluded.includes(key)) {
      continue;
    }
    if (typeof value === "string" && value) {
      query.set(key, value);
    } else if (Array.isArray(value)) {
      value.filter(Boolean).forEach((item) => query.append(key, item));
    }
  }
}

function selectedActors(params: Record<string, string | string[] | undefined>): LogActor[] {
  const raw = params.actor;
  const values = Array.isArray(raw) ? raw : typeof raw === "string" ? [raw] : [];
  const allowed = new Set(actorFilters.map((filter) => filter.value));
  return values.filter((value): value is LogActor => allowed.has(value as LogActor));
}

function buildPageHref(params: Record<string, string | string[] | undefined>, cursor?: string | null) {
  const query = new URLSearchParams();
  appendParams(query, params, ["cursor"]);
  if (!query.has("limit")) {
    query.set("limit", "50");
  }
  if (cursor) {
    query.set("cursor", cursor);
  }
  const qs = query.toString();
  return qs ? `/logs?${qs}` : "/logs";
}

function buildSortHref(
  params: Record<string, string | string[] | undefined>,
  sortKey: LogSortKey,
  currentSortKey: LogSortKey,
  currentSortDirection: LogSortDirection,
) {
  const query = new URLSearchParams();
  appendParams(query, params, ["cursor"]);
  if (!query.has("limit")) {
    query.set("limit", "50");
  }
  const nextDirection =
    sortKey === currentSortKey ? (currentSortDirection === "asc" ? "desc" : "asc") : sortKey === "occurred_at" ? "desc" : "asc";
  query.set("sort_by", sortKey);
  query.set("sort_dir", nextDirection);
  const qs = query.toString();
  return qs ? `/logs?${qs}` : "/logs";
}

function buildTranscriptSortHref(
  params: Record<string, string | string[] | undefined>,
  sortDirection: LogSortDirection,
) {
  const query = new URLSearchParams();
  appendParams(query, params, ["cursor"]);
  if (!query.has("limit")) {
    query.set("limit", "50");
  }
  query.set("view", "transcript");
  query.set("sort_by", "occurred_at");
  query.set("sort_dir", sortDirection);
  const qs = query.toString();
  return qs ? `/logs?${qs}` : "/logs";
}

function buildSessionHref(
  params: Record<string, string | string[] | undefined>,
  sessionId?: string | null,
) {
  const query = new URLSearchParams();
  appendParams(query, params, ["cursor", "session_id"]);
  if (!query.has("limit")) {
    query.set("limit", "50");
  }
  if (sessionId) {
    query.set("session_id", sessionId);
  }
  const qs = query.toString();
  return qs ? `/logs?${qs}` : "/logs";
}

function buildSessionSortHref(
  params: Record<string, string | string[] | undefined>,
  sortDirection: "asc" | "desc",
) {
  const query = new URLSearchParams();
  appendParams(query, params, ["cursor"]);
  if (!query.has("limit")) {
    query.set("limit", "50");
  }
  query.set("session_sort", sortDirection);
  const qs = query.toString();
  return qs ? `/logs?${qs}` : "/logs";
}

function buildActorHref(
  params: Record<string, string | string[] | undefined>,
  currentActors: LogActor[],
  actor?: LogActor,
) {
  const query = new URLSearchParams();
  appendParams(query, params, ["cursor", "actor"]);
  if (!query.has("limit")) {
    query.set("limit", "50");
  }
  const nextActors =
    actor === undefined ? [] : currentActors.includes(actor) ? currentActors.filter((item) => item !== actor) : [...currentActors, actor];
  for (const item of nextActors) {
    query.append("actor", item);
  }
  const qs = query.toString();
  return qs ? `/logs?${qs}` : "/logs";
}

function buildViewHref(
  params: Record<string, string | string[] | undefined>,
  viewMode: "table" | "transcript",
) {
  const query = new URLSearchParams();
  appendParams(query, params, ["cursor", "view"]);
  if (!query.has("limit")) {
    query.set("limit", "50");
  }
  query.set("view", viewMode);
  if (viewMode === "transcript") {
    query.set("sort_by", "occurred_at");
    query.set("sort_dir", "asc");
  }
  const qs = query.toString();
  return qs ? `/logs?${qs}` : "/logs";
}

export default async function LogsPageView({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const viewMode = typeof params.view === "string" && params.view === "transcript" ? "transcript" : "table";
  const sortKey = (typeof params.sort_by === "string" ? params.sort_by : "occurred_at") as LogSortKey;
  const sortDirection = (
    typeof params.sort_dir === "string" ? params.sort_dir : viewMode === "transcript" ? "asc" : "desc"
  ) as LogSortDirection;
  const effectiveSortKey = viewMode === "transcript" ? "occurred_at" : sortKey;
  const query = new URLSearchParams();

  appendParams(query, params, []);

  if (!query.has("limit")) {
    query.set("limit", "50");
  }
  query.set("sort_by", effectiveSortKey);
  query.set("sort_dir", sortDirection);
  const sessionSortDirection = typeof params.session_sort === "string" && params.session_sort === "asc" ? "asc" : "desc";
  const actors = selectedActors(params);

  const sessionsQuery = new URLSearchParams();
  if (typeof params.source_id === "string" && params.source_id) {
    sessionsQuery.set("source_id", params.source_id);
  }
  if (typeof params.tool === "string" && params.tool) {
    sessionsQuery.set("tool", params.tool);
  }
  if (typeof params.q === "string" && params.q) {
    sessionsQuery.set("q", params.q);
  }
  for (const actor of actors) {
    sessionsQuery.append("actor", actor);
  }
  sessionsQuery.set("sort_dir", sessionSortDirection);
  sessionsQuery.set("limit", "120");

  const [page, sessions] = await Promise.all([
    serverApi<LogsPage>(`/logs?${query.toString()}`),
    serverApi<SessionSummaryPage>(`/logs/sessions?${sessionsQuery.toString()}`),
  ]);
  const nextHref = page.next_cursor
    ? buildPageHref({ ...params, sort_by: effectiveSortKey, sort_dir: sortDirection }, page.next_cursor)
    : null;
  const selectedSessionId = typeof params.session_id === "string" ? params.session_id : "";
  const clearSessionHref = buildSessionHref(params, null);
  const sortHrefs = Object.fromEntries(
    sortKeys.map((key) => [key, buildSortHref(params, key, sortKey, sortDirection)]),
  ) as Record<LogSortKey, string>;
  const newestSessionsHref = buildSessionSortHref(params, "desc");
  const oldestSessionsHref = buildSessionSortHref(params, "asc");
  const clearActorHref = buildActorHref(params, actors);
  const tableViewHref = buildViewHref(params, "table");
  const transcriptViewHref = buildViewHref(params, "transcript");
  const transcriptOldestHref = buildTranscriptSortHref(params, "asc");
  const transcriptNewestHref = buildTranscriptSortHref(params, "desc");

  return (
    <div className="logs-layout">
      <aside className="frame panel stack logs-sidebar">
        <div className="panel-header">
          <div>
            <div className="title">sessions</div>
            <div className="subtitle">jump into a single chat session before reviewing individual records.</div>
          </div>
          <span className="eyebrow">{sessions.items.length}</span>
        </div>
        <div className="cluster">
          <a className={`ghost-button inline ${sessionSortDirection === "desc" ? "active-filter" : ""}`} href={newestSessionsHref}>
            newest first
          </a>
          <a className={`ghost-button inline ${sessionSortDirection === "asc" ? "active-filter" : ""}`} href={oldestSessionsHref}>
            oldest first
          </a>
        </div>
        {selectedSessionId ? (
          <a className="ghost-button inline" href={clearSessionHref}>
            clear session filter
          </a>
        ) : null}
        <div className="session-list">
          {sessions.items.map((session) => {
            const href = buildSessionHref(params, session.session_id);
            const active = session.session_id === selectedSessionId;
            return (
              <a className={`session-link ${active ? "active" : ""}`} href={href} key={`${session.source_name}:${session.session_id}`}>
                <div className="split">
                  <span className="title-small mono">{session.session_id}</span>
                  <span className="eyebrow">{session.log_count}</span>
                </div>
                <div className="cluster muted">
                  <span>{session.source_name}</span>
                  <span>{session.tool}</span>
                </div>
                <div className="session-preview">{session.preview}</div>
                <div className="eyebrow">{formatTime(session.latest_occurred_at)}</div>
              </a>
            );
          })}
        </div>
      </aside>

      <section className="frame panel stack logs-main">
        <div className="panel-header">
          <div>
            <div className="title">logs</div>
            <div className="subtitle">query across recent entries and indexed search results.</div>
          </div>
          <span className="eyebrow">{page.estimated_total} est</span>
        </div>
        <SearchBar
          action="/logs"
          defaultValue={typeof params.q === "string" ? params.q : ""}
          hiddenFields={{
            ...(actors.length ? { actor: actors } : {}),
            ...(selectedSessionId ? { session_id: selectedSessionId } : {}),
            view: viewMode,
            sort_by: effectiveSortKey,
            sort_dir: sortDirection,
          }}
          placeholder="search full log content, project path, session text"
        />
        <div className="cluster">
          <a className={`ghost-button inline ${viewMode === "table" ? "active-filter" : ""}`} href={tableViewHref}>
            table view
          </a>
          <a className={`ghost-button inline ${viewMode === "transcript" ? "active-filter" : ""}`} href={transcriptViewHref}>
            transcript view
          </a>
          {viewMode === "transcript" ? <span className="eyebrow">chronological reconstruction</span> : null}
        </div>
        {viewMode === "transcript" ? (
          <div className="cluster">
            <a className={`ghost-button inline ${sortDirection === "asc" ? "active-filter" : ""}`} href={transcriptOldestHref}>
              oldest first
            </a>
            <a className={`ghost-button inline ${sortDirection === "desc" ? "active-filter" : ""}`} href={transcriptNewestHref}>
              newest first
            </a>
          </div>
        ) : null}
        <div className="cluster">
          <a className={`ghost-button inline ${actors.length === 0 ? "active-filter" : ""}`} href={clearActorHref}>
            all actors
          </a>
          {actorFilters.map((filter) => (
            <a
              className={`ghost-button inline ${actors.includes(filter.value) ? "active-filter" : ""}`}
              href={buildActorHref(params, actors, filter.value)}
              key={filter.value}
            >
              {filter.label}
            </a>
          ))}
        </div>
        <LogTableClient
          logs={page.items}
          sortHrefs={sortHrefs}
          sortDirection={sortDirection}
          sortKey={sortKey}
          viewMode={viewMode}
        />
        <div className="split">
          <span className="muted">showing up to {query.get("limit") ?? "50"} rows</span>
          {nextHref ? (
            <a className="ghost-button inline" href={nextHref}>
              {sortDirection === "asc" ? "newer logs" : "older logs"}
            </a>
          ) : (
            <span className="muted">end of results</span>
          )}
        </div>
      </section>
    </div>
  );
}
