from app.agent.state import AgentState
from app.services.groq_client import chat_completion

SYSTEM_PROMPT = """You are Penguin, an assistant that answers questions about a codebase using only the \
README, commit history, and blame context provided. Be direct and specific. If the context does not \
contain the answer, say so instead of guessing."""


async def answer(state: AgentState) -> AgentState:
    context = state.get("context", {})
    user_prompt = f"""README excerpt:
{context.get('readme', '')[:3000]}

Question: {state['query']}"""

    state["response"] = await chat_completion(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )
    return state
