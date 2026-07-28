from app.config import get_settings
import httpx

TAVILY_URL = "https://api.tavily.com/search"


async def ground(query: str, max_results: int = 3) -> list:
    """Grounds the roleplay/seance monologues with live context on the
    library/error/pattern in question — not general search-augmented Q&A."""
    settings = get_settings()
    if not settings.tavily_api_key:
        return []
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TAVILY_URL,
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title"), "url": r.get("url"), "content": (r.get("content") or "")[:500]}
            for r in data.get("results", [])
        ]
