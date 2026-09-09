import math
import random

from types import SimpleNamespace

from app.services.cpm import (
    compute_earliest_times,
    compute_latest_times,
    compute_slack,
)
from app.services.graph import build_adjacency_list, reverse_adjacency_list
from app.services.resource_scheduler import resource_constrained_schedule
from app.services.topological import topological_sort


def run_monte_carlo(
    tasks,
    dependencies,
    resources,
    task_resources,
    num_trials,
    resource_capacity_overrides=None,
    seed=None,
):
    resource_capacity_overrides = resource_capacity_overrides or {}
    rng = random.Random(seed)
    normalized_tasks = [_normalize_task(task) for task in tasks]
    task_ids = [task["id"] for task in normalized_tasks]
    task_titles = {task["id"]: task["title"] for task in normalized_tasks}
    normalized_dependencies = [
        SimpleNamespace(
            task_id=_read(dep, "task_id"),
            depends_on_task_id=_read(dep, "depends_on_task_id"),
        )
        for dep in dependencies
    ]
    graph = build_adjacency_list(normalized_dependencies)
    for task_id in task_ids:
        graph.setdefault(task_id, [])
    reverse_graph = reverse_adjacency_list(graph)
    topo_order = topological_sort(graph)
    resource_map = _normalize_resources(resources, resource_capacity_overrides)
    task_requirements = _normalize_task_resources(task_resources, task_ids)

    project_durations = []
    trial_results = []
    critical_counts = {task_id: 0 for task_id in task_ids}

    for _ in range(num_trials):
        sampled_duration = {
            task["id"]: max(
                1,
                round(
                    rng.triangular(
                        task["duration_optimistic"],
                        task["duration_pessimistic"],
                        task["duration_likely"],
                    )
                ),
            )
            for task in normalized_tasks
        }
        ES, EF = compute_earliest_times(
            graph,
            reverse_graph,
            topo_order,
            sampled_duration,
        )
        LS, LF = compute_latest_times(graph, topo_order, sampled_duration, EF)
        slack = compute_slack(ES, LS)
        constrained = resource_constrained_schedule(
            graph,
            reverse_graph,
            topo_order,
            sampled_duration,
            ES,
            EF,
            LS,
            LF,
            slack,
            task_requirements,
            resource_map,
            task_titles,
        )
        project_duration = constrained["constrained_duration"]
        project_durations.append(project_duration)
        for task_id, task_slack in slack.items():
            if task_slack == 0:
                critical_counts[task_id] += 1
        trial_results.append(
            {
                "project_duration": project_duration,
                "sampled_durations": sampled_duration,
                "slack": slack,
            }
        )

    return {
        "num_trials": num_trials,
        "project_durations": project_durations,
        "summary": _summary(project_durations),
        "histogram": _histogram(project_durations),
        "criticality_index": {
            task_id: round((critical_counts[task_id] / num_trials) * 100, 2)
            for task_id in task_ids
        },
        "trials": trial_results,
    }


def _normalize_task(task):
    task_id = _read(task, "id")
    title = _read(task, "title") or f"Task {task_id}"
    duration = _read(task, "duration", None)
    if duration is None:
        duration = _read(task, "duration_estimate")
    optimistic = _read(task, "duration_optimistic", None)
    likely = _read(task, "duration_likely", None)
    pessimistic = _read(task, "duration_pessimistic", None)
    optimistic = duration if optimistic is None else optimistic
    likely = duration if likely is None else likely
    pessimistic = duration if pessimistic is None else pessimistic
    low = min(optimistic, likely, pessimistic)
    high = max(optimistic, likely, pessimistic)
    mode = min(max(likely, low), high)
    return {
        "id": task_id,
        "title": title,
        "duration": duration,
        "duration_optimistic": low,
        "duration_likely": mode,
        "duration_pessimistic": high,
    }


def _normalize_resources(resources, overrides):
    if isinstance(resources, dict):
        items = resources.items()
    else:
        items = [(_read(resource, "id"), resource) for resource in resources]

    return {
        int(resource_id): {
            "id": int(resource_id),
            "name": _read(resource, "name", f"Resource {resource_id}"),
            "capacity": max(1, overrides.get(int(resource_id), _read(resource, "capacity"))),
        }
        for resource_id, resource in items
    }


def _normalize_task_resources(task_resources, task_ids):
    requirements = {task_id: {} for task_id in task_ids}
    if isinstance(task_resources, dict):
        for task_id, resources in task_resources.items():
            requirements[int(task_id)] = {
                int(resource_id): amount
                for resource_id, amount in resources.items()
            }
        return requirements

    for requirement in task_resources:
        task_id = _read(requirement, "task_id")
        requirements.setdefault(task_id, {})[_read(requirement, "resource_id")] = _read(
            requirement,
            "amount",
        )
    return requirements


def _summary(values):
    if not values:
        return {
            "min": 0,
            "max": 0,
            "mean": 0,
            "stdev": 0,
            "p10": 0,
            "p50": 0,
            "p90": 0,
        }

    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    ordered = sorted(values)
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(mean, 2),
        "stdev": round(math.sqrt(variance), 2),
        "p10": _percentile(ordered, 10),
        "p50": _percentile(ordered, 50),
        "p90": _percentile(ordered, 90),
    }


def _percentile(ordered_values, percentile):
    if len(ordered_values) == 1:
        return ordered_values[0]
    position = (len(ordered_values) - 1) * (percentile / 100)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered_values[int(position)]
    weight = position - lower
    value = ordered_values[lower] * (1 - weight) + ordered_values[upper] * weight
    return round(value, 2)


def _histogram(values, bucket_count=20):
    if not values:
        return {"bucket_edges": [0], "counts": []}
    low = min(values)
    high = max(values)
    if low == high:
        return {"bucket_edges": [low, high], "counts": [len(values)]}

    width = (high - low) / bucket_count
    counts = [0 for _ in range(bucket_count)]
    for value in values:
        index = min(bucket_count - 1, int((value - low) / width))
        counts[index] += 1
    edges = [round(low + (width * index), 2) for index in range(bucket_count + 1)]
    return {"bucket_edges": edges, "counts": counts}


def _read(source, name, default=None):
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)
