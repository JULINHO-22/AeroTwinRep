from typing import Annotated
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.identity import User
from app.services.agent_service import query
router=APIRouter(tags=['agent']); viewer=require_roles(UserRole.OPERATOR,UserRole.SUPERVISOR)
class AgentRequest(BaseModel): question:str=Field(min_length=1,max_length=500)
@router.post('/agent/query')
def agent_query(payload:AgentRequest,user:Annotated[User,Depends(viewer)],session:Annotated[Session,Depends(get_db)]): return query(session,user.id,payload.question)
