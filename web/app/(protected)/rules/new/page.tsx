import { RuleForm } from "@/components/rule-form";
import { requireUser } from "@/lib/auth";
import { serverApi } from "@/lib/server-api";
import type { SourceOut } from "@/lib/types";

export default async function NewRulePage() {
  const user = await requireUser();
  if (user.role !== "admin") {
    return (
      <section className="frame panel">
        <div className="title">rules</div>
        <p className="subtitle">admin access is required to create rules.</p>
      </section>
    );
  }

  const sources = await serverApi<SourceOut[]>("/sources?limit=200");

  return (
    <section className="frame panel stack">
      <div>
        <div className="title">new rule</div>
        <p className="subtitle">define matching logic and alert delivery targets.</p>
      </div>
      <RuleForm sources={sources} />
    </section>
  );
}
