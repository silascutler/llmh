"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";

type RuleToggleProps = {
  id: string;
  enabled: boolean;
};

export function RuleToggle({ id, enabled }: RuleToggleProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function onChange(nextEnabled: boolean) {
    setLoading(true);
    try {
      await api(`/rules/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: nextEnabled }),
      });
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <label className="cluster">
      <input disabled={loading} checked={enabled} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
      <span className="label">{loading ? "updating" : enabled ? "enabled" : "disabled"}</span>
    </label>
  );
}
