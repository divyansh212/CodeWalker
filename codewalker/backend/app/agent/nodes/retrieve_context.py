from app.db import get_db
from app.services.ingestion import get_or_fetch_blame
from app.agent.state import AgentState


async def retrieve_context(state: AgentState) -> AgentState:
    db = get_db()
    repo_key = f"{state['repo_owner']}/{state['repo_name']}"
    repo_doc = await db.repos.find_one({"_id": repo_key}) or {}

    context = {"readme": repo_doc.get("readme", "")}

    path = state.get("target_path")
    if path:
        ranges = await get_or_fetch_blame(state["token"], state["repo_owner"], state["repo_name"], path)
        context["blame"] = ranges
        if ranges:
            author = ranges[0]["commit"]["author"]["name"]
            profile = await db.contributors.find_one({"repo": repo_key, "author": author})
            context["author_profile"] = profile

    state["context"] = context
    return state
