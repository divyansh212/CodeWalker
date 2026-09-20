"""Prove that raw commit text actually reaches the roleplay and answer prompts.

smoke_ingest.py stops one step short of this: it proves the contributor lookup
resolves, not that anything the lookup returns is ever put in front of the model.
This script asserts on the prompt strings themselves -- it runs the real node
functions with chat_completion stubbed out and checks that the commit messages are
in the text that would have been sent to Groq.

Two modes.

  fixture (default)   No network at all. Synthetic commits with sentinel strings go
                      through the real build_voice_profile and the real
                      persist_voice_profiles into Mongo under a throwaway repo key,
                      with a seeded blame_cache entry so retrieve_context needs no
                      GitHub call. Deterministic, needs no token and no API keys.

  --live owner/name   Ingests a real public repo, picks a real file the same way
                      smoke_ingest does, and checks that a commit message written by
                      a real person on GitHub lands in both prompts. This is the part
                      fixture mode cannot cover: that ingest_repo persists the field
                      end to end. Needs GITHUB_TOKEN.

Usage, from the backend/ directory:

    python scripts/smoke_prompts.py
    python scripts/smoke_prompts.py --live encode/httpx
    python scripts/smoke_prompts.py --show        # print the full prompts

Mongo comes from your normal .env, same as smoke_ingest.py. Fixture mode writes only
under the throwaway key below and deletes it again on the way out, including on
failure. It never touches a real repo's blame_cache -- that cache never invalidates
(immortal-blame-cache), so seeding fake ranges under a real key would poison it.

Exit codes:

  0  commit text reached both prompts
  1  it did not -- the missing sentinel and the prompt that lacked it are printed
  2  nothing could be tested: no Mongo, no token in --live, or no blamable file
"""

import argparse
import asyncio
import sys
import traceback
from pathlib import Path

import httpx

# Run as a script, not a module, so make `import app.*` resolve from backend/.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import smoke_ingest  # noqa: E402  -- reuse its token resolution and file picking

import app.agent.nodes.answer as answer_node  # noqa: E402
import app.agent.nodes.roleplay as roleplay_node  # noqa: E402
from app.agent.nodes.retrieve_context import retrieve_context  # noqa: E402
from app.db import get_db  # noqa: E402
from app.services.github_client import GitHubClient  # noqa: E402
from app.services.ingestion import ingest_repo, persist_voice_profiles  # noqa: E402
from app.services.voice_profile import (  # noqa: E402
    MESSAGE_CHAR_CAP,
    RECENT_MESSAGE_CAP,
    build_voice_profile,
    merge_recent_messages,
)

FIXTURE_REPO = "codewalker-smoke/prompt-fixture"
FIXTURE_PATH = "app/services/seance.py"
FIXTURE_LOGIN = "ada"
# Deliberately different from the login: blame returns the git display name, so this
# also walks the same author/author_login/author_names $or the real lookup depends on.
FIXTURE_NAME = "Ada Lovelace"

TERSE = "SENTINEL-TERSE-7f3a"
RAMBLE = "SENTINEL-RAMBLE-c41d"
OLDBATCH = "SENTINEL-OLDBATCH-90ee"
README = "SENTINEL-README-2b58"

rule = smoke_ingest.rule
short = smoke_ingest.short


class Failure(Exception):
    """A check failed: commit text did not reach where it should have. Exit 1."""


class CannotTest(Exception):
    """The run could not ask the question at all. Exit 2."""


def commit(sha: str, date: str, message: str) -> dict:
    """Shaped exactly like GitHubClient.get_commits output."""
    return {
        "sha": sha,
        "author_login": FIXTURE_LOGIN,
        "author_name": FIXTURE_NAME,
        "message": message,
        "date": date,
    }


OLD_BATCH = [
    commit("old1", "2024-01-01T10:00:00Z", "wip " + OLDBATCH),
    commit("old2", "2024-01-02T10:00:00Z", "tidy"),
]

NEW_BATCH = [
    commit("new1", "2024-03-01T10:00:00Z", TERSE),
    commit(
        "new2",
        "2024-03-02T10:00:00Z",
        RAMBLE + "\n\nI am leaving this here because the retry loop only looks wrong "
        "until you have seen the upstream close the socket mid-body. Do not simplify "
        "it without reading the issue first.",
    ),
    # Same sha as an old-batch commit, so the merge has an overlap to dedupe.
    commit("old2", "2024-01-02T10:00:00Z", "tidy"),
]


def blame_ranges() -> list:
    author = {"name": FIXTURE_NAME, "email": "ada@example.com", "date": "2024-03-02T10:00:00Z"}
    return [
        {
            "startingLine": 1,
            "endingLine": 40,
            "age": 1,
            "commit": {"oid": "new2deadbeef", "message": RAMBLE + "\n\nbody", "author": author},
        },
        {
            "startingLine": 41,
            "endingLine": 60,
            "age": 3,
            "commit": {"oid": "old1cafebabe", "message": "wip " + OLDBATCH, "author": author},
        },
    ]


def capture_prompts() -> dict:
    """Stub the two nodes' outbound calls and hand back a dict that fills with the
    prompts they built. Patched on the node modules, not on the service modules,
    because each node imported the name at import time."""
    captured: dict = {}

    def recorder(slot):
        async def fake_chat_completion(messages, **kwargs):
            captured[slot] = messages[-1]["content"]
            return "[" + slot + " response suppressed]"
        return fake_chat_completion

    async def fake_ground(query, max_results=3):
        # Tavily would be a live network call and an API key, and grounding is not
        # what this script asserts on.
        captured["ground_query"] = query
        return []

    roleplay_node.chat_completion = recorder("roleplay")
    answer_node.chat_completion = recorder("answer")
    roleplay_node.ground = fake_ground
    return captured


def require(sentinel: str, prompt: str, label: str, show: bool) -> None:
    if sentinel in prompt:
        print("  [ok]   " + label.ljust(34) + " contains " + short(sentinel, 40))
        return
    print("  [FAIL] " + label.ljust(34) + " MISSING " + short(sentinel, 40))
    if not show:
        print("\n--- prompt as built ---")
        print(prompt)
        print("--- end ---")
    raise Failure(sentinel + " never reached the " + label + " prompt")


async def run_nodes(state: dict, show: bool) -> dict:
    """retrieve_context, then both leaf nodes off the same context."""
    captured = capture_prompts()
    result = await retrieve_context(dict(state))
    context = result.get("context") or {}

    profile = context.get("author_profile")
    commits = context.get("author_commits") or []
    print("author_profile   " + (("resolved: " + str(profile.get("author"))) if profile else "None"))
    print("author_commits   " + str(len(commits)) + " message(s)")
    if not profile:
        raise Failure("retrieve_context did not resolve a contributor -- run "
                      "smoke_ingest.py, that is the lookup failing, not the prompts")
    if not commits:
        raise Failure("retrieve_context resolved a profile but carried no commit "
                      "messages: nothing persisted them, or the key changed")

    for node, route in ((roleplay_node.roleplay, "roleplay"), (answer_node.answer, "answer")):
        leaf = dict(result)
        leaf["route"] = route
        await node(leaf)

    if show:
        for slot in ("roleplay", "answer"):
            rule(slot + " prompt as sent")
            print(captured.get(slot, "<not captured>"))
    # The resolved context rides back so callers probe the author the lookup actually
    # landed on. Picking any contributor with messages compares two different people
    # and fails a pipeline that is working.
    captured["_context"] = context
    return captured


async def check_pure_helpers() -> None:
    """The cap and the merge, without a database in the way."""
    rule("0. storage bounds (no db)")

    many = [commit("s" + str(i), "2024-02-%02dT10:00:00Z" % (i % 28 + 1), "msg " + str(i))
            for i in range(40)]
    stored = build_voice_profile(many)[FIXTURE_LOGIN]["recent_messages"]
    print("40 commits in -> " + str(len(stored)) + " stored (cap " + str(RECENT_MESSAGE_CAP) + ")")
    if len(stored) != RECENT_MESSAGE_CAP:
        raise Failure("cap not applied: kept " + str(len(stored)))
    if stored != sorted(stored, key=lambda e: e["date"], reverse=True):
        raise Failure("stored messages are not newest-first")

    long_msg = build_voice_profile(
        [commit("long", "2024-02-01T10:00:00Z", "x" * 5000)]
    )[FIXTURE_LOGIN]["recent_messages"][0]["message"]
    print("5000-char message -> " + str(len(long_msg)) + " chars stored (cap "
          + str(MESSAGE_CHAR_CAP) + ")")
    if len(long_msg) > MESSAGE_CHAR_CAP:
        raise Failure("message not truncated: " + str(len(long_msg)) + " chars")

    old = build_voice_profile(OLD_BATCH)[FIXTURE_LOGIN]["recent_messages"]
    new = build_voice_profile(NEW_BATCH)[FIXTURE_LOGIN]["recent_messages"]
    merged = merge_recent_messages(old, new)
    texts = [m["message"] for m in merged]
    print("merge " + str(len(old)) + " stored + " + str(len(new)) + " incoming -> "
          + str(len(merged)) + " (deduped by sha)")
    if not any(OLDBATCH in t for t in texts):
        raise Failure("incremental merge dropped previously stored messages")
    if len({m["sha"] for m in merged}) != len(merged):
        raise Failure("merge left duplicate shas")


async def fixture_mode(show: bool) -> int:
    db = get_db()
    try:
        await db.command("ping")
    except Exception as exc:
        raise CannotTest("Mongo unreachable: " + str(exc))

    await check_pure_helpers()

    rule("1. seed the fixture through the real write path")
    await db.repos.update_one(
        {"_id": FIXTURE_REPO},
        {"$set": {"status": "ready", "default_branch": "main",
                  "readme": "# fixture\n\n" + README + "\n"}},
        upsert=True,
    )
    # Two ingests, older first, so the merge inside persist_voice_profiles is
    # exercised rather than assumed: the second write must not evict the first batch.
    await persist_voice_profiles(db, FIXTURE_REPO, build_voice_profile(OLD_BATCH))
    await persist_voice_profiles(db, FIXTURE_REPO, build_voice_profile(NEW_BATCH))
    await db.blame_cache.update_one(
        {"_id": FIXTURE_REPO + ":" + FIXTURE_PATH},
        {"$set": {"ranges": blame_ranges()}},
        upsert=True,
    )
    doc = await db.contributors.find_one({"repo": FIXTURE_REPO, "author": FIXTURE_LOGIN})
    stored = (doc or {}).get("recent_messages") or []
    print("contributor '" + FIXTURE_LOGIN + "' stored with " + str(len(stored))
          + " message(s) after two ingests")
    for m in stored:
        print("  " + str(m.get("sha")).ljust(6) + " " + (m.get("date") or "")[:10]
              + "  " + short(m.get("message", "").replace("\n", " "), 44))

    rule("2. retrieve_context")
    owner, name = FIXTURE_REPO.split("/", 1)
    captured = await run_nodes(
        {
            "query": "why does the retry loop look like that",
            "repo_owner": owner,
            "repo_name": name,
            "token": "",  # blame is cached, so no GitHub call is made
            "target_path": FIXTURE_PATH,
        },
        show,
    )

    rule("3. did the commit text reach the prompts?")
    roleplay_prompt = captured.get("roleplay", "")
    answer_prompt = captured.get("answer", "")
    if not roleplay_prompt or not answer_prompt:
        raise Failure("a node never called chat_completion")

    for sentinel in (TERSE, RAMBLE, OLDBATCH):
        require(sentinel, roleplay_prompt, "roleplay: commit message", show)
    # answer's budget is 5 messages and 3 distinct ones are stored, so all apply.
    for sentinel in (TERSE, RAMBLE, OLDBATCH):
        require(sentinel, answer_prompt, "answer: commit message", show)

    rule("4. does answer still carry what it used to drop?")
    require(README, answer_prompt, "answer: readme", show)
    require(FIXTURE_NAME, answer_prompt, "answer: author profile", show)
    require("lines 1-40", answer_prompt, "answer: blame ranges", show)

    print("\ncommit text reaches both prompts.")
    return 0


async def cleanup_fixture() -> None:
    db = get_db()
    try:
        await db.repos.delete_one({"_id": FIXTURE_REPO})
        await db.contributors.delete_many({"repo": FIXTURE_REPO})
        await db.blame_cache.delete_many({"_id": {"$regex": "^" + FIXTURE_REPO + ":"}})
        print("\ncleaned up fixture docs under " + FIXTURE_REPO)
    except Exception as exc:
        print("\ncould not clean up " + FIXTURE_REPO + ": " + str(exc), file=sys.stderr)


async def live_mode(repo: str, token_flag: str, show: bool) -> int:
    if "/" not in repo:
        raise CannotTest("--live takes owner/name")
    owner, name = repo.split("/", 1)
    repo_key = owner + "/" + name

    token = smoke_ingest.resolve_token(token_flag)
    if not token:
        raise CannotTest(
            "No GitHub token. Set GITHUB_TOKEN in your environment or backend/.env -- "
            "live mode ingests a real repo and GraphQL blame rejects anonymous calls."
        )

    db = get_db()
    rule("1. real ingest of " + repo_key)
    try:
        await ingest_repo(token, owner, name)
    except httpx.HTTPStatusError as exc:
        # A dead token is a run that could not ask the question, not a pipeline that
        # is broken -- and ingest_repo has already stamped status:"error" on the repo
        # doc on its way out, so say plainly that nothing was tested.
        if exc.response.status_code in (401, 403):
            raise CannotTest(
                "GitHub rejected the token (" + str(exc.response.status_code) + "). It "
                "is malformed, expired, revoked, or rate-limited -- check GITHUB_TOKEN for "
                "stray characters first (a classic PAT is 40 chars: ghp_ plus 36), then "
                "mint a new one. Nothing about the prompt path was tested."
            )
        raise
    repo_doc = await db.repos.find_one({"_id": repo_key}) or {}
    branch = repo_doc.get("default_branch", "main")
    print("status " + str(repo_doc.get("status")) + ", branch " + str(branch))

    client = GitHubClient(token)
    commits = await client.get_commits(owner, name)
    ingested = {c["author_name"] for c in commits if c.get("author_name")}
    ingested |= {c["author_login"] for c in commits if c.get("author_login")}

    rule("2. pick a real file whose blamed author was ingested")
    path, _ = await smoke_ingest.pick_path(client, owner, name, commits, branch, ingested)
    if path is None:
        raise CannotTest("no candidate file whose top blame author was ingested -- "
                         "the same condition smoke_ingest.py exits 2 on")
    print("file under test  " + path)

    rule("3. retrieve_context on the real repo")
    captured = await run_nodes(
        {
            "query": "why is " + path + " written this way",
            "repo_owner": owner,
            "repo_name": name,
            "token": token,
            "target_path": path,
        },
        show,
    )

    rule("4. is real GitHub commit text in both prompts?")
    resolved = (captured.get("_context") or {}).get("author_profile") or {}
    author_key = resolved.get("author")
    # Read back from Mongo by the resolved key rather than trusting the in-memory
    # context, so the probe is demonstrably what ingest_repo persisted.
    doc = await db.contributors.find_one({"repo": repo_key, "author": author_key})
    stored = (doc or {}).get("recent_messages") or []
    print("resolved contributor: " + str(author_key) + ", "
          + str(len(stored)) + " message(s) persisted by ingest")
    if not stored:
        raise Failure("ingest_repo persisted no commit messages for " + str(author_key))
    # First line of a real stored message, long enough not to match by accident.
    probe = ""
    for entry in stored:
        lines = (entry.get("message") or "").strip().splitlines()
        first = lines[0].strip() if lines else ""
        if len(first) >= 20:
            probe = first
            break
    if not probe:
        raise CannotTest("no stored message with a line long enough to probe with")
    print("probe from Mongo: " + short(probe, 52))

    require(probe, captured.get("roleplay", ""), "roleplay: real commit text", show)
    require(probe, captured.get("answer", ""), "answer: real commit text", show)

    print("\nreal GitHub commit text reaches both prompts.")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prove commit text reaches the roleplay and answer prompts."
    )
    parser.add_argument("--live", metavar="OWNER/NAME", default="",
                        help="ingest a real public repo instead of using fixtures")
    parser.add_argument("--show", action="store_true", help="print both prompts in full")
    # Undocumented, same reasoning as smoke_ingest: an argv token lands in shell
    # history and in ps output.
    parser.add_argument("--token", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    try:
        if args.live:
            return await live_mode(args.live, args.token, args.show)
        try:
            return await fixture_mode(args.show)
        finally:
            await cleanup_fixture()
    except Failure as exc:
        print("\n[FAIL] " + str(exc), file=sys.stderr)
        return 1
    except CannotTest as exc:
        print("\n" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception:
        # Same rule as smoke_ingest: anything unhandled is a broken run, not a broken
        # pipeline, and exit 1 has to keep meaning one thing.
        traceback.print_exc()
        print("\nrun failed before it could test the prompts", file=sys.stderr)
        raise SystemExit(2)
