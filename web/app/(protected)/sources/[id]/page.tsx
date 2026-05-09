import Link from "next/link";
import { notFound } from "next/navigation";

import { SourceActions } from "@/components/source-actions";
import { SourceForm } from "@/components/source-form";
import { requireUser } from "@/lib/auth";
import { serverApi } from "@/lib/server-api";
import type { SourceDetail, SourceStats } from "@/lib/types";

export default async function SourceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireUser();
  const { id } = await params;

  let source: SourceDetail;
  try {
    source = await serverApi<SourceDetail>(`/sources/${id}`);
  } catch (error) {
    const status = (error as Error & { status?: number }).status;
    if (status === 404) {
      notFound();
    }
    throw error;
  }

  const stats = await serverApi<SourceStats>(`/sources/${id}/stats`);

  return (
    <div className="content">
      <section className="grid-4">
        <div className="card metric">
          <span className="eyebrow">debug</span>
          <div className="metric-value">{stats.debug}</div>
        </div>
        <div className="card metric">
          <span className="eyebrow">info</span>
          <div className="metric-value">{stats.info}</div>
        </div>
        <div className="card metric">
          <span className="eyebrow">warn</span>
          <div className="metric-value">{stats.warn}</div>
        </div>
        <div className="card metric">
          <span className="eyebrow">error</span>
          <div className="metric-value">{stats.error}</div>
        </div>
      </section>

      <section className="grid-2">
        <div className="frame panel stack">
          <div className="panel-header">
            <div>
              <div className="title">{source.name}</div>
              <div className="subtitle">
                {source.hostname || source.ip_address || "unlabeled host"}
                {source.last_seen_at ? ` · last seen ${new Date(source.last_seen_at).toLocaleString()}` : ""}
              </div>
            </div>
            <div className="cluster">
              <Link className="ghost-button inline mono" href={`/logs?source_id=${source.id}`}>
                inspect logs
              </Link>
              {user.role === "admin" ? (
                <SourceActions canDelete returnHref="/sources" sourceId={source.id} sourceName={source.name} />
              ) : null}
            </div>
          </div>
          <div className="row-card stack">
            <div className="split">
              <span className="label">log count</span>
              <span>{source.log_count}</span>
            </div>
            <div className="split">
              <span className="label">session count</span>
              <span>{source.session_count}</span>
            </div>
            <div className="split">
              <span className="label">ip address</span>
              <span>{source.ip_address ?? "n/a"}</span>
            </div>
            <div className="split">
              <span className="label">port</span>
              <span>{source.port ?? "n/a"}</span>
            </div>
            <div className="split">
              <span className="label">created</span>
              <span>{new Date(source.created_at).toLocaleString()}</span>
            </div>
            <div className="stack">
              <span className="label">tags</span>
              <div className="cluster">
                {source.tags.map((tag) => (
                  <span className="badge" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            {source.notes ? (
              <div className="stack">
                <span className="label">notes</span>
                <div className="subtitle">{source.notes}</div>
              </div>
            ) : null}
          </div>
        </div>

        {user.role === "admin" ? (
          <section className="frame panel stack">
            <div>
              <div className="title">edit source</div>
              <p className="subtitle">update host details, tags, and notes.</p>
            </div>
            <SourceForm initial={source} />
          </section>
        ) : null}
      </section>
    </div>
  );
}
