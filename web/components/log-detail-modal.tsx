"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import type { LogOut } from "@/lib/types";
import { formatActorLabel, formatSenderLabel } from "@/lib/log-actors";

type LogDetailModalProps = {
  log: LogOut | null;
  onClose: () => void;
};

function formatTime(value: string) {
  return new Date(value).toLocaleString();
}

export function LogDetailModal({ log, onClose }: LogDetailModalProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  useEffect(() => {
    if (!log) {
      return;
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [log, onClose]);

  if (!log) {
    return null;
  }

  if (!mounted) {
    return null;
  }

  return createPortal(
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <section
        aria-modal="true"
        className="frame modal-card stack"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="panel-header">
          <div className="stack-tight">
            <div className="cluster">
              <span className={`badge ${log.level}`}>{log.level}</span>
              <span className="eyebrow">{formatTime(log.occurred_at)}</span>
            </div>
            <div className="title">{log.message}</div>
          </div>
          <button className="ghost-button inline mono" onClick={onClose} type="button">
            close
          </button>
        </div>

        <div className="stack">
          <div className="detail-grid">
            <div className="row-card stack-tight">
              <span className="label">source</span>
              <span>{log.source_name}</span>
            </div>
            <div className="row-card stack-tight">
              <span className="label">tool</span>
              <span>{log.tool}</span>
            </div>
            <div className="row-card stack-tight">
              <span className="label">actor</span>
              <span className="mono">{formatActorLabel(log.actor, log.tool)}</span>
            </div>
            <div className="row-card stack-tight">
              <span className="label">sender</span>
              <span className="mono">{formatSenderLabel(log.sender)}</span>
            </div>
            <div className="row-card stack-tight">
              <span className="label">session</span>
              <span className="mono">{log.session_id ?? "n/a"}</span>
            </div>
            <div className="row-card stack-tight">
              <span className="label">received</span>
              <span>{formatTime(log.received_at)}</span>
            </div>
          </div>

          <div className="row-card stack">
            <span className="label">tags</span>
            <div className="cluster">
              {log.tags.length ? (
                log.tags.map((tag) => (
                  <span className="badge" key={tag}>
                    {tag}
                  </span>
                ))
              ) : (
                <span className="muted">no tags</span>
              )}
            </div>
          </div>

          <div className="row-card stack">
            <span className="label">raw</span>
            <pre className="code-block mono">{JSON.stringify(log.raw, null, 2)}</pre>
          </div>
        </div>
      </section>
    </div>
    ,
    document.body,
  );
}
