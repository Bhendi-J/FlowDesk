# FlowDesk

FlowDesk is a FastAPI project scheduling sandbox. It compares a naive CPM schedule, where tasks start as soon as their dependencies allow, with a resource-constrained schedule, where shared capacity can force otherwise-ready tasks to wait.

## Resource-Constrained Scheduler Sandbox

The sandbox graph shows task dependencies and highlights the naive critical path in the dependency DAG. Select a task to inspect its timing, slack, resource requirements, and blocking task. The Gantt timeline pairs faint naive bars with solid constrained bars on the same time axis, so a shifted start shows the effect of resource constraints. Playback reveals assignments in both the graph and timeline.

The resource utilization strip shows one row per resource over the project timeline. Gray segments are idle, green segments are below 60% capacity, amber segments are 60-99%, and red segments are fully saturated. The task and resource sliders call the simulation endpoint only; they do not write the override values back to the database.

The **Project tasks** panel restores persistent task management. Use **Add task** to set a title, description, duration, priority, status, optional prerequisite tasks, and resource requirements. Creation saves the task and its links together. The delete button opens a confirmation showing the consequences; deletion removes the task's incoming/outgoing dependency links and resource assignments while retaining other tasks. The charts refresh and temporary scenario overrides reset after either operation. Empty projects can receive new tasks from the same panel.

The project picker loads existing projects, seeding examples only when no projects exist. Task lists are scoped through `GET /tasks/?project_id=<id>`.

Frontend calculation checks: `node --test frontend/src/schedule-utils.test.mjs`. Backend regression checks: `PYTHONPATH=backend .venv/bin/python -m pytest -q`.

To seed the local examples:

```bash
curl -X POST http://127.0.0.1:8000/projects/seed-examples
```

To simulate a project without persisting overrides:

```bash
curl -X POST http://127.0.0.1:8000/projects/1/simulate-schedule \
  -H 'Content-Type: application/json' \
  -d '{"resource_capacity_overrides":{"1":2},"task_duration_overrides":{"2":7}}'
```

To run duration-uncertainty simulation, use optimistic/likely/pessimistic estimates. The response includes project-duration summary stats, histogram buckets, and per-task criticality percentages:

```bash
curl -X POST http://127.0.0.1:8000/projects/1/simulate-monte-carlo \
  -H 'Content-Type: application/json' \
  -d '{"num_trials":1000,"resource_capacity_overrides":{"1":1}}'
```

Run the backend with:

```bash
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run the frontend with:

```bash
cd frontend
npm install
npm run dev
```
