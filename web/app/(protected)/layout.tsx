import { Nav } from "@/components/nav";
import { requireUser } from "@/lib/auth";

export default async function ProtectedLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const user = await requireUser();

  return (
    <main className="screen">
      <div className="shell stack">
        <Nav username={user.username} />
        {children}
      </div>
    </main>
  );
}
