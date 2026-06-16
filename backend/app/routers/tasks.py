from fastapi import APIRouter, HTTPException, Depends
from app.database import DBsession
from app.models.tasks import Task
from sqlalchemy import select
from app.schemas.tasks import (
    TaskCreate,
    TaskRead,
    TaskUpdate
)   

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)

@router.post("/", response_model=TaskRead)
def create_task(
    task_data: TaskCreate,
    db: DBsession
):
    task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        priority=task_data.priority,
        project_id=task_data.project_id,
        assigned_user_id=task_data.assigned_user_id
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task

@router.get("/{task_id}", response_model=TaskRead)
def read_task(
    task_id: int,
    db: DBsession
):
    task = db.get(Task, task_id)

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
    return task

@router.patch("/{task_id}", response_model=TaskRead)
def update_task(

    task_id: int,
    task_data: TaskUpdate,
    db: DBsession
):
    update_data = task_data.model_dump(exclude_unset=True)
    task = db.get(Task, task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)

    return task

@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: DBsession
):
    task = db.get(Task, task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
    
    db.delete(task)
    db.commit()

    return {"detail": "Task deleted successfully"}

@router.get("/", response_model=list[TaskRead])
def read_tasks(
    db: DBsession
):
    stmt = select(Task)
    tasks = db.scalars(stmt).all()
    return tasks

