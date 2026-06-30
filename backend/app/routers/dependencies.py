from fastapi import APIRouter, HTTPException, Depends
from app.database import DBsession
from app.models.dependencies import TaskDependency
from sqlalchemy import select
from app.models.tasks import Task
from app.services.graph import creates_cycle
from app.schemas.dependencies import (
    DependencyCreate,
    DependencyRead,
    DependencyUpdate

)

router = APIRouter(
    prefix="/Dependencies",
    tags=["Dependencies"],
)

@router.post("/", response_model=DependencyRead)
def create_dependency(
    dependency_data: DependencyCreate,
    db: DBsession
):
    if dependency_data.task_id == dependency_data.depends_on_task_id:
        raise HTTPException(
            status_code=400,
            detail="A task cannot depend on itself"
        )
    
    task1 = db.get(Task, dependency_data.task_id)
    task2 = db.get(Task, dependency_data.depends_on_task_id)

    if not task1 or not task2:
        raise HTTPException(
            status_code=404,
            detail="One or both tasks not found"
        )
    
    project_id = task1.project_id
    if task2.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail="Tasks must belong to the same project"
        )
    

    stmt = select(TaskDependency).where(
        TaskDependency.task_id == dependency_data.task_id,
        TaskDependency.depends_on_task_id == dependency_data.depends_on_task_id
    )
    existing_dependency = db.scalars(stmt).first()
    if existing_dependency:
        raise HTTPException(
            status_code=400,
            detail="Dependency already exists"
        )

    stmt = (
    select(TaskDependency)
    .join(Task, TaskDependency.task_id == Task.id)
    .where(Task.project_id == project_id)
)
   
    dependencies = db.scalars(stmt).all()

    
    if creates_cycle(
    dependencies,
    dependency_data.task_id,
    dependency_data.depends_on_task_id
    ):
        raise HTTPException(
        status_code=400,
        detail="Adding this dependency would create a circular dependency"
    )
    
    dependency = TaskDependency(
        task_id=dependency_data.task_id,
        depends_on_task_id=dependency_data.depends_on_task_id
    )

    db.add(dependency)
    db.commit()
    db.refresh(dependency)

    return dependency


@router.get("/", response_model=list[DependencyRead])
def read_dependencies(
    db: DBsession
):
    stmt = select(TaskDependency)
    dependencies = db.scalars(stmt).all()

    return dependencies

@router.get("/{dependency_id}", response_model=DependencyRead)
def read_dependency(
    dependency_id: int,
    db: DBsession
):
    dependency = db.get(TaskDependency, dependency_id)

    if not dependency:
        raise HTTPException(
            status_code=404,
            detail="Dependency not found"
        )
    return dependency


@router.delete("/{dependency_id}")
def delete_dependency(
    dependency_id: int,
    db: DBsession
):
    dependency = db.get(TaskDependency, dependency_id)

    if not dependency:
        raise HTTPException(
            status_code=404,
            detail="Dependency not found"
        )

    db.delete(dependency)
    db.commit()

    return {"detail": "Dependency deleted successfully"}

