import Link from "next/link";

import { RecentLogCards } from "@/components/log-list-client";
import { serverApi } from "@/lib/server-api";
import type { AlertEventOut, LogsPage, RuleOut, SourceOut } from "@/lib/types";

export default async function DashboardPage() {
  const [sources, logs, rules, alerts] = await Promise.all([
    serverApi<SourceOut[]>("/sources?limit=200"),
    serverApi<LogsPage>("/logs?limit=8"),
    serverApi<RuleOut[]>("/rules"),
    serverApi<AlertEventOut[]>("/alerts?limit=6"),
  ]);
  const enabledRules = rules.filter((rule) => rule.enabled).length;
  const latestSources = sources.slice(0, 5);

  return (
    <div className="content">
      <section className="metrics-grid">
        <Link className="card metric card-link" href="/sources">
          <span className="eyebrow">sources</span>
          <div className="metric-value">{sources.length}</div>
          <span className="subtitle">tracked systems</span>
        </Link>
        <Link className="card metric card-link" href="/logs">
          <span className="eyebrow">log entries</span>
          <div className="metric-value">{logs.estimated_total}</div>
          <span className="subtitle">archive total</span>
        </Link>
        <Link className="card metric card-link" href="/logs">
          <span className="eyebrow">recent logs</span>
          <div className="metric-value">{logs.items.length}</div>
          <span className="subtitle">current slice</span>
        </Link>
        <Link className="card metric card-link" href="/rules">
          <span className="eyebrow">rules</span>
          <div className="metric-value">{rules.length}</div>
          <span className="subtitle">{enabledRules} enabled</span>
        </Link>
        <Link className="card metric card-link" href="/alerts">
          <span className="eyebrow">alerts</span>
          <div className="metric-value">{alerts.length}</div>
          <span className="subtitle">recent deliveries</span>
        </Link>
      </section>

      <section className="grid-2">
        <div className="frame panel stack">
          <div className="panel-header">
            <div>
              <Link className="title dashboard-title-link" href="/logs">
                recent logs
              </Link>
              <div className="subtitle">latest activity across all connected sources.</div>
            </div>
            <Link className="ghost-button inline mono" href="/logs">
              open logs
            </Link>
          </div>
          <RecentLogCards logs={logs.items} />
        </div>

        <div className="dashboard-rail">
          <section className="frame panel stack">
            <div className="panel-header">
              <div>
                <Link className="title dashboard-title-link" href="/sources">
                  sources
                </Link>
                <div className="subtitle">latest configured systems.</div>
              </div>
              <Link className="ghost-button inline mono" href="/sources">
                view all
              </Link>
            </div>
            <div className="row-list">
              {latestSources.map((source) => (
                <Link className="row-card stack" href={`/sources/${source.id}`} key={source.id}>
                  <div className="split">
                    <span className="title-small">{source.name}</span>
                    <span className="eyebrow">{source.hostname || source.ip_address || "unlabeled host"}</span>
                  </div>
                  <div className="cluster muted">
                    <span>{source.log_count} logs</span>
                    {source.tags.map((tag) => (
                      <span className="badge" key={tag}>
                        {tag}
                      </span>
                    ))}
                  </div>
                </Link>
              ))}
            </div>
          </section>

          <section className="frame panel stack">
            <div className="panel-header">
              <div>
                <Link className="title dashboard-title-link" href="/rules">
                  rules
                </Link>
                <div className="subtitle">configured detections and delivery policy.</div>
              </div>
              <Link className="ghost-button inline mono" href="/rules">
                manage rules
              </Link>
            </div>
            <div className="row-list">
              {rules.length === 0 ? (
                <article className="row-card stack">
                  <div className="title-small">no rules configured</div>
                  <div className="subtitle">create the first detection rule to start alerting on archive activity.</div>
                </article>
              ) : (
                rules.slice(0, 4).map((rule) => (
                  <Link className="row-card stack" href={`/rules/${rule.id}`} key={rule.id}>
                    <div className="split">
                      <span className="title-small">{rule.name}</span>
                      <span className={`badge ${rule.enabled ? "info" : "debug"}`}>{rule.enabled ? "enabled" : "disabled"}</span>
                    </div>
                    <div className="subtitle">
                      {rule.match_type}: {rule.match_value}
                    </div>
                  </Link>
                ))
              )}
            </div>
          </section>

          <section className="frame panel stack">
            <div className="panel-header">
              <div>
                <Link className="title dashboard-title-link" href="/alerts">
                  alerts
                </Link>
                <div className="subtitle">most recent rule matches.</div>
              </div>
              <Link className="ghost-button inline mono" href="/alerts">
                full feed
              </Link>
            </div>
            <div className="row-list">
              {alerts.length === 0 ? (
                <article className="row-card stack">
                  <div className="title-small">no recent alerts</div>
                  <div className="subtitle">rule matches will appear here once a delivery has been recorded.</div>
                </article>
              ) : (
                alerts.map((alert) => (
                  <article className="row-card stack" key={alert.id}>
                    <div className="split">
                      <span className="title-small">{alert.rule_name}</span>
                      <span className="eyebrow">{new Date(alert.fired_at).toLocaleString()}</span>
                    </div>
                    <div>{alert.log_message}</div>
                    <div className="subtitle">{alert.source_name}</div>
                  </article>
                ))
              )}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}
