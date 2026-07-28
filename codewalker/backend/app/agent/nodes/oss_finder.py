from app.agent.state import AgentState
from app.services.github_client import GitHubClient


async def oss_finder(state: AgentState) -> AgentState:
    client = GitHubClient(state["token"])
    issues = await client.search_good_first_issues()
    if not issues:
        state["response"] = "Couldn't find a good-fit issue right now — try narrowing the language or topic."
        return state

    lines = ["Here's a few good-fit starting points:"]
    for issue in issues[:5]:
        repo_name = issue["repository_url"].split("/repos/")[-1]
        lines.append(f"- {issue['title']} ({repo_name}) — {issue['html_url']}")
    state["response"] = "\n".join(lines)
    return state
