# cpm.py
def compute_earliest_times(graph, reverse_graph, topo_order, duration):
    ES = {}
    EF = {}
    for node in topo_order:
        preds = reverse_graph[node]
        ES[node] = max([EF[p] for p in preds], default=0)
        EF[node] = ES[node] + duration[node]
    return ES, EF


def compute_latest_times(graph, topo_order, duration, EF):
    project_duration = max(EF.values())
    LF = {}
    LS = {}
    for node in reversed(topo_order):
        succs = graph[node]
        LF[node] = min([LS[s] for s in succs], default=project_duration)
        LS[node] = LF[node] - duration[node]
    return LS, LF


def compute_slack(ES, LS):
    return {node: LS[node] - ES[node] for node in ES}


def critical_path(topo_order, slack, graph):
    critical_nodes = [n for n in topo_order if slack[n] == 0]
    return critical_nodes


def delay_impact(task_id, delay_days, slack, EF, duration, graph, reverse_graph, topo_order):
    if delay_days <= slack[task_id]:
        return {"affected_tasks": [], "project_delay": 0}

    new_duration = dict(duration)
    new_duration[task_id] += delay_days

    ES, EF_new = compute_earliest_times(graph, reverse_graph, topo_order, new_duration)
    old_project_duration = max(EF.values())
    new_project_duration = max(EF_new.values())

    project_delay = new_project_duration - old_project_duration

    affected = [t for t in topo_order if EF_new[t] != EF[t]]

    return {"affected_tasks": affected, "project_delay": project_delay}