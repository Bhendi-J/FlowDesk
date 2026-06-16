from app.models.users import User
from datetime import datetime
from pydantic import BaseModel,  EmailStr

class workspaceBase(BaseModel):
    name: str
    
class workspaceCreate(workspaceBase):
    owner_id: int

class workspaceRead(workspaceBase):
    id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class workspaceUpdate(BaseModel):
    name: str | None = None
    owner_id: int | None = None

