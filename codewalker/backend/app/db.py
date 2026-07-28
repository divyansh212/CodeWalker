from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_db():
    settings = get_settings()
    return get_client()[settings.mongodb_db]
