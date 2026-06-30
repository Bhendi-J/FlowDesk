from app.services.graph import build_adjacency_list, reverse_adjacency_list
from app.services.topological import topological_sort
from app.services.cpm import (
    compute_earliest_times,
    compute_latest_times,
    compute_slack,
    critical_path,
    delay_impact,
)
from types import SimpleNamespace

dependencies = [
    SimpleNamespace(task_id=2, depends_on_task_id=1),  # A->B
    SimpleNamespace(task_id=3, depends_on_task_id=1),  # A->C
    SimpleNamespace(task_id=4, depends_on_task_id=2),  # B->D
    SimpleNamespace(task_id=4, depends_on_task_id=3),  # C->D
]

duration = {1: 2, 2: 5, 3: 3, 4: 4}

graph = build_adjacency_list(dependencies)
reverse_graph = reverse_adjacency_list(graph)
topo_order = topological_sort(graph)
print("topo:", topo_order)

ES, EF = compute_earliest_times(graph, reverse_graph, topo_order, duration)
print("ES:", ES)
print("EF:", EF)

LS, LF = compute_latest_times(graph, topo_order, duration, EF)
print("LS:", LS)
print("LF:", LF)

slack = compute_slack(ES, LS)
print("slack:", slack)

print("critical path:", critical_path(topo_order, slack, graph))

print("delay B+3:", delay_impact(2, 3, slack, EF, duration, graph, reverse_graph, topo_order))
print("delay C+1:", delay_impact(3, 1, slack, EF, duration, graph, reverse_graph, topo_order))
print("delay C+3:", delay_impact(3, 3, slack, EF, duration, graph, reverse_graph, topo_order))