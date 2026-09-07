# TrackFlow UI

React + TypeScript single-page app for the [TrackFlow API](../README.md).

Built with Vite, Tailwind CSS v4, TanStack Query and React Router.

---

## Running it

The UI needs the Django API running alongside it. From the repo root:

```bash
# terminal 1 — the API
uv run manage.py runserver          # http://127.0.0.1:8000

# terminal 2 — the UI
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

Then sign in. If you have not created a user yet, run `uv run manage.py seed_demo`
and log in as `ada` / `demo-passw0rd!`.

**There is no CORS configuration anywhere**, and none is needed: Vite proxies
`/api` through to Django, so the browser only ever talks to one origin. Point it
somewhere else with `VITE_API_TARGET`:

```bash
VITE_API_TARGET=http://127.0.0.1:8010 npm run dev
```

| Script | |
|---|---|
| `npm run dev` | Dev server with hot reload and the API proxy |
| `npm run build` | Type-check, then emit a production bundle to `dist/` |
| `npm run preview` | Serve the built bundle locally |
| `npm run typecheck` | Types only, no output |

---

## What is in it

| Screen | |
|---|---|
| **Sign in / Register** | JWT, with tokens kept in `localStorage` and refreshed transparently |
| **Organizations** | The tenants you belong to. A super admin can create one and appoint its admin; org admins manage their own roster |
| **My issues** | Every issue you can see across all projects, filtered by assigned/reported/all, status and priority |
| **Projects** | Card grid with search and visibility/status filters; create a project |
| **Board** | Kanban with drag-to-transition |
| **Issues** | Dense table view of the same data |
| **Members** | Add, re-role and remove people |
| **Issue panel** | Slide-over with description editing, assignee/priority/type, comments and the activity timeline |

Dark and light themes, chosen from the system preference and remembered per
browser.

---

## How it is put together

```
src/
├── main.tsx              # providers: QueryClient, Router, Auth, Toasts
├── App.tsx               # routes; renders <Login/> when signed out
├── index.css             # theme tokens, both palettes, animations
│
├── lib/
│   ├── types.ts          # mirrors the API's serializer shapes
│   ├── api.ts            # fetch wrapper, token storage, refresh-and-retry
│   ├── auth.tsx          # AuthProvider / useAuth
│   └── queries.ts        # every server interaction, as TanStack Query hooks
│
├── components/
│   ├── ui.tsx            # Button, Field, badges, Avatar, Modal, toasts, skeletons
│   ├── Layout.tsx        # sidebar shell + PageHeader
│   ├── Board.tsx         # kanban, drag and drop, optimistic transitions
│   ├── IssueTable.tsx    # table view
│   ├── IssuePanel.tsx    # slide-over detail
│   └── Members.tsx       # project membership management
│
└── pages/
    ├── Login.tsx          ├── Projects.tsx
    ├── ProjectDetail.tsx  ├── MyIssues.tsx
    └── Organizations.tsx  # tenants + their rosters
```

**All server state lives in TanStack Query**, never in `useState`. Components
hold only UI state — which modal is open, what is typed in a filter. Every
mutation goes through `useInvalidatingMutation`, which invalidates the lists a
write could have changed; without it a status change would update the panel and
leave the board stale.

---

## Notes on specific decisions

### The board mirrors the backend's transition graph

`Board.tsx` carries a copy of `Issue.ALLOWED_TRANSITIONS`. It is used only for
*presentation* — the instant a drag starts, columns that cannot accept the card
dim out, so an illegal move is visibly impossible before any request is made.

The backend stays the authority. A drop that somehow reaches it anyway is still
rejected by `transition_issue`, and the card animates back. Keep the two in sync
if the graph changes; the copy is a convenience, not a second source of truth.

The issue panel takes the opposite approach and renders its "Move to" buttons
straight from the API's `allowed_transitions` field, so it needs no local copy
at all.

### Transitions are optimistic, with a real rollback

Dropping a card updates the cached list immediately, then fires the request. If
the server rejects it, the previous cache snapshot is restored and a toast
explains why. This is what makes the board feel instant on a slow connection
without ever showing a state the server disagrees with.

### One in-flight token refresh

When an access token expires, several queries usually 401 at the same moment.
`api.ts` keeps a single shared refresh promise, so they queue behind one refresh
call instead of firing a stampede. If the refresh fails, the app dispatches
`trackflow:signed-out` and drops you back to the sign-in screen rather than
looping.

### `is_superuser` is a rendering hint, not a grant

The profile endpoint exposes `is_superuser` so the UI knows whether to offer
"New organization". Every one of those endpoints checks the flag again on the
server; the field only stops us showing a button that would 403.

### Permissions are enforced server-side, reflected client-side

`canWrite` decides whether to *show* edit controls; it is never what protects
the data. A viewer who forced a button into the DOM would still get a `403`.
Hiding controls is there so people are not offered actions that will fail.

### Width utilities are not composed

`inputClass` and `filterClass` are separate exports rather than one class plus a
`w-auto` override. Two competing Tailwind width utilities on one element resolve
by stylesheet order, not by which was appended last — so the override silently
loses and every filter select stretches to full width.

---

## Not built

- **Real-time updates.** Data refetches on mutation and on a 15-second stale
  window; there are no websockets, so another user's change appears on your next
  fetch rather than instantly.
- **Optimistic comment posting.** Comments wait for the round trip.
- **Bulk selection** on the issue table.
- **An org switcher.** Projects from every organization you belong to appear in
  one list, distinguished by name on the card rather than by a global filter.
- **Keyboard shortcuts** beyond `Esc` to close and `⌘↵` to submit a comment.
- **Tests.** The UI has none; the API's 167 back it.
