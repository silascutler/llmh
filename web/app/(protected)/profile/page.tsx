import { ProfilePanel } from "@/components/profile-panel";
import { requireUser } from "@/lib/auth";
import { serverApi } from "@/lib/server-api";
import type { IngestTokenOut } from "@/lib/types";

export default async function ProfilePage() {
  const user = await requireUser();
  let ingestToken: string | null = null;

  if (user.role === "admin") {
    const token = await serverApi<IngestTokenOut>("/auth/ingest-token");
    ingestToken = token.token;
  }

  return <ProfilePanel user={user} ingestToken={ingestToken} />;
}
