import Link from "next/link";

import { RuleToggle } from "@/components/rule-toggle";
import { SearchBar } from "@/components/search-bar";
import { requireUser } from "@/lib/auth";
import { serverApi } from "@/lib/server-api";
import type { RuleOut } from "@/lib/types";

export default async function RulesPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const user = await requireUser();
  const params = await searchParams;
  const rules = await serverApi<RuleOut[]>("/rules");
  const filtered = params.q
    ? rules.filter((rule) => {
        const needle = params.q!.toLowerCase();
        return rule.name.toLowerCase().includes(needle) || rule.match_value.toLowerCase().includes(needle);
      })
    : rules;

  return (
    <div className="content">
      <section className="frame panel stack">
        <div className="panel-header">
          <div>
            <div className="title">rules</div>
            <div className="subtitle">matchers that turn logs into alert events.</div>
          </div>
          {user.role === "admin" ? (
            <Link className="button inline mono" href="/rules/new">
              new rule
            </Link>
          ) : null}
        </div>
        <SearchBar action="/rules" defaultValue={params.q} placeholder="filter by name or matcher" />
        <div className="row-list">
          {filtered.map((rule) => (
            <article className="row-card stack" key={rule.id}>
              <div className="split">
                <div className="stack">
                  <Link className="title-small" href={`/rules/${rule.id}`}>
                    {rule.name}
                  </Link>
                  <div className="cluster muted">
                    <span className="badge">{rule.match_type}</span>
                    <span className="mono">{rule.match_value}</span>
                  </div>
                </div>
                {user.role === "admin" ? <RuleToggle id={rule.id} enabled={rule.enabled} /> : null}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
