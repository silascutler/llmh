"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

type ResetPasswordFormProps = {
  initialToken?: string;
};

export function ResetPasswordForm({ initialToken = "" }: ResetPasswordFormProps) {
  const router = useRouter();
  const [token, setToken] = useState(initialToken);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (initialToken) {
      router.replace("/reset-password");
    }
  }, [initialToken, router]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("passwords do not match");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      });
      setDone(true);
      router.push("/login");
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "reset failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="stack" onSubmit={onSubmit}>
      <p className="subtitle">Use the reset token or link provided by an operator to set a new password.</p>
      <div className="field-full">
        <label className="label" htmlFor="reset-token">
          reset token
        </label>
        <textarea
          id="reset-token"
          className="textarea mono"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          required
        />
      </div>
      <div className="field-full">
        <label className="label" htmlFor="new-password">
          new password
        </label>
        <input
          id="new-password"
          className="input"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          minLength={8}
          required
        />
      </div>
      <div className="field-full">
        <label className="label" htmlFor="confirm-password">
          confirm password
        </label>
        <input
          id="confirm-password"
          className="input"
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          minLength={8}
          required
        />
      </div>
      {error ? <p className="subtitle">{error}</p> : null}
      {done ? <p className="subtitle">password reset complete. redirecting to login.</p> : null}
      <div className="cluster">
        <button className="button inline" disabled={loading} type="submit">
          {loading ? "resetting" : "set new password"}
        </button>
        <Link className="ghost-button inline mono" href="/login">
          back to login
        </Link>
      </div>
    </form>
  );
}
