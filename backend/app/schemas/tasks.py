from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskBase(BaseModel):
    title: str
    description: str | None = None
    status: TaskStatus = TaskStatus.pending
    priority: TaskPriority = TaskPriority.medium
    duration_estimate: int | None = None


class TaskCreate(TaskBase):
    project_id: int
    assigned_user_id: int | None = None
    duration_estimate: int #compulsary field for CPM calculations, must be provided when creating a task



class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    duration_estimate: int | None = None

class TaskRead(TaskBase):
    id: int
    created_at: datetime
    project_id: int
    assigned_user_id: int | None = None
    duration_estimate: int


    model_config = {
        "from_attributes": True
    }

