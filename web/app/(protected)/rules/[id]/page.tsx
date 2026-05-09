import { notFound } from "next/navigation";

import { RuleForm } from "@/components/rule-form";
import { requireUser } from "@/lib/auth";
import { serverApi } from "@/lib/server-api";
import type { RuleOut, SourceOut } from "@/lib/types";

export default async function RuleDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireUser();
  const { id } = await params;

  let rule: RuleOut;
  try {
    rule = await serverApi<RuleOut>(`/rules/${id}`);
  } catch (error) {
    const status = (error as Error & { status?: number }).status;
    if (status === 404) {
      notFound();
    }
    throw error;
  }

  const sources = await serverApi<SourceOut[]>("/sources?limit=200");

  return (
    <div className="content">
      <section className="frame panel stack">
        <div className="panel-header">
          <div>
            <div className="title">{rule.name}</div>
            <div className="subtitle">
              {rule.match_type} matcher created {new Date(rule.created_at).toLocaleString()}
            </div>
          </div>
          <span className={`badge ${rule.enabled ? "info" : "debug"}`}>{rule.enabled ? "enabled" : "disabled"}</span>
        </div>
        <div className="row-card stack">
          <div className="split">
            <span className="label">match value</span>
            <span className="mono">{rule.match_value}</span>
          </div>
          <div className="split">
            <span className="label">source filter</span>
            <span>{rule.source_filter ?? "any source"}</span>
          </div>
          <div className="split">
            <span className="label">tag filter</span>
            <span>{rule.tag_filter?.join(", ") || "none"}</span>
          </div>
          <div className="split">
            <span className="label">webhook</span>
            <span className="mono">{rule.webhook_url ?? "none"}</span>
          </div>
          <div className="split">
            <span className="label">email</span>
            <span className="mono">{rule.email_to ?? "none"}</span>
          </div>
        </div>
      </section>

      {user.role === "admin" ? (
        <section className="frame panel stack">
          <div>
            <div className="title">edit rule</div>
            <p className="subtitle">adjust matcher scope, delivery, or state.</p>
          </div>
          <RuleForm sources={sources} initial={rule} />
        </section>
      ) : null}
    </div>
  );
}
