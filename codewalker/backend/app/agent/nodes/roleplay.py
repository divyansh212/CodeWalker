from app.agent.state import AgentState
from app.services.groq_client import chat_completion
from app.services.tavily_client import ground

SYSTEM_PROMPT = """You are roleplaying as the original author of a piece of code, based on their commit \
history and message style. Speak in first person, reasoning through why you made the choices you made \
at the time, in a conversational tone consistent with the tone of your commit messages. Do not describe \
yourself in the third person and do not break character. Keep it to 2-4 sentences. If grounding notes are \
provided about a library, error, or pattern, weave them in naturally instead of listing them."""


async def roleplay(state: AgentState) -> AgentState:
    context = state.get("context", {})
    profile = context.get("author_profile") or {}
    blame = context.get("blame") or []

    grounding_notes = ""
    if state.get("target_path"):
        results = await ground(f"{state['target_path']} {state['query']}", max_results=2)
        if results:
            grounding_notes = "\n".join(f"- {r['title']}: {r['content']}" for r in results)

    author = profile.get("author", "an unknown contributor")
    top_words = ", ".join(profile.get("top_words", []))

    user_prompt = f"""File: {state.get('target_path')}
Question: {state['query']}
Author: {author}
Commit style keywords: {top_words}
Recent blame ranges: {blame[:3]}
Grounding notes:
{grounding_notes or "none"}

Explain this code in the author's voice."""

    state["response"] = await chat_completion(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.6,
    )
    return state
