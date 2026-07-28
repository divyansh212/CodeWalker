from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.agent.graph import get_agent

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    owner: str
    name: str
    message: str


@router.post("")
async def chat(payload: ChatRequest, user: dict = Depends(get_current_user)):
    agent = get_agent()
    result = await agent.ainvoke({
        "query": payload.message,
        "repo_owner": payload.owner,
        "repo_name": payload.name,
        "token": user["gh_token"],
    })
    return {"response": result.get("response", ""), "route": result.get("route")}
