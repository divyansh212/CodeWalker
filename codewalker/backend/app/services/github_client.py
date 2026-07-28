from typing import Optional
import httpx

GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"

# GitHub's REST API has no direct "blame" endpoint — blame lives in the
# GraphQL v4 API as a field on Commit, reached via repository.ref.target.
BLAME_QUERY = """
query($owner: String!, $repo: String!, $path: String!, $branch: String!) {
  repository(owner: $owner, name: $repo) {
    ref(qualifiedName: $branch) {
      target {
        ... on Commit {
          blame(path: $path) {
            ranges {
              startingLine
              endingLine
              age
              commit {
                oid
                message
                author { name email date }
              }
            }
          }
        }
      }
    }
  }
}
"""


class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

    async def get_readme(self, owner: str, repo: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/readme",
                headers={**self.headers, "Accept": "application/vnd.github.raw"},
            )
            if resp.status_code == 404:
                return ""
            resp.raise_for_status()
            return resp.text

    async def get_repo_meta(self, owner: str, repo: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def get_commits(
        self,
        owner: str,
        repo: str,
        since_sha: Optional[str] = None,
        per_page: int = 100,
        max_pages: int = 5,
    ) -> list:
        commits: list = []
        async with httpx.AsyncClient() as client:
            page = 1
            while page <= max_pages:
                resp = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/commits",
                    headers=self.headers,
                    params={"per_page": per_page, "page": page},
                )
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                stop = False
                for c in batch:
                    if since_sha and c["sha"] == since_sha:
                        stop = True
                        break
                    commits.append({
                        "sha": c["sha"],
                        "author_login": (c.get("author") or {}).get("login"),
                        "author_name": c["commit"]["author"]["name"],
                        "message": c["commit"]["message"],
                        "date": c["commit"]["author"]["date"],
                    })
                if stop or len(batch) < per_page:
                    break
                page += 1
        return commits

    async def get_blame(self, owner: str, repo: str, path: str, branch: str = "main") -> list:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GITHUB_GRAPHQL,
                headers=self.headers,
                json={
                    "query": BLAME_QUERY,
                    "variables": {"owner": owner, "repo": repo, "path": path, "branch": branch},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            try:
                return data["data"]["repository"]["ref"]["target"]["blame"]["ranges"]
            except (KeyError, TypeError):
                return []

    async def search_good_first_issues(
        self, language: Optional[str] = None, topic: Optional[str] = None
    ) -> list:
        query_parts = ['label:"good first issue"', "is:open", "is:issue"]
        if language:
            query_parts.append(f"language:{language}")
        if topic:
            query_parts.append(topic)
        q = " ".join(query_parts)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API}/search/issues",
                headers=self.headers,
                params={"q": q, "sort": "created", "order": "desc", "per_page": 10},
            )
            resp.raise_for_status()
            return resp.json().get("items", [])
