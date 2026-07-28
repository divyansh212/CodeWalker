import re
from app.agent.state import AgentState

FILE_PATTERN = re.compile(r"[\w\-/]+\.\w+")
ROLEPLAY_HINTS = ["why", "explain", "who wrote", "what were they thinking", "confusing", "weird"]


def route_query(state: AgentState) -> AgentState:
    query = state["query"].lower()

    if any(k in query for k in ["find a repo", "good first issue", "want to learn", "want to contribute"]):
        state["route"] = "oss_finder"
        return state

    if any(k in query for k in ["stuck", "help me solve", "can't figure out this issue"]):
        state["route"] = "oss_solver"
        return state

    match = FILE_PATTERN.search(state["query"])
    if match:
        state["target_path"] = match.group(0)
        if any(k in query for k in ROLEPLAY_HINTS):
            state["route"] = "roleplay"
            return state

    state["route"] = "answer"
    return state
