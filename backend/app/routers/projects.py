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
from app.models.users import User
from app.models.tasks import Task
from app.models.dependencies import TaskDependency
from app.models.resources import Resource, TaskResourceRequirement

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


@router.post("/seed-examples")
def seed_example_projects(db: DBsession):
    owner = db.scalars(
        select(User).where(User.email == "examples@flowdesk.local")
    ).first()
    if owner is None:
        owner = User(
            name="FlowDesk Examples",
            email="examples@flowdesk.local",
            password_hash="example-only",
        )
        db.add(owner)
        db.flush()

    workspace = db.scalars(
        select(Workspace).where(
            Workspace.name == "Example Schedules",
            Workspace.owner_id == owner.id,
        )
    ).first()
    if workspace is None:
        workspace = Workspace(name="Example Schedules", owner_id=owner.id)
        db.add(workspace)
        db.flush()

    examples = [
        {
            "name": "Software Release",
            "description": "Design, development, and QA contending for senior engineering time.",
            "resources": [("Senior engineer", 1), ("QA engineer", 1)],
            "tasks": [
                ("Design", 3, []),
                ("Backend dev", 5, ["Design"]),
                ("Frontend dev", 4, ["Design"]),
                ("QA", 3, ["Backend dev", "Frontend dev"]),
                ("Release", 1, ["QA"]),
            ],
            "requirements": {
                "Design": {"Senior engineer": 1},
                "Backend dev": {"Senior engineer": 1},
                "Frontend dev": {"Senior engineer": 1},
                "QA": {"QA engineer": 1},
                "Release": {"Senior engineer": 1},
            },
        },
        {
            "name": "Construction Sequence",
            "description": "A compact construction flow with crew contention in the middle.",
            "resources": [("Crew", 1), ("Inspector", 1)],
            "tasks": [
                ("Foundation", 4, []),
                ("Framing", 5, ["Foundation"]),
                ("Electrical", 3, ["Framing"]),
                ("Plumbing", 3, ["Framing"]),
                ("Drywall", 4, ["Electrical", "Plumbing"]),
                ("Inspection", 1, ["Drywall"]),
            ],
            "requirements": {
                "Foundation": {"Crew": 1},
                "Framing": {"Crew": 1},
                "Electrical": {"Crew": 1},
                "Plumbing": {"Crew": 1},
                "Drywall": {"Crew": 1},
                "Inspection": {"Inspector": 1},
            },
        },
        {
            "name": "Manufacturing Line",
            "description": "Sequential stations sharing a constrained machine.",
            "resources": [("CNC machine", 1), ("Assembler", 1)],
            "tasks": [
                ("Cut stock", 2, []),
                ("Mill parts", 4, ["Cut stock"]),
                ("Drill housings", 3, ["Cut stock"]),
                ("Assemble", 3, ["Mill parts", "Drill housings"]),
                ("Pack", 1, ["Assemble"]),
            ],
            "requirements": {
                "Cut stock": {"CNC machine": 1},
                "Mill parts": {"CNC machine": 1},
                "Drill housings": {"CNC machine": 1},
                "Assemble": {"Assembler": 1},
                "Pack": {"Assembler": 1},
            },
        },
    ]

    seeded = []
    for example in examples:
        project = db.scalars(
            select(Project).where(
                Project.name == example["name"],
                Project.workspace_id == workspace.id,
            )
        ).first()
        if project is not None:
            seeded.append({"id": project.id, "name": project.name})
            continue

        project = Project(
            name=example["name"],
            description=example["description"],
            workspace_id=workspace.id,
        )
        db.add(project)
        db.flush()

        resources_by_name = {}
        for resource_name, capacity in example["resources"]:
            resource = Resource(
                project_id=project.id,
                name=resource_name,
                capacity=capacity,
            )
            db.add(resource)
            db.flush()
            resources_by_name[resource_name] = resource

        tasks_by_name = {}
        for title, duration, _ in example["tasks"]:
            task = Task(
                project_id=project.id,
                title=title,
                description=None,
                duration_estimate=duration,
            )
            db.add(task)
            db.flush()
            tasks_by_name[title] = task

        for title, _, prerequisites in example["tasks"]:
            for prerequisite in prerequisites:
                db.add(
                    TaskDependency(
                        task_id=tasks_by_name[title].id,
                        depends_on_task_id=tasks_by_name[prerequisite].id,
                    )
                )

        for title, requirements in example["requirements"].items():
            for resource_name, amount in requirements.items():
                db.add(
                    TaskResourceRequirement(
                        task_id=tasks_by_name[title].id,
                        resource_id=resources_by_name[resource_name].id,
                        amount=amount,
                    )
                )

        seeded.append({"id": project.id, "name": project.name})

    db.commit()
    return {"projects": seeded}

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
