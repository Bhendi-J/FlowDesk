from fastapi import APIRouter, HTTPException
from app.database import DBsession
from app.models.tasks import Task
from app.models.dependencies import TaskDependency
from app.services.graph import build_adjacency_list, reverse_adjacency_list
from app.services.topological import topological_sort
from app.services.cpm import (
    compute_earliest_times, compute_latest_times,
    compute_slack, critical_path, delay_impact
)
from sqlalchemy import select

router = APIRouter(prefix="/projects", tags=["CPM"])

def _load_project_data(db, project_id):
    tasks = db.scalars(select(Task).where(Task.project_id == project_id)).all()
    if not tasks:
        raise HTTPException(404, "No tasks found for project")
    duration = {t.id: t.duration_estimate for t in tasks}

    deps = db.scalars(
        select(TaskDependency)
        .join(Task, TaskDependency.task_id == Task.id)
        .where(Task.project_id == project_id)
    ).all()

    graph = build_adjacency_list(deps)
    for t in tasks:
        graph.setdefault(t.id, [])  # isolated tasks included
    reverse_graph = reverse_adjacency_list(graph)
    return graph, reverse_graph, duration

@router.get("/{project_id}/critical-path")
def get_critical_path(project_id: int, db: DBsession):
    graph, reverse_graph, duration = _load_project_data(db, project_id)
    try:
        topo_order = topological_sort(graph)
    except ValueError:
        raise HTTPException(400, "Graph contains a cycle")

    ES, EF = compute_earliest_times(graph, reverse_graph, topo_order, duration)
    LS, LF = compute_latest_times(graph, topo_order, duration, EF)
    slack = compute_slack(ES, LS)
    cp = critical_path(topo_order, slack, graph)

    return {
        "topo_order": topo_order,
        "ES": ES, "EF": EF, "LS": LS, "LF": LF,
        "slack": slack,
        "critical_path": cp,
        "project_duration": max(EF.values())
    }

@router.post("/{project_id}/delay-impact")
def get_delay_impact(project_id: int, task_id: int, delay_days: int, db: DBsession):
    graph, reverse_graph, duration = _load_project_data(db, project_id)
    try:
        topo_order = topological_sort(graph)
    except ValueError:
        raise HTTPException(400, "Graph contains a cycle")

    ES, EF = compute_earliest_times(graph, reverse_graph, topo_order, duration)
    LS, LF = compute_latest_times(graph, topo_order, duration, EF)
    slack = compute_slack(ES, LS)

    if task_id not in duration:
        raise HTTPException(404, "Task not found in project")

    return delay_impact(task_id, delay_days, slack, EF, duration, graph, reverse_graph, topo_order)