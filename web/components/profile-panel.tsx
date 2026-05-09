"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import type { IngestTokenOut, UserOut } from "@/lib/types";

function formatTime(value: string) {
  return new Date(value).toLocaleString();
}

export function ProfilePanel({ user, ingestToken }: { user: UserOut; ingestToken: string | null }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordStatus, setPasswordStatus] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [tokenVisible, setTokenVisible] = useState(false);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordLoading(true);
    setPasswordError(null);
    setPasswordStatus(null);

    if (newPassword !== confirmPassword) {
      setPasswordError("new passwords do not match");
      setPasswordLoading(false);
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError("new password must be at least 8 characters");
      setPasswordLoading(false);
      return;
    }

    try {
      await api("/auth/password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordStatus("password updated");
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : "password change failed");
    } finally {
      setPasswordLoading(false);
    }
  }

  async function onCopyToken() {
    if (!ingestToken) {
      return;
    }
    try {
      await navigator.clipboard.writeText(ingestToken);
      setCopyStatus("copied");
    } catch {
      setCopyStatus("copy failed");
    }
  }

  return (
    <div className="content stack">
      <section className="frame panel stack">
        <div className="panel-header">
          <div>
            <div className="title">profile</div>
            <div className="subtitle">manage your account access and client credentials.</div>
          </div>
        </div>
        <div className="profile-grid">
          <div className="row-card stack-tight">
            <span className="label">username</span>
            <span>{user.username}</span>
          </div>
          <div className="row-card stack-tight">
            <span className="label">role</span>
            <span>{user.role}</span>
          </div>
          <div className="row-card stack-tight">
            <span className="label">created</span>
            <span>{formatTime(user.created_at)}</span>
          </div>
        </div>
      </section>

      <section className="frame panel stack">
        <div className="panel-header">
          <div>
            <div className="title">password</div>
            <div className="subtitle">update the current account password used for browser login.</div>
          </div>
        </div>
        <form className="stack" onSubmit={onSubmit}>
          <div className="form-grid">
            <div className="field">
              <label className="label" htmlFor="current-password">
                current password
              </label>
              <input
                id="current-password"
                className="input"
                type="password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                required
              />
            </div>
            <div className="field">
              <label className="label" htmlFor="new-password">
                new password
              </label>
              <input
                id="new-password"
                className="input"
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                required
              />
            </div>
            <div className="field">
              <label className="label" htmlFor="confirm-password">
                confirm password
              </label>
              <input
                id="confirm-password"
                className="input"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                required
              />
            </div>
          </div>
          {passwordError ? <p className="subtitle">{passwordError}</p> : null}
          {passwordStatus ? <p className="subtitle">{passwordStatus}</p> : null}
          <div className="cluster">
            <button className="button inline" disabled={passwordLoading} type="submit">
              {passwordLoading ? "updating" : "update password"}
            </button>
          </div>
        </form>
      </section>

      <section className="frame panel stack">
        <div className="panel-header">
          <div>
            <div className="title">ingest token</div>
            <div className="subtitle">use this bearer token with standalone shippers and import clients.</div>
          </div>
        </div>
        {ingestToken ? (
          <div className="stack">
            <pre className="code-block mono">{tokenVisible ? ingestToken : "•".repeat(Math.max(24, ingestToken.length))}</pre>
            <div className="cluster">
              <button className="ghost-button inline" onClick={() => setTokenVisible((current) => !current)} type="button">
                {tokenVisible ? "hide token" : "show token"}
              </button>
              <button className="ghost-button inline" onClick={onCopyToken} type="button">
                copy token
              </button>
              {copyStatus ? <span className="eyebrow">{copyStatus}</span> : null}
            </div>
          </div>
        ) : (
          <p className="subtitle">ingest token display is restricted to admin accounts.</p>
        )}
      </section>
    </div>
  );
}
