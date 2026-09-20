from datetime import datetime, timezone
from app.services.github_client import GitHubClient
from app.services.voice_profile import build_voice_profile, merge_recent_messages
from app.db import get_db


async def ingest_repo(token: str, owner: str, repo: str):
    """Background job: README + commit log always; blame is fetched lazily
    per-file on demand (see get_or_fetch_blame) to control API rate limits."""
    db = get_db()
    client = GitHubClient(token)
    repo_key = f"{owner}/{repo}"

    await db.repos.update_one(
        {"_id": repo_key},
        {"$set": {"status": "ingesting", "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )

    try:
        meta = await client.get_repo_meta(owner, repo)
        default_branch = meta.get("default_branch", "main")
        readme = await client.get_readme(owner, repo)

        existing = await db.repos.find_one({"_id": repo_key})
        since_sha = existing.get("last_sha") if existing else None
        commits = await client.get_commits(owner, repo, since_sha=since_sha)

        profiles = build_voice_profile(commits)
        await persist_voice_profiles(db, repo_key, profiles)

        prior_count = existing.get("commit_count", 0) if existing else 0
        await db.repos.update_one(
            {"_id": repo_key},
            {"$set": {
                "status": "ready",
                "default_branch": default_branch,
                "readme": readme[:20000],
                "last_sha": commits[0]["sha"] if commits else since_sha,
                "commit_count": prior_count + len(commits),
                "updated_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as exc:
        await db.repos.update_one(
            {"_id": repo_key},
            {"$set": {"status": "error", "error": str(exc), "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        raise


async def persist_voice_profiles(db, repo_key: str, profiles: dict) -> None:
    """Upsert one contributor doc per author, merging stored commit messages.

    Everything else in the profile is recomputed from scratch each run and can be
    overwritten, but recent_messages is cumulative: on an incremental ingest the
    profile was built from only the newly fetched commits, so a blind $set would
    throw away everything stored on previous runs.
    """
    for author, profile in profiles.items():
        query = {"repo": repo_key, "author": author}
        stored = await db.contributors.find_one(query, {"recent_messages": 1})
        merged = merge_recent_messages(
            (stored or {}).get("recent_messages") or [],
            profile.get("recent_messages") or [],
        )
        await db.contributors.update_one(
            query,
            {"$set": {**profile, "recent_messages": merged, "repo": repo_key}},
            upsert=True,
        )


async def get_or_fetch_blame(token: str, owner: str, repo: str, path: str) -> list:
    db = get_db()
    repo_key = f"{owner}/{repo}"
    cache_key = f"{repo_key}:{path}"

    cached = await db.blame_cache.find_one({"_id": cache_key})
    if cached:
        return cached["ranges"]

    repo_doc = await db.repos.find_one({"_id": repo_key})
    branch = (repo_doc or {}).get("default_branch", "main")

    client = GitHubClient(token)
    ranges = await client.get_blame(owner, repo, path, branch=branch)
    await db.blame_cache.update_one(
        {"_id": cache_key},
        {"$set": {"ranges": ranges}},
        upsert=True,
    )
    return ranges
