from pydantic import BaseModel, Field


class SimulateScheduleRequest(BaseModel):
    resource_capacity_overrides: dict[int, int] = Field(default_factory=dict)
    task_duration_overrides: dict[int, int] = Field(default_factory=dict)


class TaskDurationEstimateOverride(BaseModel):
    optimistic: int | None = None
    likely: int | None = None
    pessimistic: int | None = None


class SimulateMonteCarloRequest(BaseModel):
    num_trials: int = 1000
    resource_capacity_overrides: dict[int, int] = Field(default_factory=dict)
    task_duration_estimate_overrides: dict[int, TaskDurationEstimateOverride] = Field(
        default_factory=dict
    )
    seed: int | None = None


class ScheduleBlockedBy(BaseModel):
    resource_id: int
    resource_name: str
    task_id: int
    task_title: str
    blocked_until: int


class ScheduleTraceEntry(BaseModel):
    task_id: int
    assigned_start: int
    assigned_finish: int
    blocked_by: ScheduleBlockedBy | None = None


class ScheduledTask(BaseModel):
    id: int
    title: str
    duration: int
    duration_optimistic: int | None = None
    duration_likely: int | None = None
    duration_pessimistic: int | None = None
    earliest_start: int
    earliest_finish: int
    latest_start: int
    latest_finish: int
    slack: int
    constrained_start: int
    constrained_finish: int
    resource_requirements: dict[int, int] = Field(default_factory=dict)


class MonteCarloSummary(BaseModel):
    min: int
    max: int
    mean: float
    stdev: float
    p10: float
    p50: float
    p90: float


class MonteCarloHistogram(BaseModel):
    bucket_edges: list[float]
    counts: list[int]


class MonteCarloTrial(BaseModel):
    project_duration: int
    sampled_durations: dict[int, int]
    slack: dict[int, int]


class ScheduleResource(BaseModel):
    id: int
    name: str
    capacity: int


class ScheduleDependency(BaseModel):
    task_id: int
    depends_on_task_id: int


class ScheduleResponse(BaseModel):
    topo_order: list[int]
    ES: dict[int, int]
    EF: dict[int, int]
    LS: dict[int, int]
    LF: dict[int, int]
    slack: dict[int, int]
    critical_path: list[int]
    project_duration: int
    constrained_duration: int
    tasks: list[ScheduledTask]
    resources: list[ScheduleResource]
    dependencies: list[ScheduleDependency]
    trace: list[ScheduleTraceEntry]


class MonteCarloResponse(BaseModel):
    num_trials: int
    project_durations: list[int]
    summary: MonteCarloSummary
    histogram: MonteCarloHistogram
    criticality_index: dict[int, float]
    trials: list[MonteCarloTrial]
