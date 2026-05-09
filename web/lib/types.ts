export type UserOut = {
  id: string;
  username: string;
  role: "admin" | "viewer";
  created_at: string;
};

export type IngestTokenOut = {
  token: string;
};

export type SourceOut = {
  id: string;
  name: string;
  hostname: string | null;
  ip_address: string | null;
  port: number | null;
  notes: string | null;
  tags: string[];
  log_count: number;
  session_count: number;
  created_at: string;
  updated_at: string;
};

export type SourceDetail = SourceOut & {
  last_seen_at: string | null;
};

export type SourceStats = {
  debug: number;
  info: number;
  warn: number;
  error: number;
};

export type LogOut = {
  id: string;
  source_id: string;
  source_name: string;
  tool: string;
  actor: "human" | "assistant" | "tool" | "system" | "other";
  sender: string | null;
  session_id: string | null;
  level: "debug" | "info" | "warn" | "error";
  message: string;
  raw: Record<string, unknown>;
  tags: string[];
  occurred_at: string;
  received_at: string;
};

export type LogsPage = {
  items: LogOut[];
  next_cursor: string | null;
  estimated_total: number;
};

export type SessionSummary = {
  session_id: string;
  source_name: string;
  tool: string;
  log_count: number;
  latest_occurred_at: string;
  preview: string;
};

export type SessionSummaryPage = {
  items: SessionSummary[];
};

export type RuleOut = {
  id: string;
  name: string;
  enabled: boolean;
  match_type: "keyword" | "regex" | "source" | "tag";
  match_value: string;
  source_filter: string | null;
  tag_filter: string[] | null;
  webhook_url: string | null;
  email_to: string | null;
  created_by: string;
  created_at: string;
};

export type AlertEventOut = {
  id: string;
  rule_id: string;
  rule_name: string;
  log_id: string;
  log_message: string;
  source_name: string;
  occurred_at: string;
  fired_at: string;
  delivery_status: Record<string, unknown>;
};
