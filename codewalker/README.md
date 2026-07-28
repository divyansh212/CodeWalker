# Penguin (Codewalker)

An agent that reads a repo's README, commit history, and blame the way a new
hire would — then, when it hits confusing legacy code, roleplays out loud
what the original author was probably thinking, in their inferred voice.
Half debugging tool, half seance.

This repo is a working scaffold: everything below actually runs. What's
stubbed vs. real is called out explicitly so you know what needs your keys
before it does anything live.

## What's real right now

- **Backend** (`/backend`) — FastAPI app, verified to boot and serve every
  route (`/api/health`, `/api/auth/github/*`, `/api/repos`, `/api/chat`).
  The LangGraph agent compiles and runs its full route → retrieve_context →
  {roleplay, answer} / oss_finder / oss_solver graph.
- **Frontend** (`/frontend`) — Next.js + Tailwind, built and served
  successfully. `/` (landing, with the fully interactive demo terminal),
  `/login`, and `/dashboard` all typecheck and render.
- **GitHub ingestion** — README + commit log via REST, blame via the
  GraphQL `Commit.blame` field (there's no REST blame endpoint), voice
  profiles built from commit message tone/frequency, blame results cached
  in Mongo per file so repeat queries don't re-hit the API.
- **Agent** — Groq for generation, Tavily scoped specifically to grounding
  the roleplay monologues (not general search), OSS issue finder via
  GitHub's `good first issue` search.

## What needs your credentials to actually do anything

Nothing above will *work* end-to-end until you fill in `.env` — there's no
way around that part being yours:

1. **MongoDB** — you already have `Cluster0` provisioned (AWS Mumbai). Drop
   its connection string into `MONGODB_URI`.
2. **GitHub OAuth app** — create one at
   [github.com/settings/developers](https://github.com/settings/developers).
   Callback URL must be exactly `http://localhost:8000/api/auth/github/callback`
   for local dev.
3. **Groq** — API key from [console.groq.com/keys](https://console.groq.com/keys).
4. **Tavily** — API key from [app.tavily.com](https://app.tavily.com).
5. **JWT_SECRET** — any random string, used to sign session tokens.

Copy `.env.example` to `.env` and fill these in.

## Running it

```bash
cp .env.example .env   # then fill it in
docker compose up --build
```

Frontend on `http://localhost:3000`, backend on `http://localhost:8000`.

Or run each side natively while developing:

```bash
# backend
cd backend
pip install -r requirements.txt --break-system-packages
uvicorn app.main:app --reload

# frontend
cd frontend
npm install
npm run dev
```

## Project layout

```
backend/
  app/
    main.py                 FastAPI app + router wiring
    config.py                env-based settings
    db.py                    Mongo (motor) connection
    auth/github_oauth.py      OAuth login/callback, session JWTs
    services/
      github_client.py        REST + GraphQL blame + issue search
      voice_profile.py         per-author commit-style aggregation
      ingestion.py             background ingest job + blame cache
      groq_client.py           Groq chat completions
      tavily_client.py         grounding search, scoped to roleplay
    agent/
      graph.py                 LangGraph wiring
      state.py                 shared agent state
      nodes/                   route, retrieve_context, roleplay,
                                answer, oss_finder, oss_solver
    api/routes_*.py            /auth, /repos, /chat endpoints

frontend/
  app/
    page.tsx                   landing page (demo terminal)
    login/page.tsx             GitHub OAuth entry
    dashboard/page.tsx          connect a repo → live terminal
  components/
    Terminal.tsx                shared demo/live terminal, typewriter engine
    HexLattice.tsx               ambient background, generated at runtime
    Nav.tsx, FeatureGrid.tsx, OssSteps.tsx, Footer.tsx, Reveal.tsx
```

## Suggested build order from here

The scaffold covers steps 1–7 of the original build plan (repo scaffold,
OAuth flow, ingestion, voice profiles, Q&A path, roleplay + Tavily
grounding, frontend chat UI). What's left, in order:

8. **Streaming responses** — `/api/chat` currently returns a single JSON
   blob; swap to Server-Sent Events so the frontend terminal can type out
   a *real* response token-by-token instead of all-at-once.
9. **Per-file blame on demand in the UI** — right now the agent infers
   `target_path` from the question text via regex; a real file browser in
   the dashboard would remove the guesswork.
10. **Deploy** — Dockerize backend → AWS free tier; frontend → Vercel.
    Both Dockerfiles are already in place; this step just needs your AWS
    and Vercel accounts.
11. **Feature 2 polish** — `oss_finder`/`oss_solver` are functional but
    basic (no persisted `oss_recommendations` cache yet, per the original
    data model notes).

## A note on the demo terminal on the landing page

The landing page's terminal (`mode="demo"` in `Terminal.tsx`) is
intentionally **not** wired to the backend — it's canned responses keyed
by keyword, for visitors who haven't connected a repo yet. The dashboard's
terminal (`mode="live"`) is the real one, calling `/api/chat` against
whichever repo you ingested.
