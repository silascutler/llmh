import Link from "next/link";

import { SourceActions } from "@/components/source-actions";
import { SearchBar } from "@/components/search-bar";
import { requireUser } from "@/lib/auth";
import { serverApi } from "@/lib/server-api";
import type { SourceOut } from "@/lib/types";

export default async function SourcesPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; tag?: string }>;
}) {
  const user = await requireUser();
  const params = await searchParams;
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.tag) query.set("tag", params.tag);
  const suffix = query.size ? `?${query.toString()}` : "";
  const sources = await serverApi<SourceOut[]>(`/sources${suffix}`);

  return (
    <div className="content">
      <section className="frame panel stack">
        <div className="panel-header">
          <div>
            <div className="title">sources</div>
            <div className="subtitle">inventory of systems sending logs into llmh.</div>
          </div>
          {user.role === "admin" ? (
            <Link className="button inline mono" href="/sources/new">
              new source
            </Link>
          ) : null}
        </div>
        <SearchBar action="/sources" defaultValue={params.q} placeholder="search name or hostname" />
        <div className="row-list">
          {sources.map((source) => (
            <div className="row-card stack" key={source.id}>
              <div className="split">
                <Link className="stack row-card-link" href={`/sources/${source.id}`}>
                  <span className="title-small">{source.name}</span>
                </Link>
                <SourceActions
                  canDelete={user.role === "admin"}
                  compact
                  returnHref="/sources"
                  sourceId={source.id}
                  sourceName={source.name}
                />
              </div>
              <div className="source-row-meta">
                <span className="source-meta-chip">
                  <span className="source-meta-key">logs</span>
                  <span>{source.log_count}</span>
                </span>
                <span className="source-meta-chip">
                  <span className="source-meta-key">sessions</span>
                  <span>{source.session_count}</span>
                </span>
                <span className="source-meta-chip">
                  <span className="source-meta-key">host</span>
                  <span>{source.hostname || "n/a"}</span>
                </span>
                <span className="source-meta-chip">
                  <span className="source-meta-key">ip</span>
                  <span>{source.ip_address || "n/a"}</span>
                </span>
                <span className="source-meta-chip">
                  <span className="source-meta-key">port</span>
                  <span>{source.port ?? "n/a"}</span>
                </span>
                {source.tags.map((tag) => (
                  <span className="badge" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
