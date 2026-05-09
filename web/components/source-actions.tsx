"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";

type SourceActionsProps = {
  sourceId: string;
  sourceName: string;
  canDelete?: boolean;
  returnHref?: string;
  compact?: boolean;
};

export function SourceActions({
  sourceId,
  sourceName,
  canDelete = false,
  returnHref,
  compact = false,
}: SourceActionsProps) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    const confirmed = window.confirm(`Delete source "${sourceName}" and all of its logs?`);
    if (!confirmed) {
      return;
    }
    setDeleting(true);
    try {
      await api(`/sources/${sourceId}`, { method: "DELETE" });
      if (returnHref) {
        router.push(returnHref);
        router.refresh();
        return;
      }
      router.refresh();
    } finally {
      setDeleting(false);
    }
  }

  function handleExport() {
    window.location.assign(`/api/sources/${sourceId}/export`);
  }

  return (
    <div className={`cluster ${compact ? "source-actions-compact" : ""}`}>
      <button className="ghost-button inline mono" onClick={handleExport} type="button">
        export
      </button>
      {canDelete ? (
        <button
          className="button inline mono danger-button"
          disabled={deleting}
          onClick={handleDelete}
          type="button"
        >
          {deleting ? "deleting..." : "remove"}
        </button>
      ) : null}
    </div>
  );
}
