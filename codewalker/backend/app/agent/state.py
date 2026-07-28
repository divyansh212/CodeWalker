from typing import TypedDict, Optional


class AgentState(TypedDict, total=False):
    query: str
    repo_owner: str
    repo_name: str
    token: str
    route: str
    target_path: Optional[str]
    context: dict
    response: str
