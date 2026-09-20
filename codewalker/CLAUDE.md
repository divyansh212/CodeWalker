# CLAUDE.md

Guidance for Claude Code when working in this repo.

## What this is

Penguin (internal name: Codewalker) is an agent that reads a GitHub repo the way a
new hire would — README first, then commit log, then the file tree, then the source
itself with `git blame` per file — builds a rough "voice profile" for each contributor
from their commit style, and then, when asked about confusing legacy code, **roleplays
in first person as the inferred author**, reasoning through why they probably wrote it
that way. Half debugging tool, half seance.

Secondary feature: open-source onboarding for people who have never opened a PR —
find a good-fit repo, surface `good first issue` candidates, and walk them through a
fix if they get stuck.

Audience is beginners. Assume no familiarity with forks, PRs, or issue etiquette in
any user-facing copy.

## The one rule that matters

**The roleplay register is the product.** It is not a tone flourish on top of a Q&A
bot. If a change makes `roleplay` output drift toward third-person description
("the author probably wanted to…"), that change is wrong. First person, in character,
no breaking frame, no meta-commentary about being an AI.

Reading the source makes this harder to hold, not easier. Plain code explanation is now
the easy output, so the roleplay register is the thing that erodes: the failure mode is
no longer a generic answer, it is a competent line-by-line walkthrough that has stopped
being anybody's voice. Explaining the code is the floor. The product is the author's
reasoning about why it is that way.

Keep the `roleplay` and `answer` system prompts in separate files so the persona can
be iterated on without touching the plain path. They are currently module-level
constants in their node files; that is acceptable, but do not merge them.

## Layout

```
codewalker/
  docker-compose.yml        backend + frontend (Mongo is Atlas, not a local service)
  .env.example              copy to .env
  backend/
    app/
      main.py               FastAPI app, CORS, router wiring
      config.py             pydantic-settings, env-backed
      db.py                 motor client (module-level singleton)
      dependencies.py       get_current_user — Bearer JWT -> payload
      auth/github_oauth.py  authorize URL, code exchange, session JWT
      services/
        github_client.py    REST (readme, meta, commits, issue search) + GraphQL blame
        voice_profile.py    per-author commit-style aggregation
        ingestion.py        background ingest job + lazy per-file blame cache
        groq_client.py      raw httpx call to Groq's OpenAI-compatible endpoint
        tavily_client.py    grounding search — scoped, see below
      agent/
        graph.py            LangGraph wiring + compiled-singleton accessor
        state.py            AgentState TypedDict
        nodes/              route, retrieve_context, roleplay, answer,
                            oss_finder, oss_solver
      api/                  routes_auth, routes_repos, routes_chat (all under /api)
    scripts/
      smoke_ingest.py       ingest -> blame -> lookup check, see Commands
  frontend/
    app/page.tsx            landing page
    app/login/page.tsx      OAuth entry
    app/dashboard/page.tsx  connect repo -> poll status -> live terminal
    components/Terminal.tsx shared terminal, mode="demo" | "live"
```

## Commands

```bash
cp .env.example .env        # then fill it in — nothing works until you do
docker compose up --build   # frontend :3000, backend :8000

# native dev
cd backend  && pip install -r requirements.txt && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev

# verify the ingest path against a real public repo (run from backend/)
export GITHUB_TOKEN=...          # or put it in .env; never pass it as an argv flag
python scripts/smoke_ingest.py encode/httpx --fresh
```

`scripts/smoke_ingest.py` is the verification step for any change to ingest, blame, or
contributor lookup. It ingests a real public repo, picks one file, and prints the
contributor keys stored in Mongo beside the author names GraphQL blame returns — then
runs the actual `retrieve_context` node and reports whether the lookup resolves. It
**exits 1 when the lookup fails**, so it doubles as a before/after check on
contributor-key-mismatch: a passing run is the evidence the fix landed, and a failing
one reproduces the bug with the wanted key and the available keys printed side by side.

Pass `--fresh` unless you specifically want cached state. `blame_cache` never
invalidates (immortal-blame-cache), so a second run without it reads stale ranges and
can report a healthier result than the code deserves. A token is required, since
GraphQL blame rejects anonymous calls — set `GITHUB_TOKEN` in your environment or
`.env`; `--token` exists as an override but keeps a live token in shell history and
`ps` output, so prefer the env var.

There is no unit test suite yet. If you add one, pytest for the backend.

## Stack and why

| Layer | Choice | Note |
|---|---|---|
| Frontend | Next.js 14 (app router), Tailwind, TypeScript | no component library |
| Backend | FastAPI, httpx, LangGraph | httpx direct, not PyGithub |
| DB | MongoDB Atlas (motor) | Cluster0, AWS Mumbai, already provisioned |
| LLM | Groq (`llama-3.3-70b-versatile`) | OpenAI-compatible endpoint |
| Grounding | Tavily | narrowly scoped, see below |
| Auth | GitHub OAuth | session JWT via python-jose |

Use a plain alphanumeric password in the Mongo connection string — special characters
need URL-encoding and it silently fails otherwise.

**Tavily is not a general search tool here.** Its only job is to ground the roleplay
monologue: when the in-character reasoning touches a library, error, or pattern, Tavily
fetches live context so the monologue is technically true rather than invented. Do not
wire it into `answer` or into a general chat path.

## Agent graph

```
route ─┬─> retrieve_context ─┬─> roleplay ─> END
       │                     └─> answer   ─> END
       ├─> oss_finder ─> END
       └─> oss_solver ─> END
```

`route` classifies by keyword/regex today (see Known traps). `retrieve_context` pulls
the README from `repos` and, if a `target_path` was extracted, blame for that file plus
the matching contributor profile.

## Data model (Mongo)

- `repos` — `_id` is `"owner/name"`. Holds `status` (`ingesting` | `ready` | `error`),
  `readme` (truncated to 20k), `default_branch`, `last_sha`, `commit_count`.
- `contributors` — one doc per `(repo, author)` with commit count, avg message length,
  `top_words`, first/last commit dates.
- `blame_cache` — `_id` is `"owner/name:path"`, holds GraphQL blame ranges.
- `file_tree` — one doc per repo, keyed to a commit SHA. The recursive tree from
  `/git/trees?recursive=1`.
- `file_cache` — one doc per `(repo, path, SHA)`. File bodies from `/contents/{path}`.
- `sessions` / `messages` — **specified but not implemented.** `/api/chat` is stateless.
- `oss_recommendations` — specified, not implemented.

`file_tree` and `file_cache` carry the SHA in their key, so both fall out of use on
their own when the repo moves. `blame_cache` does not — see immortal-blame-cache.

No indexes are declared. Add one on `contributors(repo, author)` when you touch it.

## Known traps

Read this before changing anything in the ingest/roleplay path. These are live bugs,
not hypotheticals, and every one of them fails silently.

1. **commits-never-reach-prompts** — **Commit history never reaches a prompt.** Raw
   commit messages are reduced to word counts in `build_voice_profile` and then
   discarded — nothing persists them. `answer` sends only `readme[:3000]` and ignores
   the `blame` and `author_profile` that `retrieve_context` just built. Grounding in
   commits is currently a claim, not a fact.
2. **immortal-blame-cache** — **Blame cache never invalidates.** Keyed `repo:path` with
   no SHA and no TTL. Include `last_sha` in the cache key.
3. **file-pattern-over-matches** — **`FILE_PATTERN` over-matches.** `[\w\-/]+\.\w+`
   matches `node.js`, `3.11`, `e.g`, so casual prose sets a bogus `target_path` and
   triggers blame on a path that doesn't exist. Roleplay also requires a filename *and*
   a hint word in the same message, so "why is this function so weird" routes to plain
   Q&A.
4. **commit-count-double-count** — **`commit_count` double-counts** when `since_sha`
   falls outside the 5-page fetch window, and repos over ~500 commits are silently
   truncated on first ingest.
5. **ingest-has-no-heartbeat** — **Ingestion is a FastAPI `BackgroundTask`.** A restart
   mid-ingest leaves `status: "ingesting"` forever and the dashboard polls into the
   void.
6. **tavily-query-is-a-path** — **Tavily query is `f"{target_path} {query}"`** —
   searching the web for a file path returns noise. Extract library/import names from
   the blamed code instead.
7. **blame-has-no-code** — **Roleplay reasons about code it has never seen.** GraphQL
   blame returns line ranges and commit metadata, never source. `roleplay` therefore
   works from a filename, `top_words`, and three ranges, and describes code nothing in
   the pipeline has read. Delete this entry once file fetching lands.

## Security debt

Do not ship publicly before these are fixed, and do not add features that depend on the
current shape of them.

- The GitHub access token is embedded in the session JWT. JWTs are signed, not
  encrypted, so the payload is base64 and readable by anyone holding the token.
- That token is handed to the frontend as a **URL query param** (`/dashboard?token=…`)
  and parked in `localStorage`. Query params leak into history, referrers, and logs.
- OAuth scope is `repo`, which is read *and write* on all private repos. MVP needs read
  only — `public_repo`, or `read:user` alone for public repos.
- `routes_auth.login` generates a `state` and `callback` never validates it. CSRF.

## Conventions

- Backend is async end to end. Use `httpx.AsyncClient`, never `requests`.
- New env vars go in `config.py` as typed fields **and** in `.env.example` with a comment.
- Routes live under `/api`; add routers in `main.py`, keep the prefix on the router.
- Node functions take and return `AgentState`; mutate in place and return it.
- Frontend: server components by default, `"use client"` only where hooks are needed.
  `useSearchParams` requires a `Suspense` boundary (see `dashboard/page.tsx`).

## Design system

Black, modular, precise, terminal-adjacent. The explicit goal is to not look like
generic AI SaaS: **no gradients, no glassmorphism, no glow, no SaaS blue, no large
rounded corners.** Separation comes from 1px hairline borders, never shadows.

| Token | Value | Use |
|---|---|---|
| `--ink` | `#000000` | canvas |
| `--panel` | `#0e0e11` | cards, terminal, nav |
| `--panel-2` | `#151519` | terminal header bar |
| `--hairline` | `#232228` | borders, dividers |
| `--hairline-soft` | `#19191d` | section rules |
| `--paper` | `#edeeea` | primary text (warm off-white, not pure white) |
| `--slate` | `#8d8d95` | secondary text |
| `--slate-dim` | `#5c5c62` | tertiary text |
| `--signal` | `#d6923a` | the one accent — CTAs, active states, hex icon |
| `--signal-bright` | `#e8ab5c` | signal hover |
| `--err` | `#c96a52` | errors only |

Type: Space Grotesk (display/headings), Inter (body), IBM Plex Mono (labels, buttons,
terminal, UI chrome). Radius stays 3–8px throughout.

Motifs: the hexagon (`viewBox="0 0 20 20"`, `M10 1 18 5.5v9L10 19 2 14.5v-9Z`) as an
inline icon beside eyebrow labels and as a 5% ambient background lattice; the terminal
window as the signature container for anything conversational. Use the accent sparingly —
one signal color on a black page only works if it stays rare.

## Terminal modes

`Terminal.tsx` takes `mode="demo" | "live"`. **Demo is intentionally canned** — keyword-
matched responses for visitors on the landing page who have not connected a repo. Do not
wire it to the backend. Live is the real one, posting to `/api/chat`.

## What's next

In rough order:

- Get commit messages into the prompts (commits-never-reach-prompts).
- Fetch the file tree and file contents, and stitch them to the blame ranges, so
  roleplay reasons about code it has actually read (blame-has-no-code).
- Repo briefing on ingest — an orientation pass over the repo once it is ready.
- SSE streaming on `/api/chat` so the terminal types a real response token by token.
- Repo-scoped issue suggestions.
- Voice input via Groq Whisper.
- `oss_finder` with real user context.

Then chat history (`sessions`/`messages`), a dashboard file browser so `target_path`
stops being a regex guess, and deploy (backend Docker -> AWS free tier, frontend ->
Vercel).

One practical note: pointed at itself this repo has one author and one commit, so it
cannot demo its own feature. Keep a messy long-history public repo on hand for testing.
