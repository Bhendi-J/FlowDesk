import test from 'node:test';
import assert from 'node:assert/strict';
import { changeEstimate, estimateFor, isCriticalEdge, resourceSegments, timelineTicks } from './schedule-utils.mjs';

test('moving any estimate maintains valid triangular bounds and updates likely when crossed', () => {
  const original = { optimistic: 3, likely: 5, pessimistic: 8 };
  assert.deepEqual(changeEstimate(original, 'optimistic', 10), { optimistic: 10, likely: 10, pessimistic: 10 });
  assert.deepEqual(changeEstimate(original, 'pessimistic', 2), { optimistic: 2, likely: 2, pessimistic: 2 });
  assert.deepEqual(changeEstimate(original, 'likely', 12), { optimistic: 3, likely: 12, pessimistic: 12 });
  assert.deepEqual(original, { optimistic: 3, likely: 5, pessimistic: 8 });
});
test('persisted estimates and overrides have consistent precedence', () => {
  const task = { id: 1, duration: 4, duration_likely: 5, duration_optimistic: 3, duration_pessimistic: 8 };
  assert.deepEqual(estimateFor(task, { 1: { likely: 10 } }), { optimistic: 3, likely: 10, pessimistic: 10 });
  assert.deepEqual(estimateFor({ id: 2, duration: 1 }), { optimistic: 1, likely: 1, pessimistic: 1 });
});
test('axis includes exact endpoints with bounded label density on long schedules', () => {
  assert.deepEqual(timelineTicks(1), [0, 1]);
  for (const horizon of [10, 13, 101, 1000000]) {
    const ticks = timelineTicks(horizon);
    assert.equal(ticks[0], 0);
    assert.equal(ticks.at(-1), horizon);
    assert.ok(ticks.length <= 11);
    assert.equal(new Set(ticks).size, ticks.length);
  }
});
test('critical endpoints alone do not make a nonbinding dependency critical', () => {
  const tasks = [{ id: 1, earliest_finish: 3 }, { id: 2, earliest_start: 5 }, { id: 3, earliest_start: 3 }];
  const ids = new Set([1, 2, 3]);
  assert.equal(isCriticalEdge({ depends_on_task_id: 1, task_id: 2 }, tasks, ids), false);
  assert.equal(isCriticalEdge({ depends_on_task_id: 1, task_id: 3 }, tasks, ids), true);
});
test('utilization accounts for overlaps, simultaneous boundaries, idle time and playback', () => {
  const tasks = [
    { id: 1, constrained_start: 1, constrained_finish: 4, resource_requirements: { 1: 1 } },
    { id: 2, constrained_start: 3, constrained_finish: 5, resource_requirements: { 1: 1 } },
    { id: 3, constrained_start: 4, constrained_finish: 6, resource_requirements: { 1: 1 } },
  ];
  const resource = { id: 1, capacity: 2 };
  const segments = resourceSegments(tasks, resource, new Set([1, 2, 3]), 1000000);
  assert.deepEqual(segments.map(s => [s.start, s.end, s.used]), [[0, 1, 0], [1, 3, 1], [3, 4, 2], [4, 5, 2], [5, 6, 1], [6, 1000000, 0]]);
  assert.equal(segments[2].pct, 100);
  assert.deepEqual(resourceSegments(tasks, resource, new Set(), 10), [{ start: 0, end: 10, used: 0, pct: 0 }]);
});
