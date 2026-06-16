from fastapi import APIRouter, HTTPException, Depends
from app.database import DBsession
from app.models.dependencies import TaskDependency
from sqlalchemy import select
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

@router.patch("/{dependency_id}", response_model=DependencyRead)
def update_dependency(
    dependency_id: int,
    dependency_data: DependencyUpdate,
    db: DBsession
):
    dependency = db.get(TaskDependency, dependency_id)

    if not dependency:
        raise HTTPException(
            status_code=404,
            detail="Dependency not found"
        )

    for field, value in dependency_data.model_dump(exclude_unset=True).items():
        setattr(dependency, field, value)

    db.commit()
    db.refresh(dependency)

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

