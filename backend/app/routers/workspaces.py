from fastapi import APIRouter, HTTPException, Depends
from app.database import DBsession
from app.models.workspaces import Workspace
from app.models.users import User
from sqlalchemy import select
from app.schemas.workspaces import (
    workspaceCreate, 
    workspaceBase, 
    workspaceRead, 
    workspaceUpdate
)

router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"],
)

@router.post("/", response_model=workspaceRead)
def create_workspace(
    workspace_data:workspaceCreate,
    db:DBsession
):
    user = db.get(User, workspace_data.owner_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="No user found with the provided owner id"
        )
    workspace = Workspace(
        name = workspace_data.name,
        owner_id = workspace_data.owner_id
    )

    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    return workspace

@router.get("/", response_model=list[workspaceRead])
def read_workspaces(
    db:DBsession
):
    stmt = select(Workspace)
    workspaces = db.scalars(stmt).all()

    return workspaces


@router.get("/{workspace_id}", response_model=workspaceRead)
def read_workspace(
    workspace_id:int,
    db:DBsession
):
    workspace = db.get(Workspace, workspace_id)

    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found"
        )
    return workspace

@router.patch("/{workspace_id}", response_model=workspaceRead)
def update_workspace(
    workspace_id: int,
    workspace_data: workspaceUpdate,
    db: DBsession
):
    update_data = workspace_data.model_dump(exclude_unset=True)
    workspace = db.get(Workspace, workspace_id)

    if workspace is None:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found"
        )
    
    for key, value in update_data.items():
        setattr(workspace, key, value)

    db.commit()
    db.refresh(workspace)

    return workspace



@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: int,
    db : DBsession
):
    workspace = db.get(Workspace, workspace_id)

    if workspace is None:
        raise HTTPException(
            status_code=400,
            detail="Workspace not found"
        )
    
    db.delete(workspace)
    db.commit()

    return {"message": "Workspace Deleted"}