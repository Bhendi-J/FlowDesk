from fastapi import APIRouter, HTTPException, Depends
from app.database import DBsession
from app.models.projects import Project
from sqlalchemy import select
from app.schemas.projects import (
    projectCreate,
    projectBase,
    projectRead,
    projectUpdate
)
from app.models.workspaces import Workspace

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)

@router.post("/", response_model=projectRead)
def create_project(
    project_data: projectCreate,
    db: DBsession
):
    
    workspace = db.get(Workspace, project_data.workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found"
        )
    
    project = Project(
        name=project_data.name,
        description=project_data.description,
        workspace_id=project_data.workspace_id,
        deadline=project_data.deadline
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return project

@router.get("/", response_model=list[projectRead])
def read_projects(
    db: DBsession
):
    stmt = select(Project)
    projects = db.scalars(stmt).all()

    return projects

@router.get("/{project_id}", response_model=projectRead)
def read_project(
    project_id: int,
    db: DBsession
):
    project = db.get(Project, project_id)

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )
    return project

@router.patch("/{project_id}", response_model=projectRead)
def update_project( 
    project_id: int,
    project_data: projectUpdate,
    db: DBsession
):
    update_data = project_data.model_dump(exclude_unset=True)
    project = db.get(Project, project_id)


    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )
    
    for key, value in update_data.items():
        setattr(project, key, value)

    db.commit()
    db.refresh(project)

    return project

@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: DBsession
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )
    
    db.delete(project)
    db.commit()

    return {"detail": "Project deleted successfully"}