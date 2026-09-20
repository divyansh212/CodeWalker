"""Smoke-test the ingest -> blame -> contributor-lookup path against a real repo.

This exists to make the contributor-key-mismatch trap in CLAUDE.md visible instead
of silent. It ingests a public repo, picks one file, and prints the three things
you need side by side:

  1. the contributor keys actually stored in Mongo   (voice_profile's key)
  2. the author names GraphQL blame actually returns (retrieve_context's key)
  3. whether retrieve_context's lookup resolves      (runs the real node)

Without --path it picks the file itself, walking recently-touched files in a fixed
order until it finds one whose top blame author was actually ingested. Picking the
first file the newest commit happened to touch made the exit code depend on that
commit: land on a file whose top line was last edited by someone outside the
500-commit window and the run fails with nothing wrong with the lookup.

Usage, from the backend/ directory:

    export GITHUB_TOKEN=...
    python scripts/smoke_ingest.py torvalds/linux
    python scripts/smoke_ingest.py encode/httpx --path httpx/_client.py
    python scripts/smoke_ingest.py encode/httpx --fresh

A GitHub token is required -- GraphQL blame rejects anonymous calls. Set GITHUB_TOKEN
in your environment or in backend/.env. config.py deliberately has no token field: a
personal dev PAT is not server config. A classic PAT with no scopes works for public
repos.

Mongo comes from your normal .env (MONGODB_URI / MONGODB_DB), so run this from
backend/ where that file lives. It writes to the same collections the app uses.

Exit codes:

  0  the lookup resolved
  1  the lookup is broken -- contributor-key-mismatch, or a regression of it
  2  nothing could be tested: no token, no blame ranges, or no candidate file whose
     top blame author was ingested at all

Exit 1 means the lookup is broken and nothing else. An author who never entered the
ingest window has no contributor doc under any key, so that file cannot exercise the
lookup either way -- that is a 2.
"""

import argparse
import asyncio
import os
import sys
import traceback
from pathlib import Path

import httpx
from dotenv import dotenv_values

# Run as a script, not a module, so make `import app.*` resolve from backend/.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.nodes.retrieve_context import retrieve_context  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.services.github_client import GitHubClient  # noqa: E402
from app.services.ingestion import ingest_repo  # noqa: E402


# Caps on the candidate walk: enough files to get past a docs-only commit, few
# enough that a bad repo cannot fire off dozens of blame queries.
MAX_CANDIDATE_COMMITS = 5
MAX_CANDIDATE_FILES = 20


def rule(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 60 - len(title)))


def short(value, width: int = 58) -> str:
    text = "None" if value is None else str(value)
    # ASCII only: Windows consoles default to cp1252 and choke on nicer glyphs.
    return text if len(text) <= width else text[: width - 3] + "..."


def resolve_token(flag: str = "") -> str:
    """--token flag, then GITHUB_TOKEN in the environment, then GITHUB_TOKEN in .env.

    The token stays out of config.py on purpose -- Settings is server config and a
    personal dev PAT is not. Settings sets extra = "ignore", so GITHUB_TOKEN can sit
    in the same .env without pydantic complaining, but that also means Settings never
    surfaces it, so read the file directly.
    """
    if flag:
        return flag.strip()
    from_env = os.environ.get("GITHUB_TOKEN", "").strip()
    if from_env:
        return from_env
    from_file = dotenv_values(BACKEND_ROOT / ".env").get("GITHUB_TOKEN") or ""
    return from_file.strip()


async def candidate_paths(client: GitHubClient, owner: str, repo: str, commits: list) -> list:
    """Recently touched files: newest commit first, filenames sorted within each.

    Sorted so the pick does not depend on the order the API happens to list files in.
    Two caps keep this from turning into a blame-call spree on a big merge.
    """
    paths: list = []
    async with httpx.AsyncClient() as http:
        for c in commits[:MAX_CANDIDATE_COMMITS]:
            resp = await http.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits/{c['sha']}",
                headers=client.headers,
            )
            if resp.status_code != 200:
                continue
            files = resp.json().get("files") or []
            for f in sorted(files, key=lambda f: f.get("filename") or ""):
                if f.get("status") == "removed" or not f.get("filename"):
                    continue
                if f["filename"] not in paths:
                    paths.append(f["filename"])
                    if len(paths) >= MAX_CANDIDATE_FILES:
                        return paths
    return paths


async def pick_path(
    client: GitHubClient, owner: str, repo: str, commits: list, branch: str, ingested: set
) -> tuple:
    """First candidate file whose ranges[0] author was actually ingested.

    `ingested` comes from the commit window itself, not from the contributor docs'
    key fields -- selecting on the keys the lookup matches on would let the lookup
    pick its own exam questions, and a file it cannot resolve would be quietly
    skipped instead of failing.

    Returns (path, ranges) so the caller does not blame the same file twice, or
    (None, None) when no candidate can exercise the lookup.
    """
    failures = 0
    for path in await candidate_paths(client, owner, repo, commits):
        try:
            ranges = await client.get_blame(owner, repo, path, branch=branch)
        except httpx.HTTPError as exc:
            # Blame on a very large file outruns httpx's default timeout. That is a
            # failure to ask the question, not an answer -- try the next candidate.
            failures += 1
            print(f"  skip  {short(path, 40):<40} blame failed: {type(exc).__name__}")
            continue
        if not ranges:
            continue
        author = ranges[0]["commit"]["author"]["name"]
        if author in ingested:
            return path, ranges
        print(f"  skip  {short(path, 40):<40} ranges[0] '{short(author, 18)}' not ingested")
    if failures:
        print(f"  ({failures} candidate(s) skipped because blame itself failed)")
    return None, None


async def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test ingest + contributor lookup.")
    parser.add_argument("repo", help="owner/name, e.g. encode/httpx")
    parser.add_argument(
        "--path",
        help="file to blame (default: the first recently-touched file whose top blame "
             "author was ingested)",
    )
    # Undocumented override. Prefer GITHUB_TOKEN: an argv flag lands in shell
    # history and in ps output for every user on the box.
    parser.add_argument("--token", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="drop this repo's repos doc, contributors and blame_cache first. The "
             "repos doc goes too: a surviving last_sha makes the next ingest "
             "incremental, so it fetches no commits and rebuilds no contributors. "
             "blame_cache never invalidates on its own -- the immortal-blame-cache trap",
    )
    args = parser.parse_args()

    if "/" not in args.repo:
        print("repo must be owner/name", file=sys.stderr)
        return 2
    owner, name = args.repo.split("/", 1)
    repo_key = f"{owner}/{name}"

    token = resolve_token(args.token)
    if not token:
        print(
            "No GitHub token found. Set GITHUB_TOKEN in your environment, or add it to\n"
            f"{BACKEND_ROOT / '.env'}\n"
            "GraphQL blame rejects anonymous calls, so there is nothing to check without it.\n"
            "A classic PAT with no scopes is enough for public repos.",
            file=sys.stderr,
        )
        return 2

    settings = get_settings()
    db = get_db()
    print(f"repo   {repo_key}")
    print(f"mongo  {settings.mongodb_db} on {short(settings.mongodb_uri.split('@')[-1], 40)}")

    if args.fresh:
        # The repos doc has to go as well. Leaving it keeps last_sha, which sends the
        # next ingest down the incremental path: it fetches zero commits, rebuilds
        # zero contributors, and the empty collection reads exactly like a broken
        # lookup.
        gone_r = (await db.repos.delete_one({"_id": repo_key})).deleted_count
        gone_c = (await db.contributors.delete_many({"repo": repo_key})).deleted_count
        gone_b = (await db.blame_cache.delete_many(
            {"_id": {"$regex": f"^{repo_key}:"}}
        )).deleted_count
        print(f"fresh  cleared {gone_r} repo doc, {gone_c} contributors, "
              f"{gone_b} blame_cache entries")

    rule("1. ingest")
    await ingest_repo(token, owner, name)
    repo_doc = await db.repos.find_one({"_id": repo_key}) or {}
    print(f"status          {repo_doc.get('status')}")
    print(f"default_branch  {repo_doc.get('default_branch')}")
    print(f"commit_count    {repo_doc.get('commit_count')}")
    print(f"readme          {len(repo_doc.get('readme') or '')} chars")

    client = GitHubClient(token)
    branch = repo_doc.get("default_branch", "main")
    # Fetched once, reused by path selection and by section 4's login mapping.
    commits = await client.get_commits(owner, name)
    ingested = {c["author_name"] for c in commits if c.get("author_name")}
    ingested |= {c["author_login"] for c in commits if c.get("author_login")}

    preblamed = None
    if args.path:
        path = args.path
    else:
        path, preblamed = await pick_path(client, owner, name, commits, branch, ingested)
        if path is None:
            print(
                "no testable file found in the ingest window -- every candidate file was "
                "either\nblamed to an author outside the ingested commits (no contributor "
                "doc under any\nkey, so the lookup cannot be exercised either way) or "
                "could not be blamed at all.\nTry --fresh (an incremental ingest fetches "
                "no commits), --path with a recently\ntouched file, or a repo whose "
                "history fits the window.",
                file=sys.stderr,
            )
            return 2
    print(f"file under test  {path}")

    rule("2. contributor keys in Mongo (what voice_profile stored)")
    stored = await db.contributors.find({"repo": repo_key}).to_list(length=None)
    stored_keys = {c["author"] for c in stored}
    print(f"{len(stored)} contributor docs")
    # msgs is informational only -- it is how many raw commit messages ingest kept for
    # this contributor, which is what reaches the prompts. It does not affect the exit
    # code; scripts/smoke_prompts.py is what actually asserts on that.
    for c in sorted(stored, key=lambda c: -c.get("commit_count", 0))[:10]:
        words = ", ".join(c.get("top_words", [])[:4])
        msgs = len(c.get("recent_messages") or [])
        print(f"  {short(c['author'], 24):<24} {c.get('commit_count', 0):>4} commits  "
              f"{msgs:>2} msgs  [{words}]")
    if len(stored) > 10:
        print(f"  ... and {len(stored) - 10} more")

    rule("3. author names from GraphQL blame (what retrieve_context looks up)")
    ranges = preblamed if preblamed is not None else await client.get_blame(
        owner, name, path, branch=branch
    )
    if not ranges:
        print(f"no blame ranges for {path} -- wrong path or empty file, nothing to compare")
        return 2
    blame_names = []
    for r in ranges:
        n = r["commit"]["author"]["name"]
        if n not in blame_names:
            blame_names.append(n)
    print(f"{len(ranges)} ranges, {len(blame_names)} distinct author names")
    for n in blame_names[:10]:
        hit = "match in mongo" if n in stored_keys else "NO MATCH"
        print(f"  {short(n, 28):<28} {hit}")

    rule("4. are these the same people? (login vs git display name)")
    # Commits carry both keys, so we can prove the two lists describe one person.
    name_to_login = {}
    for c in commits:
        if c.get("author_name") and c.get("author_login"):
            name_to_login.setdefault(c["author_name"], c["author_login"])
    for n in blame_names[:10]:
        login = name_to_login.get(n)
        if login is None:
            print(f"  blame '{short(n, 24)}' -> no login seen in commit log")
        elif login in stored_keys:
            print(f"  blame '{short(n, 24)}' -> login '{login}' IS the mongo key"
                  f"{'' if n == login else '  <-- mismatch, lookup will miss'}")
        else:
            print(f"  blame '{short(n, 24)}' -> login '{login}' but no such mongo key")

    rule("5. does retrieve_context actually resolve?")
    first = ranges[0]["commit"]["author"]["name"]
    print(f"retrieve_context keys on ranges[0] author name: '{first}'")
    state = {
        "query": f"why is {path} written this way",
        "repo_owner": owner,
        "repo_name": name,
        "token": token,
        "target_path": path,
    }
    result = await retrieve_context(state)
    profile = (result.get("context") or {}).get("author_profile")

    if profile:
        print(f"[ok]   resolved -> author='{profile.get('author')}', "
              f"{profile.get('commit_count')} commits, "
              f"top_words={profile.get('top_words', [])[:5]}")
        print("       roleplay will run in character with real commit style.")
        return 0

    print("[FAIL] lookup returned None.")
    print("       roleplay falls back to 'an unknown contributor' with no top_words,")
    print("       which is the contributor-key-mismatch trap firing silently.")
    print(f"       wanted key: '{first}'")
    print(f"       have keys : {sorted(stored_keys)[:8]}")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception:
        # Anything unhandled is a run that broke, not a lookup that broke. Python
        # would exit 1 here, and exit 1 has to keep meaning one thing.
        traceback.print_exc()
        print("\nrun failed before it could test the lookup", file=sys.stderr)
        raise SystemExit(2)
