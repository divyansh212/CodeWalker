from app.agent.state import AgentState
from app.services.groq_client import chat_completion

SYSTEM_PROMPT = """You help a beginner who is stuck on an open-source issue. Assume no prior familiarity \
with git, PRs, or issue etiquette. Explain the likely fix step by step, in plain language."""


async def oss_solver(state: AgentState) -> AgentState:
    state["response"] = await chat_completion(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state["query"]},
        ],
        temperature=0.4,
    )
    return state
