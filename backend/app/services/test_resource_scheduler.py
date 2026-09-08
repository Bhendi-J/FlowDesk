from app.services.resource_scheduler import resource_constrained_schedule


def test_contention_extends_schedule_without_exceeding_capacity():
    graph = {1: [], 2: [], 3: []}
    reverse_graph = {1: [], 2: [], 3: []}
    topo_order = [1, 2, 3]
    duration = {1: 2, 2: 2, 3: 2}
    earliest_start = {1: 0, 2: 0, 3: 0}
    earliest_finish = {1: 2, 2: 2, 3: 2}
    latest_start = {1: 0, 2: 0, 3: 0}
    latest_finish = {1: 2, 2: 2, 3: 2}
    slack = {1: 0, 2: 0, 3: 0}
    requirements = {1: {1: 5}, 2: {1: 5}, 3: {1: 5}}
    resources = {1: {"id": 1, "name": "Shared resource", "capacity": 5}}
    task_titles = {1: "Task A", 2: "Task B", 3: "Task C"}

    result = resource_constrained_schedule(
        graph,
        reverse_graph,
        topo_order,
        duration,
        earliest_start,
        earliest_finish,
        latest_start,
        latest_finish,
        slack,
        requirements,
        resources,
        task_titles,
    )

    assert result["constrained_duration"] > max(earliest_finish.values())

    for tick in range(result["constrained_duration"]):
        usage = 0
        for task in result["tasks"]:
            if task["constrained_start"] <= tick < task["constrained_finish"]:
                usage += task["resource_requirements"].get(1, 0)
        assert usage <= resources[1]["capacity"]


def test_ample_capacity_matches_naive_schedule():
    graph = {1: [3], 2: [3], 3: []}
    reverse_graph = {1: [], 2: [], 3: [1, 2]}
    topo_order = [1, 2, 3]
    duration = {1: 2, 2: 3, 3: 1}
    earliest_start = {1: 0, 2: 0, 3: 3}
    earliest_finish = {1: 2, 2: 3, 3: 4}
    latest_start = {1: 1, 2: 0, 3: 3}
    latest_finish = {1: 3, 2: 3, 3: 4}
    slack = {1: 1, 2: 0, 3: 0}
    requirements = {1: {1: 5}, 2: {1: 5}, 3: {1: 5}}
    resources = {1: {"id": 1, "name": "Shared resource", "capacity": 15}}
    task_titles = {1: "Task A", 2: "Task B", 3: "Task C"}

    result = resource_constrained_schedule(
        graph,
        reverse_graph,
        topo_order,
        duration,
        earliest_start,
        earliest_finish,
        latest_start,
        latest_finish,
        slack,
        requirements,
        resources,
        task_titles,
    )

    assert result["constrained_duration"] == max(earliest_finish.values())
    for task in result["tasks"]:
        task_id = task["id"]
        assert task["constrained_start"] == earliest_start[task_id]
        assert task["constrained_finish"] == earliest_finish[task_id]
