from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, PositiveInt, field_validator


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
    duration_optimistic: int | None = None
    duration_likely: int | None = None
    duration_pessimistic: int | None = None


class TaskCreate(TaskBase):
    project_id: int
    assigned_user_id: int | None = None
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    duration_estimate: PositiveInt
    depends_on_task_ids: list[int] = Field(default_factory=list)
    resource_requirements: dict[int, PositiveInt] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Task title cannot be blank")
        return value



class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    duration_estimate: int | None = None
    duration_optimistic: int | None = None
    duration_likely: int | None = None
    duration_pessimistic: int | None = None

class TaskRead(TaskBase):
    id: int
    created_at: datetime
    project_id: int
    assigned_user_id: int | None = None
    duration_estimate: int
    duration_optimistic: int | None = None
    duration_likely: int | None = None
    duration_pessimistic: int | None = None


    model_config = {
        "from_attributes": True
    }
