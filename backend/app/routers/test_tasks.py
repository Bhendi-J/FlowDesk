import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.database import Base, get_db
from app.main import app
from app.models.dependencies import TaskDependency
from app.models.resources import TaskResourceRequirement
from app.models.tasks import Task


@pytest.fixture
def task_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tasks.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = session_override
    try:
        client = TestClient(app)
        projects = client.post("/projects/seed-examples").json()["projects"]
        yield client, engine, projects
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_create_task_with_links_and_delete_without_orphans(task_client):
    client, engine, projects = task_client
    project_id = projects[0]["id"]
    schedule = client.get(f"/projects/{project_id}/schedule").json()
    prerequisite = schedule["tasks"][-1]["id"]
    resource = schedule["resources"][0]["id"]
    response = client.post("/tasks/", json={
        "project_id": project_id, "title": "  Follow-up  ", "description": "Review release",
        "duration_estimate": 2, "priority": "high", "status": "pending",
        "depends_on_task_ids": [prerequisite, prerequisite], "resource_requirements": {str(resource): 1},
    })
    assert response.status_code == 200
    task_id = response.json()["id"]
    assert response.json()["title"] == "Follow-up"
    child = client.post("/tasks/", json={
        "project_id": project_id, "title": "Next", "duration_estimate": 1,
        "depends_on_task_ids": [task_id],
    }).json()
    assert client.get(f"/projects/{project_id}/schedule").status_code == 200
    assert client.delete(f"/tasks/{task_id}").status_code == 200
    with Session(engine) as db:
        assert db.get(Task, task_id) is None
        assert db.get(Task, child["id"]) is not None
        assert not db.scalars(select(TaskDependency).where(
            (TaskDependency.task_id == task_id) | (TaskDependency.depends_on_task_id == task_id)
        )).all()
        assert not db.scalars(select(TaskResourceRequirement).where(TaskResourceRequirement.task_id == task_id)).all()
    assert client.get(f"/projects/{project_id}/schedule").status_code == 200
    assert client.delete(f"/tasks/{task_id}").status_code == 404


def test_invalid_create_is_atomic_and_task_list_is_project_scoped(task_client):
    client, engine, projects = task_client
    project_id = projects[0]["id"]
    tasks = client.get(f"/tasks/?project_id={project_id}").json()
    other_task = client.get(f"/tasks/?project_id={projects[1]['id']}").json()[0]
    assert all(task["project_id"] == project_id for task in tasks)
    payload = {"project_id": project_id, "title": "New", "duration_estimate": 2}
    assert client.post("/tasks/", json={**payload, "depends_on_task_ids": [other_task["id"]]}).status_code == 400
    assert client.post("/tasks/", json={**payload, "resource_requirements": {"99999": 1}}).status_code == 400
    for invalid in [{"title": "   "}, {"title": "x" * 101}, {"duration_estimate": 0}, {"duration_estimate": -1}]:
        assert client.post("/tasks/", json={**payload, **invalid}).status_code == 422
    assert len(client.get(f"/tasks/?project_id={project_id}").json()) == len(tasks)


def test_delete_all_tasks_and_create_again(task_client):
    client, _, projects = task_client
    project_id = projects[0]["id"]
    for task in client.get(f"/tasks/?project_id={project_id}").json():
        assert client.delete(f"/tasks/{task['id']}").status_code == 200
    assert client.get(f"/tasks/?project_id={project_id}").json() == []
    assert client.get(f"/projects/{project_id}/schedule").status_code == 404
    created = client.post("/tasks/", json={"project_id": project_id, "title": "Fresh start", "duration_estimate": 3})
    assert created.status_code == 200
    schedule = client.get(f"/projects/{project_id}/schedule")
    assert schedule.status_code == 200
    assert schedule.json()["constrained_duration"] == 3
