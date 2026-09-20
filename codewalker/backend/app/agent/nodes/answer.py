from app.agent.state import AgentState
from app.services.groq_client import chat_completion
from app.services.voice_profile import format_messages_for_prompt

# Tighter than roleplay's budget: the plain path leans on the README, and commits are
# corroboration here rather than the point of the output.
PROMPT_MESSAGE_LIMIT = 5
BLAME_RANGE_LIMIT = 5

SYSTEM_PROMPT = """You are Penguin, an assistant that answers questions about a codebase using only the \
README, commit history, and blame context provided. Be direct and specific. If the context does not \
contain the answer, say so instead of guessing."""


def format_blame(ranges: list, limit: int) -> str:
    """One line per range. The raw GraphQL dicts carry nested commit objects that
    burn prompt budget on field names, so flatten to what a reader would want."""
    lines = []
    for r in ranges[:limit]:
        commit = r.get("commit") or {}
        author = ((commit.get("author") or {}).get("name")) or "unknown"
        subject = (commit.get("message") or "").strip().splitlines()
        subject = subject[0] if subject else ""
        lines.append(
            f"- lines {r.get('startingLine')}-{r.get('endingLine')}: "
            f"{author} ({(commit.get('oid') or '')[:7]}) {subject}"
        )
    return "\n".join(lines)


async def answer(state: AgentState) -> AgentState:
    context = state.get("context", {})
    profile = context.get("author_profile") or {}
    blame = context.get("blame") or []

    # retrieve_context builds all of this on the way here; sending only the README
    # threw it away and made "grounded in commit history" a claim rather than a fact.
    sections = [f"README excerpt:\n{context.get('readme', '')[:3000]}"]

    path = state.get("target_path")
    if path:
        sections.append(f"File under discussion: {path}")
    if blame:
        sections.append(f"Blame for that file:\n{format_blame(blame, BLAME_RANGE_LIMIT)}")
    if profile:
        sections.append(
            f"Primary author: {profile.get('author')} "
            f"({profile.get('commit_count')} commits in the ingested window, "
            f"{profile.get('first_commit')} to {profile.get('last_commit')}; "
            f"recurring terms: {', '.join(profile.get('top_words') or []) or 'none'})"
        )
    commit_messages = format_messages_for_prompt(
        context.get("author_commits") or [], PROMPT_MESSAGE_LIMIT
    )
    if commit_messages:
        sections.append(f"That author's recent commit messages:\n{commit_messages}")

    sections.append(f"Question: {state['query']}")
    user_prompt = "\n\n".join(sections)

    state["response"] = await chat_completion(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )
    return state
