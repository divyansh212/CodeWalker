from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api import routes_auth, routes_repos, routes_chat

settings = get_settings()

app = FastAPI(title="Codewalker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router, prefix="/api")
app.include_router(routes_repos.router, prefix="/api")
app.include_router(routes_chat.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
