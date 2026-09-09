from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.database import DBsession
from app.models.dependencies import TaskDependency
from app.models.resources import Resource, TaskResourceRequirement
from app.models.tasks import Task
from app.schemas.schedule import (
    MonteCarloResponse,
    ScheduleResponse,
    SimulateMonteCarloRequest,
    SimulateScheduleRequest,
)
from app.services.cpm import (
    compute_earliest_times,
    compute_latest_times,
    compute_slack,
    critical_path,
)
from app.services.graph import build_adjacency_list, reverse_adjacency_list
from app.services.monte_carlo import run_monte_carlo
from app.services.resource_scheduler import resource_constrained_schedule
from app.services.topological import topological_sort

router = APIRouter(prefix="/projects", tags=["Schedule"])


@router.get(
    "/{project_id}/schedule",
    response_model=ScheduleResponse,
    response_model_exclude_none=True,
)
def get_schedule(project_id: int, db: DBsession):
    return _schedule_project(db, project_id)


@router.post(
    "/{project_id}/simulate-schedule",
    response_model=ScheduleResponse,
    response_model_exclude_none=True,
)
def simulate_schedule(
    project_id: int,
    simulation: SimulateScheduleRequest,
    db: DBsession,
):
    return _schedule_project(
        db,
        project_id,
        resource_capacity_overrides=simulation.resource_capacity_overrides,
        task_duration_overrides=simulation.task_duration_overrides,
    )


@router.post(
    "/{project_id}/simulate-monte-carlo",
    response_model=MonteCarloResponse,
)
def simulate_monte_carlo(
    project_id: int,
    simulation: SimulateMonteCarloRequest,
    db: DBsession,
):
    num_trials = min(max(1, simulation.num_trials), 5000)
    tasks, deps, resource_map, task_requirements = _load_project_schedule_inputs(
        db,
        project_id,
        resource_capacity_overrides=simulation.resource_capacity_overrides,
    )
    return run_monte_carlo(
        _apply_task_duration_estimate_overrides(
            tasks,
            simulation.task_duration_estimate_overrides,
        ),
        deps,
        list(resource_map.values()),
        task_requirements,
        num_trials,
        resource_capacity_overrides=simulation.resource_capacity_overrides,
        seed=simulation.seed,
    )


def _schedule_project(
    db,
    project_id,
    resource_capacity_overrides=None,
    task_duration_overrides=None,
):
    resource_capacity_overrides = resource_capacity_overrides or {}
    task_duration_overrides = task_duration_overrides or {}
    tasks, deps, resource_map, task_requirements = _load_project_schedule_inputs(
        db,
        project_id,
        resource_capacity_overrides=resource_capacity_overrides,
    )
    if not tasks:
        raise HTTPException(404, "No tasks found for project")

    if not tasks:
        raise HTTPException(404, "No tasks found for project")

    task_ids = {task.id for task in tasks}
    task_titles = {task.id: task.title for task in tasks}
    duration = {
        task.id: max(1, task_duration_overrides.get(task.id, task.duration_estimate))
        for task in tasks
    }

    dependencies = [
        {
            "task_id": dep.task_id,
            "depends_on_task_id": dep.depends_on_task_id,
        }
        for dep in deps
        if dep.task_id in task_ids and dep.depends_on_task_id in task_ids
    ]

    graph = build_adjacency_list(deps)
    for task in tasks:
        graph.setdefault(task.id, [])
    reverse_graph = reverse_adjacency_list(graph)

    try:
        topo_order = topological_sort(graph)
    except ValueError:
        raise HTTPException(400, "Graph contains a cycle")

    ES, EF = compute_earliest_times(graph, reverse_graph, topo_order, duration)
    LS, LF = compute_latest_times(graph, topo_order, duration, EF)
    slack = compute_slack(ES, LS)
    cp = critical_path(topo_order, slack, graph)

    constrained = resource_constrained_schedule(
        graph,
        reverse_graph,
        topo_order,
        duration,
        ES,
        EF,
        LS,
        LF,
        slack,
        task_requirements,
        resource_map,
        task_titles,
    )
    scheduled_tasks = constrained["tasks"]
    task_estimates = {
        task.id: {
            "duration_optimistic": task.duration_optimistic,
            "duration_likely": task.duration_likely,
            "duration_pessimistic": task.duration_pessimistic,
        }
        for task in tasks
    }
    for scheduled_task in scheduled_tasks:
        scheduled_task.update(task_estimates[scheduled_task["id"]])

    return {
        "topo_order": topo_order,
        "ES": ES,
        "EF": EF,
        "LS": LS,
        "LF": LF,
        "slack": slack,
        "critical_path": cp,
        "project_duration": max(EF.values()),
        "constrained_duration": constrained["constrained_duration"],
        "tasks": scheduled_tasks,
        "resources": list(resource_map.values()),
        "dependencies": dependencies,
        "trace": constrained["trace"],
    }


def _load_project_schedule_inputs(db, project_id, resource_capacity_overrides=None):
    resource_capacity_overrides = resource_capacity_overrides or {}
    tasks = db.scalars(select(Task).where(Task.project_id == project_id)).all()
    if not tasks:
        raise HTTPException(404, "No tasks found for project")

    deps = db.scalars(
        select(TaskDependency)
        .join(Task, TaskDependency.task_id == Task.id)
        .where(Task.project_id == project_id)
    ).all()

    resources = db.scalars(
        select(Resource).where(Resource.project_id == project_id)
    ).all()
    resource_map = {
        resource.id: {
            "id": resource.id,
            "name": resource.name,
            "capacity": max(
                1,
                resource_capacity_overrides.get(resource.id, resource.capacity),
            ),
        }
        for resource in resources
    }

    requirements = db.scalars(
        select(TaskResourceRequirement)
        .join(Task, TaskResourceRequirement.task_id == Task.id)
        .where(Task.project_id == project_id)
    ).all()
    task_requirements = {task.id: {} for task in tasks}
    for requirement in requirements:
        if requirement.resource_id in resource_map:
            task_requirements[requirement.task_id][requirement.resource_id] = (
                requirement.amount
            )

    return tasks, deps, resource_map, task_requirements


def _apply_task_duration_estimate_overrides(tasks, overrides):
    if not overrides:
        return tasks

    normalized = []
    for task in tasks:
        override = overrides.get(task.id)
        if override is None:
            normalized.append(task)
            continue

        normalized.append(
            {
                "id": task.id,
                "title": task.title,
                "duration_estimate": task.duration_estimate,
                "duration_optimistic": (
                    override.optimistic
                    if override.optimistic is not None
                    else task.duration_optimistic
                ),
                "duration_likely": (
                    override.likely
                    if override.likely is not None
                    else task.duration_likely
                ),
                "duration_pessimistic": (
                    override.pessimistic
                    if override.pessimistic is not None
                    else task.duration_pessimistic
                ),
            }
        )
    return normalized
