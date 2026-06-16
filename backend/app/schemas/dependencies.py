from datetime import datetime


from pydantic import BaseModel

from pydantic import BaseModel, ConfigDict


class DependencyBase(BaseModel):
    task_id: int
    depends_on_task_id: int


class DependencyCreate(DependencyBase):
    pass


class DependencyRead(DependencyBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class DependencyUpdate(BaseModel):
    task_id: int | None = None
    depends_on_task_id: int | None = None

