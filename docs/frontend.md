# Frontend (`web/`)

Next.js 15 App Router with React Server Components where practical. TypeScript strict, Tailwind, shadcn/ui. Talks to the FastAPI backend as a pure REST client.

## Stack

- Next.js 15 (App Router)
- TypeScript (`strict: true`)
- Tailwind CSS
- shadcn/ui primitives: `button`, `input`, `form`, `table`, `card`, `dialog`, `dropdown-menu`, `toast`, `badge`, `select`, `tabs`, `popover`, `command`
- `react-hook-form` + `zod` for forms
- `lib/api.ts` — `fetch` wrapper that sends cookies (`credentials: "include"`) and points at `process.env.NEXT_PUBLIC_API_BASE_URL`

## Routes

| Path | Page |
|---|---|
| `/login` | Login form. On success → `router.push('/')` |
| `/` | Dashboard: KPI cards (total sources, logs 24h, errors 24h, alerts 24h), 20 most recent logs table, recent alerts feed |
| `/sources` | Sortable table; "New source" button |
| `/sources/new` | `SourceForm` |
| `/sources/[id]` | Detail with tabs: **Info**, **Recent logs** (filtered by source_id), **Edit** |
| `/logs` | Search page: `SearchBar` (q + filter chips: source, tool, level, tag, date range) + `LogTable` with cursor-based infinite scroll |
| `/rules` | List with enable/disable toggle |
| `/rules/new`, `/rules/[id]` | `RuleForm` (match_type radio, value, optional source/tag filters, webhook url, email) |
| `/alerts` | Feed grouped by day; expand to show triggering log + delivery status |

## Auth Gate

`app/layout.tsx` (or a `(protected)` route group) checks `/auth/me` server-side; redirects to `/login` if 401. `/login` lives outside the gate.

The login page uses a client component that calls `/auth/login` then `router.replace('/')`. Server-side checks rely on the cookie being forwarded automatically by Next.js.

## Components

- `components/nav.tsx` — top bar with links + logout
- `components/log-table.tsx` — paginated/infinite log list
- `components/log-row.tsx` — single row with level badge, timestamp, source, message
- `components/source-form.tsx`, `rule-form.tsx` — react-hook-form + zod
- `components/search-bar.tsx` — `command` palette for query + filter chips

## API Client

`lib/api.ts`:

```ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL!;

export async function api<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
```

`lib/types.ts` mirrors the backend schemas (LogOut, SourceOut, AlertRuleOut, AlertEventOut, UserOut).
