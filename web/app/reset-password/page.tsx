import { ResetPasswordForm } from "@/components/reset-password-form";

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const params = await searchParams;

  return (
    <main className="login-shell">
      <section className="frame login-card stack">
        <div className="stack">
          <span className="eyebrow">llmh access</span>
          <div>
            <div className="title">reset password</div>
          </div>
        </div>
        <ResetPasswordForm initialToken={params.token} />
      </section>
    </main>
  );
}
