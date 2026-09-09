# FlowDesk Interview Guide

This document explains the current FlowDesk codebase from an interview perspective.
It is based on the repository snapshot in this workspace on August 27, 2026.

The goal is not just to describe files, but to help you:

- explain the overall architecture clearly
- defend design decisions
- walk through the important algorithms step by step
- answer "why did you do it this way?" with confidence
- call out honest limitations without sounding unprepared

## 1. What FlowDesk Is

FlowDesk is a backend-first project management and scheduling API.

At a high level it does two jobs:

1. It manages project data: users, workspaces, projects, tasks, and task dependencies.
2. It analyzes project schedules using a dependency graph and Critical Path Method (CPM).

The product idea is:

- a user owns workspaces
- a workspace contains projects
- a project contains tasks
- tasks can depend on other tasks
- once dependencies exist, the backend can compute execution order, earliest and latest timings, slack, critical path, and delay impact

If you need a 20-second answer in an interview:

> "FlowDesk is a FastAPI backend for project scheduling. It stores projects and task dependencies in a relational database, models the dependency network as a directed acyclic graph, and runs Critical Path Method calculations to tell you project duration, critical tasks, and how delays propagate."

## 2. Folder Structure

The repo is small and centered around the backend:

```text
FlowDesk/
├── pyproject.toml
└── backend/
    ├── flowdesk.db
    ├── practice.py
    └── app/
        ├── __init__.py
        ├── database.py
        ├── main.py
        ├── core/
        ├── models/
        │   ├── users.py
        │   ├── workspaces.py
        │   ├── projects.py
        │   ├── tasks.py
        │   └── dependencies.py
        ├── routers/
        │   ├── users.py
        │   ├── workspaces.py
        │   ├── projects.py
        │   ├── tasks.py
        │   ├── dependencies.py
        │   └── cpm.py
        ├── schemas/
        │   ├── users.py
        │   ├── workspaces.py
        │   ├── projects.py
        │   ├── tasks.py
        │   └── dependencies.py
        └── services/
            ├── graph.py
            ├── topological.py
            ├── cpm.py
            └── test_cpm.py
```

How to explain the structure:

- `models/` defines database tables and ORM relationships.
- `schemas/` defines request and response shapes using Pydantic.
- `routers/` defines API endpoints and business validation.
- `services/` contains reusable graph and scheduling algorithms.
- `main.py` wires everything into a FastAPI app.
- `database.py` creates the engine, base class, session dependency, and tables.

This is a clean layered backend structure:

`HTTP request -> router -> database/models + service logic -> response schema`

## 3. Runtime Architecture

### Entry point

`backend/app/main.py` is the actual application entry point in the codebase.

It does three things:

1. creates a FastAPI app
2. uses a lifespan hook to create database tables on startup
3. registers all routers

The root endpoint simply returns a health-style message.

### Database setup

`backend/app/database.py` uses:

- SQLAlchemy `DeclarativeBase` for ORM models
- a SQLite database at `sqlite:///./flowdesk.db`
- a session dependency `get_db()`
- `create_tables()` to call `Base.metadata.create_all(...)`

Why this is reasonable:

- SQLite keeps local development simple
- SQLAlchemy gives clean table mapping and relationships
- FastAPI dependency injection makes DB session access simple in each route

How to defend it:

> "I chose SQLite for speed of development and simple local execution, and I isolated the DB session behind dependency injection so I can later swap to Postgres with minimal router changes."

## 4. Core Domain Model

FlowDesk has five main entities.

### User

Represents a person in the system.

Fields:

- `id`
- `name`
- `email`
- `password_hash`
- `created_at`

Relationships:

- one user can own many workspaces
- one user can be assigned many tasks

### Workspace

Represents a top-level container owned by a user.

Fields:

- `id`
- `name`
- `created_at`
- `owner_id`

Relationships:

- belongs to one user
- has many projects

### Project

Represents a schedulable body of work inside a workspace.

Fields:

- `id`
- `name`
- `description`
- `created_at`
- `workspace_id`
- `deadline`

Relationships:

- belongs to one workspace
- has many tasks

### Task

Represents an actionable unit of work.

Fields:

- `id`
- `project_id`
- `assigned_user_id`
- `title`
- `description`
- `status`
- `priority`
- `duration_estimate`
- `created_at`

Why `duration_estimate` matters:

- it is the duration input for CPM
- without duration estimates, scheduling math cannot work

### TaskDependency

Represents a prerequisite relationship between two tasks.

Meaning:

- `task_id` is the dependent task
- `depends_on_task_id` is the prerequisite task

If task B depends on task A, then:

- `task_id = B`
- `depends_on_task_id = A`

In graph terms the code turns that into:

`A -> B`

That direction is important because it means edges point from prerequisite to dependent task.

## 5. Why the Project Uses Separate Models, Schemas, Routers, and Services

This is one of the easiest architecture questions to get asked.

A strong answer is:

- models describe how data is stored
- schemas describe how data enters and leaves the API
- routers describe endpoint behavior and validation rules
- services isolate reusable domain logic, especially algorithms

Why that matters:

- avoids mixing HTTP logic with algorithmic logic
- keeps the CPM code reusable and testable
- makes the code easier to extend without turning routers into giant files

Short interview answer:

> "I separated persistence, transport, and algorithmic concerns so CRUD behavior stays simple while the graph and CPM logic remain independently testable and reusable."

## 6. API Surface

The API exposes CRUD-style resources plus scheduling analysis.

### Users

- `POST /users/`
- `GET /users/`
- `GET /users/{user_id}`
- `PATCH /users/{user_id}`
- `DELETE /users/{user_id}`

### Workspaces

- `POST /workspaces/`
- `GET /workspaces/`
- `GET /workspaces/{workspace_id}`
- `PATCH /workspaces/{workspace_id}`
- `DELETE /workspaces/{workspace_id}`

### Projects

- `POST /projects/`
- `GET /projects/`
- `GET /projects/{project_id}`
- `PATCH /projects/{project_id}`
- `DELETE /projects/{project_id}`

### Tasks

- `POST /tasks/`
- `GET /tasks/`
- `GET /tasks/{task_id}`
- `PATCH /tasks/{task_id}`
- `DELETE /tasks/{task_id}`

### Dependencies

- `POST /Dependencies/`
- `GET /Dependencies/`
- `GET /Dependencies/{dependency_id}`
- `DELETE /Dependencies/{dependency_id}`

### CPM / Scheduling

- `GET /projects/{project_id}/critical-path`
- `POST /projects/{project_id}/delay-impact?task_id=...&delay_days=...`

Why the CPM routes live under `/projects`:

- scheduling is project-scoped
- all tasks and dependencies are loaded inside one project boundary

## 7. End-to-End Data Flow

If someone asks "what happens when a request comes in?", use this pattern.

### Example: create task

1. Client sends `POST /tasks/`.
2. FastAPI validates request JSON against `TaskCreate`.
3. Router checks that the target project exists.
4. If `assigned_user_id` is present, router checks that the user exists.
5. Router creates a `Task` ORM object.
6. SQLAlchemy session adds and commits it.
7. The task is refreshed from DB.
8. FastAPI serializes it using `TaskRead`.

### Example: create dependency

1. Client sends `POST /Dependencies/`.
2. Request is validated against `DependencyCreate`.
3. Router blocks self-dependency.
4. Router verifies both tasks exist.
5. Router verifies both tasks are in the same project.
6. Router checks that the dependency is not already stored.
7. Router loads all existing dependencies for that project.
8. Service logic checks whether the new edge would create a cycle.
9. If safe, dependency is inserted and returned.

### Example: compute critical path

1. Client calls `GET /projects/{project_id}/critical-path`.
2. Router loads all project tasks and dependencies.
3. Service builds a directed graph and reverse graph.
4. Service topologically sorts the graph.
5. CPM forward pass computes earliest start and finish times.
6. CPM backward pass computes latest start and finish times.
7. Slack is derived from latest start minus earliest start.
8. Zero-slack tasks are returned as the critical path set.

## 8. The Most Important Algorithmic Idea

The core computer science idea in FlowDesk is:

> A project schedule can be represented as a directed acyclic graph (DAG), where nodes are tasks and edges mean "must happen before."

Why a DAG:

- task order matters
- cycles must be illegal because circular prerequisites make scheduling impossible
- DAGs allow topological sorting and CPM calculations

This is the conceptual heart of the project.

## 9. Graph Construction

The graph utilities are in `backend/app/services/graph.py`.

### `build_adjacency_list(dependencies)`

Input:

- a list of dependency records

Output:

- a dictionary mapping each task to the tasks that depend on it

If B depends on A, the graph stores:

`A -> [B]`

Why this direction is useful:

- it makes topological ordering natural
- it lets earliest times flow forward from prerequisites to dependents

### `reverse_adjacency_list(graph)`

This builds the reverse graph:

- original graph = task -> successors
- reverse graph = task -> predecessors

Why the reverse graph exists:

- earliest start of a task depends on the finish times of its predecessors
- reverse lookup makes that efficient and clean

### `has_path(graph, start, end)`

This is a DFS reachability check.

It answers:

- "Can I already reach `end` from `start` in the current graph?"

### `creates_cycle(dependencies, task_id, depends_on_task_id)`

This is a smart pre-insert cycle check.

If we are about to add:

`depends_on_task_id -> task_id`

then a cycle would be formed if there is already a path:

`task_id -> ... -> depends_on_task_id`

That is exactly what the code checks.

Interview defense:

> "Before inserting a new dependency, I check whether the dependent task can already reach the proposed prerequisite. If yes, adding the new edge would close a loop and create a cycle."

Complexity:

- graph build: `O(E)`
- DFS path check: `O(V + E)` in the project subgraph

## 10. Topological Sort

The implementation is in `backend/app/services/topological.py`.

It uses Kahn's algorithm.

### What it does

It returns a valid order of tasks such that every prerequisite appears before the task that depends on it.

### How it works

1. compute indegree for every node
2. push all zero-indegree nodes into a queue
3. repeatedly pop a node, add it to the result, and decrement indegree of its neighbors
4. whenever a neighbor reaches indegree zero, add it to the queue
5. if the final order does not contain all nodes, a cycle exists

Why it matters:

- CPM forward and backward passes assume tasks are processed in dependency-safe order
- cycle detection falls out naturally if not all nodes can be ordered

Complexity:

- `O(V + E)`

Strong interview phrasing:

> "I use topological sorting because scheduling on a dependency graph only makes sense if prerequisites are processed before dependents. Kahn's algorithm gives me both the order and a second layer of cycle detection."

## 11. Critical Path Method (CPM)

The CPM logic is in `backend/app/services/cpm.py`.

This is the most important algorithm section in the project.

### The data loaded before calculation

For a given project, the code loads:

- all tasks
- all durations as `task_id -> duration_estimate`
- all dependency edges
- adjacency list
- reverse adjacency list
- isolated tasks are explicitly added to the graph

That last step is important:

- tasks with no dependencies still count toward scheduling
- otherwise they would disappear from the graph and from CPM output

### Forward pass: earliest times

Function:

- `compute_earliest_times(graph, reverse_graph, topo_order, duration)`

Outputs:

- `ES`: earliest start
- `EF`: earliest finish

Formula:

- `ES(task) = max(EF of all predecessors)`, default `0` if none
- `EF(task) = ES(task) + duration(task)`

Interpretation:

- a task can only start after all prerequisites have finished

### Backward pass: latest times

Function:

- `compute_latest_times(graph, topo_order, duration, EF)`

Outputs:

- `LS`: latest start
- `LF`: latest finish

First it computes:

- `project_duration = max(EF.values())`

Then for tasks processed in reverse topological order:

- `LF(task) = min(LS of all successors)`, default `project_duration` if none
- `LS(task) = LF(task) - duration(task)`

Interpretation:

- latest times tell us how far we can delay a task without extending the project

### Slack

Function:

- `compute_slack(ES, LS)`

Formula:

- `slack(task) = LS(task) - ES(task)`

Meaning:

- slack is scheduling flexibility
- zero slack means the task cannot slip without affecting the overall timeline

### Critical path

Function:

- `critical_path(topo_order, slack, graph)`

Current implementation:

- returns all nodes in topological order where `slack == 0`

Why this is mostly correct:

- zero-slack tasks are critical tasks

Important nuance:

- this implementation returns the critical task set in order
- it does not reconstruct one explicit path when multiple zero-slack branches or ties exist

That is a strong "honest limitation" to mention if asked for rigor.

### Delay impact

Function:

- `delay_impact(task_id, delay_days, slack, EF, duration, graph, reverse_graph, topo_order)`

Logic:

1. if delay is within that task's slack, the project duration does not change
2. otherwise copy the duration map and increase the selected task's duration
3. recompute earliest times
4. compare new finish times to old finish times
5. return affected tasks and total project delay

Why this is a good design:

- it reuses the existing CPM logic instead of inventing a second forecasting algorithm
- it stays understandable and mathematically consistent

Complexity:

- one extra forward pass, so roughly `O(V + E)`

## 12. Worked Example You Can Explain in an Interview

The sample in `backend/app/services/test_cpm.py` gives a clean explanation case.

### Example graph

Dependencies:

- task 2 depends on task 1
- task 3 depends on task 1
- task 4 depends on task 2
- task 4 depends on task 3

Durations:

- task 1 = 2
- task 2 = 5
- task 3 = 3
- task 4 = 4

Graph:

```text
1 -> 2 -> 4
 \-> 3 -/
```

### Topological order

`[1, 2, 3, 4]`

### Earliest times

- `ES(1) = 0`, `EF(1) = 2`
- `ES(2) = 2`, `EF(2) = 7`
- `ES(3) = 2`, `EF(3) = 5`
- `ES(4) = max(7, 5) = 7`, `EF(4) = 11`

So project duration is:

- `11`

### Latest times

- `LF(4) = 11`, `LS(4) = 7`
- `LF(3) = 7`, `LS(3) = 4`
- `LF(2) = 7`, `LS(2) = 2`
- `LF(1) = min(2, 4) = 2`, `LS(1) = 0`

### Slack

- task 1: `0`
- task 2: `0`
- task 3: `2`
- task 4: `0`

### Critical path

`[1, 2, 4]`

Why:

- these tasks have zero slack
- any delay on them delays the whole project

### Delay examples

If task 2 is delayed by 3 days:

- task 2 was critical
- project delay becomes 3 days
- affected tasks are task 2 and task 4

If task 3 is delayed by 1 day:

- task 3 had 2 days of slack
- project delay remains 0

If task 3 is delayed by 3 days:

- it exceeds slack by 1 day
- project delay becomes 1 day

That example is excellent to say out loud because it proves you understand both critical path and slack.

## 13. Validation Rules and Why They Matter

The dependency endpoint contains the most meaningful business validation in the project.

### No self-dependency

Why:

- a task depending on itself is invalid by definition

### Both tasks must exist

Why:

- prevents orphan edges

### Both tasks must belong to the same project

Why:

- CPM is computed per project
- cross-project edges would break project boundaries and complicate scheduling semantics

### Duplicate dependency is blocked

Why:

- prevents redundant graph edges
- keeps results and storage cleaner

### Circular dependencies are blocked

Why:

- circular prerequisites make scheduling impossible
- topological order and CPM require a DAG

This is one of the strongest parts of the backend from an interview standpoint because it shows algorithmic validation, not just CRUD.

## 14. Time and Space Complexity

If someone asks for complexity, use this table.

| Operation | Complexity | Why |
|---|---|---|
| Build adjacency list | `O(E)` | one pass over dependencies |
| Reverse adjacency list | `O(V + E)` | initialize nodes and invert edges |
| Reachability DFS | `O(V + E)` | worst-case traversal |
| Cycle pre-check on new dependency | `O(V + E)` | graph build plus DFS |
| Topological sort | `O(V + E)` | each node and edge processed once |
| Earliest time pass | `O(V + E)` | predecessors examined across graph |
| Latest time pass | `O(V + E)` | successors examined across graph |
| Slack computation | `O(V)` | one value per task |
| Delay impact recomputation | `O(V + E)` | one updated forward pass |

Memory usage is also graph-shaped:

- adjacency lists, reverse graph, and time maps are all roughly `O(V + E)`

## 15. Design Choices You Can Defend

### Why FastAPI?

- quick API development
- automatic request validation
- clean dependency injection
- easy route organization

### Why SQLAlchemy ORM?

- readable model definitions
- relationships map well to the domain
- keeps persistence logic structured

### Why SQLite initially?

- low setup cost
- easy local testing
- enough for prototype-stage backend work

### Why use a graph instead of only SQL joins?

- dependency scheduling is fundamentally a graph problem
- algorithms like cycle detection, topological sort, and CPM are graph-native

### Why separate CPM into service functions?

- easier to test and reason about
- routers stay thin
- same logic could later be used by background jobs, CLI tools, or analytics endpoints

### Why topological sort before CPM?

- earliest and latest time calculations require dependency-safe ordering

### Why calculate slack?

- slack is what turns raw timing into actionable scheduling insight
- it tells you which tasks are flexible and which are critical

## 16. Honest Limitations in the Current Snapshot

This section matters a lot in interviews. Good engineers can describe tradeoffs without pretending the system is finished.

### Security and auth are not implemented yet

- `password_hash` is currently assigned directly from the input password
- there is no authentication or authorization layer

How to defend it:

> "This snapshot focuses on core scheduling behavior. In a production version, I would hash passwords properly, add auth, and enforce resource-level access control."

### No migrations yet

- tables are created with `create_all()`
- that is fine for prototyping but not ideal for schema evolution

Improvement:

- use Alembic migrations

### Dependency updates are missing

- there is create/read/delete for dependencies
- there is no patch/update route for dependencies

Why that is acceptable for now:

- creation is the risky operation because it can introduce invalid graph structure

### The critical path function returns critical nodes, not a reconstructed single path

- zero-slack nodes are identified correctly
- but in more complex graphs, "critical path" may be better represented as one or more full edge-connected paths

Improvement:

- reconstruct explicit path(s) from predecessor/successor relationships among zero-slack tasks

### Environment/bootstrap metadata is incomplete

- `pyproject.toml` is minimal and does not currently declare installable dependencies
- the listed FastAPI entrypoint looks stale compared to the actual code layout

How to say it:

> "The core application code is there, but the packaging/bootstrap layer still needs cleanup for production-quality setup."

### Test coverage is very light

- there is a CPM sample script
- there is not yet a full automated test suite for routes, DB behavior, and edge cases

Improvement:

- add pytest-based unit tests and API integration tests

### Naming consistency could be improved

Examples:

- schema classes like `workspaceCreate` use lowercase names
- dependency router prefix is `/Dependencies` with a capital D

This is not a functional issue, but it affects polish and consistency.

## 17. Likely Interview Questions and Strong Answers

### "What is the hardest technical part of FlowDesk?"

The scheduling engine, because once tasks depend on one another the problem becomes graph-based rather than simple CRUD. The important part was guaranteeing acyclic dependencies and then using topological order plus CPM passes to compute timing accurately.

### "Why did you model dependencies as a graph?"

Because task prerequisites naturally form directed edges. Once represented as a DAG, I can perform cycle detection, derive legal execution order, compute earliest and latest times, and analyze delay propagation cleanly.

### "How do you prevent invalid schedules?"

I validate dependency inserts with multiple checks: no self-dependency, both tasks must exist, tasks must be in the same project, duplicates are rejected, and a DFS reachability check prevents circular dependencies before insertion.

### "How do you compute the critical path?"

I build the project DAG, topologically sort it, run a forward pass for earliest start and finish times, run a backward pass for latest start and finish times, compute slack as `LS - ES`, and treat zero-slack tasks as critical.

### "What does slack mean in business terms?"

Slack is how much a task can move without delaying the project. If slack is zero, that task is on the critical path and any delay there directly affects the delivery date.

### "How do you estimate delay impact?"

If a delay fits inside the task's slack, the project finish date stays unchanged. If it exceeds slack, I increase that task's duration, recompute the forward pass, and compare the new finish times to the old ones to see which tasks and the overall project are affected.

### "What would you improve next?"

Authentication, password hashing, migrations, automated tests, better packaging, and a more rigorous critical path reconstruction for cases with multiple critical branches.

### "Why keep CPM logic outside the router?"

Because routers should coordinate requests and responses, while CPM is reusable domain logic. Separating them reduces coupling and makes testing easier.

## 18. How to Explain the App in 30 Seconds, 2 Minutes, and 5 Minutes

### 30-second version

FlowDesk is a FastAPI backend for project scheduling. It manages users, workspaces, projects, and tasks, then models task dependencies as a DAG so it can compute topological order, critical path, slack, project duration, and delay impact.

### 2-minute version

The codebase is split into models, schemas, routers, and services. Models define the relational structure in SQLAlchemy, schemas validate API input and output, routers handle CRUD and validation, and services contain graph and CPM algorithms. The most interesting part is dependency management: when a new dependency is added, the backend checks for self-links, cross-project links, duplicates, and cycles. For schedule analysis, it loads all project tasks and dependencies, builds a directed graph, topologically sorts it, computes earliest and latest timings, derives slack, and identifies the critical tasks. That lets the system answer not just "what tasks exist?" but also "what controls the timeline?" and "what happens if this task slips?"

### 5-minute version

Start with the domain hierarchy: user -> workspace -> project -> task -> dependency. Then explain that dependencies turn the project into a DAG. Once you have that graph, you can run two core operations: validation and scheduling. Validation means preventing cycles and illegal dependency relationships. Scheduling means running topological sort and CPM. The forward pass computes the earliest feasible schedule, the backward pass computes the latest safe schedule, and slack tells you which tasks are flexible. Zero-slack tasks form the critical set. Then explain delay impact as a recomputation problem: if a task takes longer, recompute earliest finishes and compare them to the baseline. Finish by acknowledging that the current snapshot is strong on scheduling logic but still needs production features like auth, migrations, and fuller tests.

## 19. If You Need to Defend Specific Files

### `main.py`

Responsible for bootstrapping the app and registering routers. Good separation of startup wiring from business logic.

### `database.py`

Centralizes engine/session setup, which keeps DB access patterns consistent across routers.

### `models/`

Defines the persistent domain. The ORM relationships make ownership and containment easy to reason about.

### `schemas/`

Protects the API boundary and prevents direct exposure of raw ORM internals.

### `routers/dependencies.py`

This is one of the best files to talk about because it demonstrates domain validation, data integrity, and graph reasoning.

### `routers/cpm.py`

This is the strongest algorithm file from a product perspective because it turns stored tasks into actionable schedule insights.

### `services/graph.py`

Contains the graph abstraction layer. This is where task dependencies become algorithm-friendly structures.

### `services/topological.py`

Implements execution ordering using Kahn's algorithm, which is standard, efficient, and interview-friendly.

### `services/cpm.py`

Contains the schedule math. This is the file to reference when discussing earliest/latest times, slack, critical path, and delay simulation.

## 20. Best Final Summary to Use in an Interview

If you want one polished explanation, use this:

> "FlowDesk is a scheduling-focused project management backend. I designed the data model around users, workspaces, projects, tasks, and task dependencies. The key technical decision was to treat dependencies as a directed acyclic graph, because that lets the system validate prerequisites, produce legal task orderings, and run Critical Path Method calculations. On top of normal CRUD APIs, the backend can compute earliest and latest execution windows, slack, critical tasks, and the impact of delays. The current version is strongest in its scheduling logic, and the next production steps would be auth, migrations, better packaging, and broader automated testing."

## 21. One-Line Memory Hooks

Use these if you blank out during an interview:

- FlowDesk is CRUD plus graph-based scheduling.
- Dependencies are stored in SQL but reasoned about as a DAG.
- Cycle prevention is what keeps the schedule valid.
- Topological sort gives legal execution order.
- CPM gives earliest time, latest time, slack, and critical tasks.
- Delay impact is just recomputing the schedule after changing duration.
- Zero slack means zero room for delay.

