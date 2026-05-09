import { serverApi } from "@/lib/server-api";
import type { AlertEventOut } from "@/lib/types";

export default async function AlertsPage({
  searchParams,
}: {
  searchParams: Promise<{ rule_id?: string }>;
}) {
  const params = await searchParams;
  const query = new URLSearchParams();
  query.set("limit", "50");
  if (params.rule_id) {
    query.set("rule_id", params.rule_id);
  }

  const alerts = await serverApi<AlertEventOut[]>(`/alerts?${query.toString()}`);

  return (
    <div className="content">
      <section className="frame panel stack">
        <div className="panel-header">
          <div>
            <div className="title">alerts</div>
            <div className="subtitle">delivery history for rules that matched incoming logs.</div>
          </div>
          <span className="eyebrow">{alerts.length} events</span>
        </div>
        <div className="row-list">
          {alerts.map((alert) => (
            <article className="row-card stack" key={alert.id}>
              <div className="split">
                <div className="stack">
                  <div className="title-small">{alert.rule_name}</div>
                  <div>{alert.log_message}</div>
                </div>
                <span className="eyebrow">{new Date(alert.fired_at).toLocaleString()}</span>
              </div>
              <div className="cluster muted">
                <span>{alert.source_name}</span>
                <span>{new Date(alert.occurred_at).toLocaleString()}</span>
              </div>
              <pre className="card mono" style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(alert.delivery_status, null, 2)}
              </pre>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
