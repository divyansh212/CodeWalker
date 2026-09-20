import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

logger = logging.getLogger(__name__)

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


async def ensure_indexes() -> None:
    """Cover every branch of the contributor lookup.

    retrieve_context matches a blamed author against `author`, `author_login` and
    `author_names` in one $or. Mongo cannot serve an $or from a single index — it
    needs one per branch, or it scans the whole collection for the entire query,
    so an index on `author` alone would be wasted. `author_names` is an array, so
    its index is multikey.

    create_index is idempotent, and this is best-effort on purpose: a database
    that is unreachable at boot should not stop the API from starting, since
    every query already fails on its own terms.
    """
    db = get_db()
    specs = [
        ("repo_author", [("repo", 1), ("author", 1)]),
        ("repo_author_login", [("repo", 1), ("author_login", 1)]),
        ("repo_author_names", [("repo", 1), ("author_names", 1)]),
    ]
    for name, keys in specs:
        try:
            await db.contributors.create_index(keys, name=name)
        except Exception as exc:
            logger.warning("could not create index %s on contributors: %s", name, exc)
