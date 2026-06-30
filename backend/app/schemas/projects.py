from app.models.workspaces import Workspace
from app.models.users import User

from datetime import datetime
from pydantic import BaseModel,  EmailStr

class projectBase(BaseModel):
    name: str
    description: str | None = None

class projectCreate(projectBase):
    workspace_id: int
    deadline: datetime | None = None

class projectRead(projectBase):
    id: int
    workspace_id: int
    deadline: datetime | None = None

    model_config = {
        "from_attributes": True
    }

class projectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    deadline: datetime | None = None
