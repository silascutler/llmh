import { SourceForm } from "@/components/source-form";
import { requireUser } from "@/lib/auth";

export default async function NewSourcePage() {
  const user = await requireUser();
  if (user.role !== "admin") {
    return (
      <section className="frame panel">
        <div className="title">sources</div>
        <p className="subtitle">admin access is required to create sources.</p>
      </section>
    );
  }

  return (
    <section className="frame panel stack">
      <div>
        <div className="title">new source</div>
        <p className="subtitle">add a host or service that will submit logs.</p>
      </div>
      <SourceForm />
    </section>
  );
}
