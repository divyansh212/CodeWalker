from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.services.ingestion import ingest_repo
from app.db import get_db

router = APIRouter(prefix="/repos", tags=["repos"])


class ConnectRepoRequest(BaseModel):
    owner: str
    name: str


@router.post("")
async def connect_repo(
    payload: ConnectRepoRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    background_tasks.add_task(ingest_repo, user["gh_token"], payload.owner, payload.name)
    return {"status": "ingestion_started", "repo": f"{payload.owner}/{payload.name}"}


@router.get("/{owner}/{name}/status")
async def repo_status(owner: str, name: str, user: dict = Depends(get_current_user)):
    db = get_db()
    doc = await db.repos.find_one({"_id": f"{owner}/{name}"})
    if not doc:
        raise HTTPException(status_code=404, detail="Repo not connected yet")
    return {"status": doc.get("status"), "commit_count": doc.get("commit_count", 0), "error": doc.get("error")}
