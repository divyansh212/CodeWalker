import re
from collections import Counter

STOPWORDS = {"the", "a", "an", "and", "to", "of", "in", "for", "on", "with", "this", "that", "it", "is", "fix", "add"}

# Bounds on the commit text kept per contributor. Roleplay needs to see how someone
# writes, and a handful of commits shows that as well as a hundred do -- so the cap is
# per contributor rather than per repo, and a 500-commit ingest across many repos costs
# the same per author as a 20-commit one. Worst case is ~12KB added to a contributor doc.
RECENT_MESSAGE_CAP = 20
MESSAGE_CHAR_CAP = 600


def _truncate(message: str) -> str:
    text = (message or "").strip()
    if len(text) <= MESSAGE_CHAR_CAP:
        return text
    return text[: MESSAGE_CHAR_CAP - 3] + "..."


def _dedupe_key(entry: dict) -> str:
    # sha when we have one; the text itself is the fallback so a malformed entry
    # cannot collapse every other message into a single empty key.
    return entry.get("sha") or entry.get("message") or ""


def _date_of(entry: dict) -> str:
    # GitHub dates are ISO-8601 UTC, so lexical order is chronological order.
    return entry.get("date") or ""


def recent_messages(commits: list, cap: int = RECENT_MESSAGE_CAP) -> list:
    """The newest commit messages from this batch, verbatim but length-capped."""
    entries = [
        {"sha": c.get("sha"), "date": c.get("date"), "message": _truncate(c.get("message", ""))}
        for c in commits
        if (c.get("message") or "").strip()
    ]
    return merge_recent_messages([], entries, cap=cap)


def merge_recent_messages(existing: list, incoming: list, cap: int = RECENT_MESSAGE_CAP) -> list:
    """Newest first, deduped by sha, capped.

    Ingest is incremental: build_voice_profile only ever sees the commits fetched on
    this run, so a stored list has to be merged rather than replaced. Overwriting would
    let an incremental run evict twenty real messages in favour of the two new ones.
    Incoming wins a sha collision -- a run whose window overlaps what is already stored
    is refetching the same commits, not finding different ones.
    """
    merged: dict = {}
    for entry in list(incoming) + list(existing):
        key = _dedupe_key(entry)
        if key and key not in merged:
            merged[key] = entry
    return sorted(merged.values(), key=_date_of, reverse=True)[:cap]


# This run's commit shas for one author, newest first. Carried on the profile so
# persist_voice_profiles can tell which of them were already counted, and dropped
# before the doc is written -- the stored field is last_counted_sha, not the list.
WINDOW_SHAS_KEY = "window_shas"


def merge_commit_count(stored_count: int, boundary_sha, window_shas: list) -> tuple:
    """(count, new_boundary_sha), counting only commits not already counted.

    commit_count has the same problem recent_messages does -- the profile is built
    from just the commits fetched on this run, so a blind $set walks the total back
    down to the size of the latest window -- but it cannot be fixed the same way,
    because a running total carries no shas to dedupe against. So store the newest
    sha counted and, on the next run, count only what sits above it.

    A plain stored_count + len(window) would fix the decay and introduce
    commit-count-double-count in its place: when since_sha falls outside the fetch
    window, get_commits returns commits that were already counted, and adding them
    again inflates the total silently. Stopping at the boundary makes that case
    correct rather than merely different.

    The boundary can still fall outside the window, if this author landed more than
    the fetch window's worth of commits since the last run. Nothing in the window
    then says what was already counted, so it counts everything and over-reports --
    the residual half of commit-count-double-count, and it needs the fetch window
    lifted rather than another guess here.
    """
    if not window_shas:
        return stored_count, boundary_sha
    newest = window_shas[0]
    if boundary_sha is None:
        return len(window_shas), newest
    if boundary_sha in window_shas:
        # Everything above the boundary is new; the boundary and below were counted.
        return stored_count + window_shas.index(boundary_sha), newest
    return stored_count + len(window_shas), newest


def format_messages_for_prompt(messages: list, limit: int) -> str:
    """Commit messages verbatim, newest first, one dated block each.

    Deliberately unsummarised and unnormalised. The terseness, the tells, and whether
    this person explains themselves or doesn't are the whole signal -- any tidying pass
    destroys exactly the thing the messages are in the prompt for.
    """
    blocks = []
    for entry in messages[:limit]:
        text = (entry.get("message") or "").strip()
        if not text:
            continue
        date = (entry.get("date") or "")[:10] or "undated"
        blocks.append(f"[{date}]\n{text}")
    return "\n\n".join(blocks)


def build_voice_profile(commits: list) -> dict:
    if not commits:
        return {}

    by_author: dict = {}
    for c in commits:
        key = c.get("author_login") or c.get("author_name") or "unknown"
        by_author.setdefault(key, []).append(c)

    profiles = {}
    for author, author_commits in by_author.items():
        messages = [c["message"] for c in author_commits]
        word_counts = Counter()
        for m in messages:
            words = re.findall(r"[a-zA-Z']+", m.lower())
            word_counts.update(w for w in words if w not in STOPWORDS and len(w) > 2)
        avg_len = sum(len(m) for m in messages) / len(messages)
        dates = sorted(c["date"] for c in author_commits)
        # Blame keys on the git display name while this keys on the login, so store
        # both and let retrieve_context match on either. One person can commit under
        # several display names (git config changes, laptop vs CI), so keep them all.
        login = next((c["author_login"] for c in author_commits if c.get("author_login")), None)
        names = []
        for c in author_commits:
            n = c.get("author_name")
            if n and n not in names:
                names.append(n)
        profiles[author] = {
            "author": author,
            "author_login": login,
            "author_names": names,
            # This window only. persist_voice_profiles merges it into the total.
            "commit_count": len(author_commits),
            "avg_message_length": round(avg_len, 1),
            "top_words": [w for w, _ in word_counts.most_common(8)],
            # The messages themselves, not just statistics about them. Hung off this
            # doc rather than a commits collection so they ride along with the
            # contributor lookup that already resolves login vs display name.
            "recent_messages": recent_messages(author_commits),
            # Transient: consumed by persist_voice_profiles, never stored.
            WINDOW_SHAS_KEY: [c["sha"] for c in author_commits if c.get("sha")],
            "first_commit": dates[0],
            "last_commit": dates[-1],
        }
    return profiles
