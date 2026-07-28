import httpx
from app.config import get_settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


async def chat_completion(messages: list, temperature: float = 0.4, max_tokens: int = 800) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": settings.groq_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
