"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";
import type { RuleOut, SourceOut } from "@/lib/types";

type RuleFormProps = {
  sources: SourceOut[];
  initial?: {
    id?: string;
    name?: string;
    enabled?: boolean;
    match_type?: "keyword" | "regex" | "source" | "tag";
    match_value?: string;
    source_filter?: string | null;
    tag_filter?: string[] | null;
    webhook_url?: string | null;
    email_to?: string | null;
  };
};

export function RuleForm({ sources, initial }: RuleFormProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: initial?.name ?? "",
    enabled: initial?.enabled ?? true,
    match_type: initial?.match_type ?? "keyword",
    match_value: initial?.match_value ?? "",
    source_filter: initial?.source_filter ?? "",
    tag_filter: (initial?.tag_filter ?? []).join(", "),
    webhook_url: initial?.webhook_url ?? "",
    email_to: initial?.email_to ?? "",
  });

  function update<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    const payload = {
      name: form.name,
      enabled: form.enabled,
      match_type: form.match_type,
      match_value: form.match_value,
      source_filter: form.source_filter || null,
      tag_filter: form.tag_filter ? form.tag_filter.split(",").map((tag) => tag.trim()).filter(Boolean) : null,
      webhook_url: form.webhook_url || null,
      email_to: form.email_to || null,
    };

    try {
      const path = initial?.id ? `/rules/${initial.id}` : "/rules";
      const method = initial?.id ? "PATCH" : "POST";
      const rule = await api<RuleOut>(path, {
        method,
        body: JSON.stringify(payload),
      });
      router.push(`/rules/${rule.id}`);
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "save failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="stack" onSubmit={onSubmit}>
      <div className="form-grid">
        <div className="field">
          <label className="label">name</label>
          <input className="input" value={form.name} onChange={(event) => update("name", event.target.value)} required />
        </div>
        <div className="field">
          <label className="label">match type</label>
          <select
            className="select"
            value={form.match_type}
            onChange={(event) => update("match_type", event.target.value as typeof form.match_type)}
          >
            <option value="keyword">keyword</option>
            <option value="regex">regex</option>
            <option value="source">source</option>
            <option value="tag">tag</option>
          </select>
        </div>
        <div className="field-full">
          <label className="label">match value</label>
          <input
            className="input mono"
            value={form.match_value}
            onChange={(event) => update("match_value", event.target.value)}
            required
          />
        </div>
        <div className="field">
          <label className="label">source filter</label>
          <select className="select" value={form.source_filter} onChange={(event) => update("source_filter", event.target.value)}>
            <option value="">any source</option>
            {sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="label">tag filter</label>
          <input
            className="input mono"
            value={form.tag_filter}
            onChange={(event) => update("tag_filter", event.target.value)}
            placeholder="critical, batch"
          />
        </div>
        <div className="field">
          <label className="label">webhook url</label>
          <input className="input mono" value={form.webhook_url} onChange={(event) => update("webhook_url", event.target.value)} />
        </div>
        <div className="field">
          <label className="label">email to</label>
          <input className="input mono" value={form.email_to} onChange={(event) => update("email_to", event.target.value)} />
        </div>
      </div>
      <label className="cluster">
        <input checked={form.enabled} onChange={(event) => update("enabled", event.target.checked)} type="checkbox" />
        <span className="label">rule enabled</span>
      </label>
      {error ? <p className="subtitle">{error}</p> : null}
      <div className="cluster">
        <button className="button inline" disabled={loading} type="submit">
          {loading ? "saving" : initial?.id ? "save changes" : "create rule"}
        </button>
        <button className="ghost-button inline" type="button" onClick={() => router.back()}>
          cancel
        </button>
      </div>
    </form>
  );
}
