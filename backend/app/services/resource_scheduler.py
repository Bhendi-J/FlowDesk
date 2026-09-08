def resource_constrained_schedule(
    graph,
    reverse_graph,
    topo_order,
    duration,
    earliest_start,
    earliest_finish,
    latest_start,
    latest_finish,
    slack,
    task_requirements,
    resources,
    task_titles,
):
    scheduled = {}
    reservations = {resource_id: [] for resource_id in resources}
    trace = []

    for task_id in topo_order:
        start = max(
            [scheduled[p]["constrained_finish"] for p in reverse_graph[task_id]],
            default=earliest_start[task_id],
        )
        precedence_earliest = start
        finish = start + duration[task_id]
        requirements = task_requirements.get(task_id, {})

        while not _has_capacity(start, finish, requirements, resources, reservations):
            start += 1
            finish = start + duration[task_id]

        for resource_id, amount in requirements.items():
            reservations.setdefault(resource_id, []).append(
                {
                    "task_id": task_id,
                    "task_title": task_titles.get(task_id, f"Task {task_id}"),
                    "start": start,
                    "finish": finish,
                    "amount": amount,
                }
            )

        scheduled[task_id] = {
            "id": task_id,
            "title": task_titles.get(task_id, f"Task {task_id}"),
            "duration": duration[task_id],
            "earliest_start": earliest_start[task_id],
            "earliest_finish": earliest_finish[task_id],
            "latest_start": latest_start[task_id],
            "latest_finish": latest_finish[task_id],
            "slack": slack[task_id],
            "constrained_start": start,
            "constrained_finish": finish,
            "resource_requirements": requirements,
        }

        entry = {
            "task_id": task_id,
            "assigned_start": start,
            "assigned_finish": finish,
        }
        if start > precedence_earliest:
            blocker = _find_blocker(
                precedence_earliest,
                start,
                requirements,
                resources,
                reservations,
            )
            if blocker:
                entry["blocked_by"] = blocker
        trace.append(entry)

    constrained_duration = max(
        [task["constrained_finish"] for task in scheduled.values()],
        default=0,
    )
    return {
        "tasks": [scheduled[task_id] for task_id in topo_order],
        "constrained_duration": constrained_duration,
        "trace": trace,
    }


def _has_capacity(start, finish, requirements, resources, reservations):
    for tick in range(start, finish):
        for resource_id, amount in requirements.items():
            capacity = resources.get(resource_id, {}).get("capacity", 0)
            used = sum(
                slot["amount"]
                for slot in reservations.get(resource_id, [])
                if slot["start"] <= tick < slot["finish"]
            )
            if used + amount > capacity:
                return False
    return True


def _find_blocker(earliest, assigned_start, requirements, resources, reservations):
    for tick in range(assigned_start - 1, earliest - 1, -1):
        for resource_id, amount in requirements.items():
            capacity = resources.get(resource_id, {}).get("capacity", 0)
            blockers = [
                slot
                for slot in reservations.get(resource_id, [])
                if slot["start"] <= tick < slot["finish"]
            ]
            used = sum(slot["amount"] for slot in blockers)
            if used + amount > capacity and blockers:
                blocker = max(blockers, key=lambda slot: slot["finish"])
                return {
                    "resource_id": resource_id,
                    "resource_name": resources[resource_id]["name"],
                    "task_id": blocker["task_id"],
                    "task_title": blocker["task_title"],
                    "blocked_until": blocker["finish"],
                }
    return None
