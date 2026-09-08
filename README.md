# FlowDesk

FlowDesk is a FastAPI project scheduling sandbox. It compares a naive CPM schedule, where tasks start as soon as their dependencies allow, with a resource-constrained schedule, where shared capacity can force otherwise-ready tasks to wait.

## Resource-Constrained Scheduler Sandbox

The sandbox graph shows task dependencies and highlights the naive critical path in the dependency DAG. The Gantt timeline overlays faint naive bars with solid constrained bars, so any horizontal gap represents delay caused by resource contention rather than precedence.

The resource utilization strip shows one row per resource over the project timeline. Green segments are below 60% capacity, amber segments are 60-99%, and red segments are fully saturated. The task and resource sliders call the simulation endpoint only; they do not write the override values back to the database.

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
