
from types import SimpleNamespace

def build_adjacency_list(dependencies):
    graph = {}

    for dep in dependencies:
        source = dep.depends_on_task_id
        target = dep.task_id

        graph.setdefault(source, [])
        graph.setdefault(target, [])
        graph[source].append(target)

    return graph

def has_path(graph, start, end, visited=None):
    if visited is None:
        visited = set()

    if start == end:
        return True

    visited.add(start)

    for neighbor in graph.get(start, []):
        if neighbor not in visited:
            if has_path(graph, neighbor, end, visited):
                return True

    return False


def creates_cycle(
    dependencies,
    task_id,
    depends_on_task_id
):
    graph = build_adjacency_list(dependencies)
    return has_path(
        graph,
        task_id,
        depends_on_task_id
    )

def reverse_adjacency_list(graph):
    reverse = {node: [] for node in graph}
    for node, neighbors in graph.items():
        for n in neighbors:
            reverse[n].append(node)
    return reverse



