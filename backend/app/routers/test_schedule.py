from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_db
from app.main import app
from app.models.dependencies import TaskDependency
from app.models.projects import Project
from app.models.resources import Resource, TaskResourceRequirement
from app.models.tasks import Task
from app.models.users import User
from app.models.workspaces import Workspace


def test_simulate_schedule_does_not_persist_task_duration(tmp_path):
    from fastapi.testclient import TestClient

    db_path = tmp_path / "flowdesk-test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="not-used",
        )
        db.add(user)
        db.flush()
        workspace = Workspace(name="Test Workspace", owner_id=user.id)
        db.add(workspace)
        db.flush()
        project = Project(name="Test Project", workspace_id=workspace.id)
        db.add(project)
        db.flush()
        resource = Resource(project_id=project.id, name="Engineer", capacity=1)
        db.add(resource)
        db.flush()
        task = Task(
            project_id=project.id,
            title="Build",
            duration_estimate=3,
        )
        db.add(task)
        db.flush()
        db.add(
            TaskResourceRequirement(
                task_id=task.id,
                resource_id=resource.id,
                amount=1,
            )
        )
        project_id = project.id
        task_id = task.id
        original_duration = task.duration_estimate
        db.commit()

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            f"/projects/{project_id}/simulate-schedule",
            json={"task_duration_overrides": {str(task_id): original_duration + 4}},
        )
        assert response.status_code == 200
        assert response.json()["tasks"][0]["duration"] == original_duration + 4

        with Session(engine) as db:
            persisted_task = db.get(Task, task_id)
            assert persisted_task.duration_estimate == original_duration
    finally:
        app.dependency_overrides.clear()


def test_seed_examples_is_idempotent(tmp_path):
    from fastapi.testclient import TestClient

    db_path = tmp_path / "flowdesk-seed-test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        first = client.post("/projects/seed-examples")
        second = client.post("/projects/seed-examples")

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["projects"] == second.json()["projects"]

        with Session(engine) as db:
            projects = db.query(Project).all()
            assert sorted(project.name for project in projects) == [
                "Construction Sequence",
                "Manufacturing Line",
                "Software Release",
            ]
    finally:
        app.dependency_overrides.clear()
