from fastapi import APIRouter, HTTPException, Depends
from app.database import DBsession
from app.models.tasks import Task
from sqlalchemy import select, delete, or_
from app.models.dependencies import TaskDependency
from app.models.resources import Resource, TaskResourceRequirement
from app.schemas.tasks import (
    TaskCreate,
    TaskRead,
    TaskUpdate
)
from app.models.projects import Project
from app.models.users import User   

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)

@router.post("/", response_model=TaskRead)
def create_task(
    task_data: TaskCreate,
    db: DBsession
):
    check_project = db.get(Project, task_data.project_id)
    if not check_project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    if task_data.assigned_user_id is not None:
        check_user = db.get(User, task_data.assigned_user_id)
        if not check_user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

    prerequisites = set(task_data.depends_on_task_ids)
    for prerequisite_id in prerequisites:
        prerequisite = db.get(Task, prerequisite_id)
        if prerequisite is None or prerequisite.project_id != task_data.project_id:
            raise HTTPException(400, "Prerequisites must be existing tasks in this project")
    for resource_id, amount in task_data.resource_requirements.items():
        resource = db.get(Resource, resource_id)
        if resource is None or resource.project_id != task_data.project_id:
            raise HTTPException(400, "Resources must belong to this project")
        if amount > resource.capacity:
            raise HTTPException(400, f"Requested units exceed {resource.name} capacity ({resource.capacity})")

    task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        priority=task_data.priority,
        project_id=task_data.project_id,
        assigned_user_id=task_data.assigned_user_id,
        duration_estimate=task_data.duration_estimate,
        duration_optimistic=task_data.duration_optimistic,
        duration_likely=task_data.duration_likely,
        duration_pessimistic=task_data.duration_pessimistic
    )

    db.add(task)
    db.flush()
    for prerequisite_id in prerequisites:
        db.add(TaskDependency(task_id=task.id, depends_on_task_id=prerequisite_id))
    for resource_id, amount in task_data.resource_requirements.items():
        db.add(TaskResourceRequirement(task_id=task.id, resource_id=resource_id, amount=amount))
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
    
    # Remove both incoming and outgoing links before deleting the task so the
    # remaining graph stays valid, including with foreign keys enforced.
    db.execute(delete(TaskDependency).where(or_(
        TaskDependency.task_id == task_id,
        TaskDependency.depends_on_task_id == task_id,
    )))
    db.execute(delete(TaskResourceRequirement).where(TaskResourceRequirement.task_id == task_id))
    db.delete(task)
    db.commit()

    return {"detail": "Task deleted successfully"}

@router.get("/", response_model=list[TaskRead])
def read_tasks(
    db: DBsession,
    project_id: int | None = None,
):
    stmt = select(Task)
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    stmt = stmt.order_by(Task.id)
    tasks = db.scalars(stmt).all()
    return tasks
