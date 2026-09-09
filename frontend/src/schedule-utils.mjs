export function estimateFor(task, overrides = {}) {
  const estimate = overrides[task.id] ?? {};
  const likely = estimate.likely ?? task.duration_likely ?? task.duration;
  return {
    optimistic: Math.min(likely, estimate.optimistic ?? task.duration_optimistic ?? Math.max(1, Math.round(likely * 0.8))),
    likely,
    pessimistic: Math.max(likely, estimate.pessimistic ?? task.duration_pessimistic ?? Math.round(likely * 1.2)),
  };
}

export function changeEstimate(estimate, field, value) {
  const next = { ...estimate, [field]: Math.max(1, Math.round(value)) };
  if (field === 'optimistic') next.likely = Math.max(next.likely, next.optimistic);
  if (field === 'pessimistic') next.likely = Math.min(next.likely, next.pessimistic);
  next.optimistic = Math.min(next.optimistic, next.likely);
  next.pessimistic = Math.max(next.pessimistic, next.likely);
  return next;
}

export function timelineTicks(horizon) {
  const step = Math.max(1, Math.ceil(horizon / 10));
  const ticks = [];
  for (let tick = 0; tick < horizon; tick += step) ticks.push(tick);
  return [...ticks, horizon];
}

// Only highlight precedence links with no gap on the selected critical path.
export function isCriticalEdge(dep, tasks, criticalIds) {
  const source = tasks.find(task => task.id === dep.depends_on_task_id);
  const target = tasks.find(task => task.id === dep.task_id);
  return criticalIds.has(source?.id) && criticalIds.has(target?.id)
    && source.earliest_finish === target.earliest_start;
}

export function resourceSegments(tasks, resource, activeIds, horizon) {
  const events = new Map([[0, 0], [horizon, 0]]);
  for (const task of tasks) {
    if (!activeIds.has(task.id)) continue;
    const amount = task.resource_requirements[resource.id] ?? 0;
    events.set(task.constrained_start, (events.get(task.constrained_start) ?? 0) + amount);
    events.set(task.constrained_finish, (events.get(task.constrained_finish) ?? 0) - amount);
  }
  const points = [...events.keys()].sort((a, b) => a - b);
  let used = 0;
  return points.slice(0, -1).map((start, index) => {
    used += events.get(start);
    return { start, end: points[index + 1], used, pct: used / resource.capacity * 100 };
  });
}
