"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";
import type { SourceOut } from "@/lib/types";

type SourceFormProps = {
  initial?: {
    id?: string;
    name?: string;
    hostname?: string | null;
    ip_address?: string | null;
    port?: number | null;
    notes?: string | null;
    tags?: string[];
  };
};

type SourcePayload = {
  name: string;
  hostname: string | null;
  ip_address: string | null;
  port: number | null;
  notes: string | null;
  tags: string[];
};

export function SourceForm({ initial }: SourceFormProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pendingPayload, setPendingPayload] = useState<SourcePayload | null>(null);
  const [form, setForm] = useState({
    name: initial?.name ?? "",
    hostname: initial?.hostname ?? "",
    ip_address: initial?.ip_address ?? "",
    port: initial?.port ? String(initial.port) : "",
    notes: initial?.notes ?? "",
    tags: (initial?.tags ?? []).join(", "),
  });

  function update(key: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function buildPayload(): SourcePayload {
    return {
      name: form.name,
      hostname: form.hostname.trim() || null,
      ip_address: form.ip_address || null,
      port: form.port ? Number(form.port) : null,
      notes: form.notes || null,
      tags: form.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
    };
  }

  async function saveSource(payload: SourcePayload) {
    setLoading(true);
    setError(null);
    try {
      const path = initial?.id ? `/sources/${initial.id}` : "/sources";
      const method = initial?.id ? "PATCH" : "POST";
      const source = await api<SourceOut>(path, {
        method,
        body: JSON.stringify(payload),
      });
      router.push(`/sources/${source.id}`);
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "save failed");
    } finally {
      setLoading(false);
      setPendingPayload(null);
    }
  }

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPendingPayload(buildPayload());
  }

  return (
    <>
      <form className="stack" onSubmit={onSubmit}>
        <div className="form-grid">
          <div className="field">
            <label className="label" htmlFor="source-name">
              name
            </label>
            <input
              className="input"
              id="source-name"
              value={form.name}
              onChange={(event) => update("name", event.target.value)}
              required
            />
          </div>
          <div className="field">
            <label className="label" htmlFor="source-hostname">
              hostname
            </label>
            <input
              className="input"
              id="source-hostname"
              value={form.hostname}
              onChange={(event) => update("hostname", event.target.value)}
              placeholder="optional"
            />
          </div>
          <div className="field">
            <label className="label" htmlFor="source-ip-address">
              ip address
            </label>
            <input className="input" id="source-ip-address" value={form.ip_address} onChange={(event) => update("ip_address", event.target.value)} />
          </div>
          <div className="field">
            <label className="label" htmlFor="source-port">
              port
            </label>
            <input className="input" id="source-port" value={form.port} onChange={(event) => update("port", event.target.value)} />
          </div>
          <div className="field-full">
            <label className="label" htmlFor="source-tags">
              tags
            </label>
            <input
              className="input mono"
              id="source-tags"
              value={form.tags}
              onChange={(event) => update("tags", event.target.value)}
              placeholder="prod, batch, worker"
            />
          </div>
          <div className="field-full">
            <label className="label" htmlFor="source-notes">
              notes
            </label>
            <textarea className="textarea" id="source-notes" value={form.notes} onChange={(event) => update("notes", event.target.value)} />
          </div>
        </div>
        {error ? <p className="subtitle">{error}</p> : null}
        <div className="cluster">
          <button className="button inline" disabled={loading} type="submit">
            {loading ? "saving" : initial?.id ? "save changes" : "create source"}
          </button>
          <button className="ghost-button inline" type="button" onClick={() => router.back()}>
            cancel
          </button>
        </div>
      </form>

      {pendingPayload ? (
        <div className="modal-backdrop" role="presentation">
          <div aria-labelledby="source-save-confirm-title" aria-modal="true" className="frame modal-card confirm-card stack" role="dialog">
            <div className="stack-tight">
              <div className="title" id="source-save-confirm-title">
                {initial?.id ? "save source changes?" : "create source?"}
              </div>
              <p className="subtitle">Confirm the source details before saving.</p>
            </div>
            <div className="row-card stack-tight">
              <div className="split">
                <span className="label">name</span>
                <span>{pendingPayload.name}</span>
              </div>
              <div className="split">
                <span className="label">hostname</span>
                <span>{pendingPayload.hostname ?? "cleared"}</span>
              </div>
              <div className="split">
                <span className="label">ip address</span>
                <span>{pendingPayload.ip_address ?? "n/a"}</span>
              </div>
              <div className="split">
                <span className="label">port</span>
                <span>{pendingPayload.port ?? "n/a"}</span>
              </div>
            </div>
            <div className="cluster">
              <button className="button inline" disabled={loading} type="button" onClick={() => saveSource(pendingPayload)}>
                {loading ? "saving" : "confirm save"}
              </button>
              <button className="ghost-button inline" disabled={loading} type="button" onClick={() => setPendingPayload(null)}>
                review
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
