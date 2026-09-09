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
                ("Design", 3, [], 2, 3, 5),
                ("Backend dev", 5, ["Design"], 4, 5, 8),
                ("Frontend dev", 4, ["Design"], 3, 4, 7),
                ("QA", 3, ["Backend dev", "Frontend dev"], 2, 3, 6),
                ("Release", 1, ["QA"], 1, 1, 2),
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
                ("Foundation", 4, [], 3, 4, 7),
                ("Framing", 5, ["Foundation"], 4, 5, 8),
                ("Electrical", 3, ["Framing"], 2, 3, 5),
                ("Plumbing", 3, ["Framing"], 2, 3, 5),
                ("Drywall", 4, ["Electrical", "Plumbing"], 3, 4, 7),
                ("Inspection", 1, ["Drywall"], 1, 1, 2),
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
                ("Cut stock", 2, [], 1, 2, 3),
                ("Mill parts", 4, ["Cut stock"], 3, 4, 6),
                ("Drill housings", 3, ["Cut stock"], 2, 3, 5),
                ("Assemble", 3, ["Mill parts", "Drill housings"], 2, 3, 5),
                ("Pack", 1, ["Assemble"], 1, 1, 2),
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
            _backfill_example_task_estimates(db, project, example)
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
        for title, duration, _, optimistic, likely, pessimistic in example["tasks"]:
            task = Task(
                project_id=project.id,
                title=title,
                description=None,
                duration_estimate=duration,
                duration_optimistic=optimistic,
                duration_likely=likely,
                duration_pessimistic=pessimistic,
            )
            db.add(task)
            db.flush()
            tasks_by_name[title] = task

        for title, _, prerequisites, _, _, _ in example["tasks"]:
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


def _backfill_example_task_estimates(db, project, example):
    existing_tasks = {
        task.title: task
        for task in db.scalars(select(Task).where(Task.project_id == project.id)).all()
    }
    for title, _, _, optimistic, likely, pessimistic in example["tasks"]:
        task = existing_tasks.get(title)
        if task is None:
            continue
        task.duration_optimistic = optimistic
        task.duration_likely = likely
        task.duration_pessimistic = pessimistic

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
