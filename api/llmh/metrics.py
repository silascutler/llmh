from __future__ import annotations

from collections import defaultdict
from threading import Lock


class MetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = (name, tuple(sorted((label, str(raw_value)) for label, raw_value in labels.items())))
        with self._lock:
            self._counters[key] += value

    def render(self) -> str:
        with self._lock:
            items = sorted(self._counters.items(), key=lambda item: (item[0][0], item[0][1]))
        lines = [
            "# HELP llmh_http_requests_total Total HTTP requests processed.",
            "# TYPE llmh_http_requests_total counter",
            "# HELP llmh_logs_ingested_total Total logs persisted.",
            "# TYPE llmh_logs_ingested_total counter",
            "# HELP llmh_logs_deduplicated_total Total logs skipped due to idempotency_key reuse.",
            "# TYPE llmh_logs_deduplicated_total counter",
            "# HELP llmh_alert_events_total Total alert events created.",
            "# TYPE llmh_alert_events_total counter",
            "# HELP llmh_rule_cache_invalidations_total Total in-process rule cache invalidations.",
            "# TYPE llmh_rule_cache_invalidations_total counter",
        ]
        for (name, labels), value in items:
            metric_name = f"llmh_{name}"
            if labels:
                label_text = ",".join(f'{key}="{val}"' for key, val in labels)
                lines.append(f"{metric_name}{{{label_text}}} {value}")
            else:
                lines.append(f"{metric_name} {value}")
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


metrics = MetricsStore()
