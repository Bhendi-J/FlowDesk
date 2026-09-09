from types import SimpleNamespace

from app.services.cpm import (
    compute_earliest_times,
    compute_latest_times,
    compute_slack,
)
from app.services.graph import build_adjacency_list, reverse_adjacency_list
from app.services.monte_carlo import run_monte_carlo
from app.services.resource_scheduler import resource_constrained_schedule
from app.services.topological import topological_sort


def test_monte_carlo_is_deterministic_with_fixed_seed():
    result_a = run_monte_carlo(
        _uncertain_tasks(),
        _dependencies(),
        _resources(),
        _task_resources(),
        num_trials=100,
        seed=42,
    )
    result_b = run_monte_carlo(
        _uncertain_tasks(),
        _dependencies(),
        _resources(),
        _task_resources(),
        num_trials=100,
        seed=42,
    )

    assert result_a == result_b


def test_sampled_durations_stay_within_three_point_ranges():
    tasks = _uncertain_tasks()
    ranges = {
        task["id"]: (task["duration_optimistic"], task["duration_pessimistic"])
        for task in tasks
    }

    result = run_monte_carlo(
        tasks,
        _dependencies(),
        _resources(),
        _task_resources(),
        num_trials=1000,
        seed=7,
    )

    for trial in result["trials"]:
        for task_id, sampled_duration in trial["sampled_durations"].items():
            low, high = ranges[task_id]
            assert low <= sampled_duration <= high


def test_fixed_three_point_estimates_collapse_to_deterministic_schedule():
    tasks = [
        {
            "id": 1,
            "title": "A",
            "duration": 2,
            "duration_optimistic": 2,
            "duration_likely": 2,
            "duration_pessimistic": 2,
        },
        {
            "id": 2,
            "title": "B",
            "duration": 4,
            "duration_optimistic": 4,
            "duration_likely": 4,
            "duration_pessimistic": 4,
        },
        {
            "id": 3,
            "title": "C",
            "duration": 3,
            "duration_optimistic": 3,
            "duration_likely": 3,
            "duration_pessimistic": 3,
        },
    ]
    dependencies = [{"task_id": 3, "depends_on_task_id": 1}]
    resources = [{"id": 1, "name": "Machine", "capacity": 1}]
    task_resources = {1: {1: 1}, 2: {1: 1}, 3: {1: 1}}

    result = run_monte_carlo(
        tasks,
        dependencies,
        resources,
        task_resources,
        num_trials=50,
        seed=99,
    )

    deterministic_duration = _deterministic_duration(
        tasks,
        dependencies,
        resources,
        task_resources,
    )

    assert set(result["project_durations"]) == {deterministic_duration}
    assert result["summary"]["min"] == deterministic_duration
    assert result["summary"]["max"] == deterministic_duration
    assert result["histogram"]["counts"] == [50]


def _deterministic_duration(tasks, dependencies, resources, task_resources):
    deps = [
        SimpleNamespace(
            task_id=dependency["task_id"],
            depends_on_task_id=dependency["depends_on_task_id"],
        )
        for dependency in dependencies
    ]
    graph = build_adjacency_list(deps)
    duration = {task["id"]: task["duration"] for task in tasks}
    task_titles = {task["id"]: task["title"] for task in tasks}
    for task in tasks:
        graph.setdefault(task["id"], [])
    reverse_graph = reverse_adjacency_list(graph)
    topo_order = topological_sort(graph)
    ES, EF = compute_earliest_times(graph, reverse_graph, topo_order, duration)
    LS, LF = compute_latest_times(graph, topo_order, duration, EF)
    slack = compute_slack(ES, LS)
    resource_map = {resource["id"]: resource for resource in resources}
    return resource_constrained_schedule(
        graph,
        reverse_graph,
        topo_order,
        duration,
        ES,
        EF,
        LS,
        LF,
        slack,
        task_resources,
        resource_map,
        task_titles,
    )["constrained_duration"]


def _uncertain_tasks():
    return [
        {
            "id": 1,
            "title": "Design",
            "duration": 3,
            "duration_optimistic": 2,
            "duration_likely": 3,
            "duration_pessimistic": 5,
        },
        {
            "id": 2,
            "title": "Build",
            "duration": 4,
            "duration_optimistic": 3,
            "duration_likely": 4,
            "duration_pessimistic": 8,
        },
        {
            "id": 3,
            "title": "Verify",
            "duration": 2,
            "duration_optimistic": 1,
            "duration_likely": 2,
            "duration_pessimistic": 4,
        },
    ]


def _dependencies():
    return [{"task_id": 3, "depends_on_task_id": 1}]


def _resources():
    return [{"id": 1, "name": "Engineer", "capacity": 1}]


def _task_resources():
    return {1: {1: 1}, 2: {1: 1}, 3: {1: 1}}
