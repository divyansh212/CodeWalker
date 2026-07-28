import re
from collections import Counter

STOPWORDS = {"the", "a", "an", "and", "to", "of", "in", "for", "on", "with", "this", "that", "it", "is", "fix", "add"}


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
        profiles[author] = {
            "author": author,
            "commit_count": len(author_commits),
            "avg_message_length": round(avg_len, 1),
            "top_words": [w for w, _ in word_counts.most_common(8)],
            "first_commit": dates[0],
            "last_commit": dates[-1],
        }
    return profiles
