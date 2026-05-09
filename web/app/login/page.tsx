import { redirect } from "next/navigation";

import { LoginForm } from "@/components/login-form";
import { serverApi } from "@/lib/server-api";
import type { UserOut } from "@/lib/types";

export default async function LoginPage() {
  try {
    await serverApi<UserOut>("/auth/me");
    redirect("/");
  } catch {
    return (
      <main className="login-shell">
        <section className="frame login-card stack">
          <div className="stack">
            <span className="eyebrow">llmh access</span>
            <div>
              <div className="title">sign in</div>
            </div>
          </div>
          <LoginForm />
        </section>
      </main>
    );
  }
}
