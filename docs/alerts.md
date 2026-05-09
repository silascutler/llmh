# Alerts

User-defined rules evaluated **inline within ingest** — simpler than a separate queue, and latency stays low because the ingest path already has the row in memory. Rule CRUD lives at `/rules` ([api.md](api.md)).

## Pipeline

In `services.logs.ingest()`, after Meili sync:

```python
await alerts.evaluator.evaluate_for(rows, session)
```

`evaluator.evaluate_for`:
1. Loads enabled rules (cached in-process for 30 seconds — TTL bucket via a small `RulesCache` class).
2. For each `(rule, log)` pair where `match(rule, log)` is true:
   - Insert an `alert_events` row with `delivery_status = {}`.
   - Dispatch deliveries (webhook, email).
   - Update `delivery_status` with results.

(Future polish: replace the TTL cache with Postgres `LISTEN/NOTIFY` on a `alert_rules_changed` channel for instant invalidation.)

## Matching

`evaluator.match(rule, log) -> bool`:

| `match_type` | Logic |
|---|---|
| `keyword` | Case-insensitive substring on `log.message` |
| `regex`   | `re.search(pattern, log.message)`, regex compiled lazily and cached |
| `source`  | `log.source_id == rule.source_filter` |
| `tag`     | Any overlap between `log.tags` and `rule.tag_filter` |

Plus: `source_filter` and `tag_filter` are applied as additional **AND** constraints regardless of `match_type`. So a `keyword` rule with `source_filter` set fires only when both the keyword matches **and** the log came from that source.

## Delivery

### Webhook — `alerts/webhook.py`

```python
async with httpx.AsyncClient(timeout=10) as client:
    resp = await client.post(rule.webhook_url, json=payload)
```

Payload (Slack/Discord-compatible):
```json
{
  "text": "[llmh] rule 'auth failures' fired",
  "attachments": [{
    "title": "claude-code on claude-laptop",
    "text":  "build failed: missing token",
    "ts":    1745781060
  }]
}
```

### Email — `alerts/email.py`

```python
await aiosmtplib.send(
    message,
    hostname=settings.smtp_host,
    port=settings.smtp_port,
    username=settings.smtp_user,
    password=settings.smtp_password,
    start_tls=settings.smtp_starttls,
)
```

Subject: `[llmh] {rule.name} fired on {source_name}`.
Body: rule name, source, tool, level, timestamp, message snippet, link to UI log detail.
Skipped silently if `rule.email_to` is null.

### Failures

No retries in v1. Failures are logged and recorded in `alert_events.delivery_status`:

```json
{
  "webhook": { "status_code": 500, "ms": 87 },
  "email":   { "ok": false, "error": "smtp connect refused" }
}
```

A successful run looks like:

```json
{
  "webhook": { "status_code": 200, "ms": 142 },
  "email":   { "ok": true }
}
```
