import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, { Background, Controls, MiniMap, MarkerType, Position, useReactFlow, useStore } from "reactflow";
import dagre from "dagre";
import { Activity, ArrowRight, Check, ChevronDown, GitBranch, LoaderCircle, Pause, Play, RotateCcw, SkipForward, SlidersHorizontal, X } from "lucide-react";
import { changeEstimate, estimateFor, isCriticalEdge, resourceSegments, timelineTicks } from "./schedule-utils.mjs";
import "reactflow/dist/style.css";

import { request } from "./api.mjs";
import TaskManager from "./TaskManager.jsx";

function FitGraph({ layout }) {
  const { fitView } = useReactFlow();
  const width = useStore(state => state.width);
  const height = useStore(state => state.height);
  useEffect(() => {
    const frame = requestAnimationFrame(() => fitView({ padding: 0.22, duration: 250, maxZoom: 1.15 }));
    return () => cancelAnimationFrame(frame);
  }, [layout, fitView, width, height]);
  return null;
}

function layoutGraph(schedule, criticalIds) {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "LR", nodesep: 44, ranksep: 72 });
  schedule.tasks.forEach(task => graph.setNode(String(task.id), { width: 196, height: 92 }));
  schedule.dependencies.forEach(dep => graph.setEdge(String(dep.depends_on_task_id), String(dep.task_id)));
  dagre.layout(graph);
  return {
    nodes: schedule.tasks.map(task => {
      const pos = graph.node(String(task.id));
      return {
        id: String(task.id), position: { x: pos.x - 98, y: pos.y - 46 },
        sourcePosition: Position.Right, targetPosition: Position.Left,
        data: { task }, style: { width: 196, height: 92 },
      };
    }),
    edges: schedule.dependencies.map(dep => {
      const critical = isCriticalEdge(dep, schedule.tasks, criticalIds);
      return {
        id: `${dep.depends_on_task_id}-${dep.task_id}`, source: String(dep.depends_on_task_id), target: String(dep.task_id),
        type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed, color: critical ? "#d07843" : "#9ca9a4" },
        style: { stroke: critical ? "#d07843" : "#9ca9a4", strokeWidth: critical ? 2.5 : 1.5 },
      };
    }),
  };
}

function Legend({ items }) {
  return <div className="legend">{items.map(([color, label]) => <span key={label}><i style={{ background: color }} />{label}</span>)}</div>;
}

function TimeAxis({ horizon }) {
  return <div className="axis">{timelineTicks(horizon).map(tick => <span key={tick} style={{ left: `${tick / horizon * 100}%` }}>t{tick}</span>)}</div>;
}

export default function App() {
  const [examples, setExamples] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [schedule, setSchedule] = useState(null);
  const [resourceOverrides, setResourceOverrides] = useState({});
  const [durationOverrides, setDurationOverrides] = useState({});
  const [estimates, setEstimates] = useState({});
  const [trialCount, setTrialCount] = useState(1000);
  const [monteCarlo, setMonteCarlo] = useState(null);
  const [runningMonteCarlo, setRunningMonteCarlo] = useState(false);
  const [step, setStep] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [revision, setRevision] = useState(0);
  const [mutating, setMutating] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [criticalOnly, setCriticalOnly] = useState(false);
  const mcController = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    request("/projects/", undefined, controller.signal, "GET").then(async projects => {
      if (!projects.length && !controller.signal.aborted) {
        const seeded = await request("/projects/seed-examples", {}, controller.signal);
        return seeded.projects;
      }
      return projects;
    }).then(projects => {
      if (controller.signal.aborted) return;
      setExamples(projects);
      setProjectId(current => current || String(projects[0]?.id ?? ""));
    }).catch(err => { if (!controller.signal.aborted) setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retry]);

  useEffect(() => {
    if (!projectId) return;
    const controller = new AbortController();
    setSimulating(true);
    setPlaying(false);
    setStep(null);
    setError("");
    const timer = setTimeout(() => {
      request(`/projects/${projectId}/simulate-schedule`, {
        resource_capacity_overrides: resourceOverrides, task_duration_overrides: durationOverrides,
      }, controller.signal).then(data => {
        if (!controller.signal.aborted) setSchedule(data);
      }).catch(err => {
        if (controller.signal.aborted) return;
        if (err.status === 404 && err.message === "No tasks found for project") setSchedule(null);
        else setError(err.message);
      })
        .finally(() => { if (!controller.signal.aborted) setSimulating(false); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [projectId, resourceOverrides, durationOverrides, retry, revision]);

  useEffect(() => {
    mcController.current?.abort();
    setRunningMonteCarlo(false);
    setMonteCarlo(null);
    return () => mcController.current?.abort();
  }, [projectId, resourceOverrides, durationOverrides, estimates, trialCount, retry, revision]);

  useEffect(() => {
    if (!playing || !schedule) return;
    const timer = setInterval(() => setStep(current => Math.min((current ?? 0) + 1, schedule.trace.length)), 800);
    return () => clearInterval(timer);
  }, [playing, schedule]);
  useEffect(() => { if (schedule && step === schedule.trace.length) setPlaying(false); }, [step, schedule]);

  const criticalIds = useMemo(() => new Set(schedule?.critical_path ?? []), [schedule]);
  const layout = useMemo(() => schedule ? layoutGraph(schedule, criticalIds) : { nodes: [], edges: [] }, [schedule, criticalIds]);
  const activeIds = useMemo(() => new Set((step === null ? schedule?.trace : schedule?.trace.slice(0, step))?.map(item => item.task_id)), [schedule, step]);
  const flowNodes = useMemo(() => layout.nodes.map(node => {
    const task = node.data.task;
    const critical = criticalIds.has(task.id);
    return { ...node, selected: task.id === selectedId,
      className: `${critical ? "node-critical" : ""} ${!activeIds.has(task.id) || (criticalOnly && !critical) ? "node-muted" : ""}`,
      data: { label: <div className="flow-node"><div className="node-top"><span>#{task.id}</span><span>{critical ? "Critical path" : `${task.slack} slack`}</span></div><strong title={task.title}>{task.title}</strong><div className="node-bottom"><span>t{task.constrained_start} <ArrowRight size={11} /> t{task.constrained_finish}</span><b>{monteCarlo ? `${Math.round(monteCarlo.criticality_index[task.id] ?? 0)}% critical` : `${task.duration} units`}</b></div></div> },
    };
  }), [layout, criticalIds, selectedId, activeIds, criticalOnly, monteCarlo]);
  const horizon = Math.max(1, schedule?.constrained_duration ?? 1, schedule?.project_duration ?? 1);
  const delay = schedule ? schedule.constrained_duration - schedule.project_duration : 0;
  const inflation = schedule?.project_duration ? Math.round(delay / schedule.project_duration * 100) : 0;
  const selected = schedule?.tasks.find(task => task.id === selectedId);
  const trace = schedule?.trace.find(item => item.task_id === selectedId);
  const project = examples.find(item => String(item.id) === projectId);
  const busy = loading || simulating || mutating;
  const changed = Object.keys(resourceOverrides).length + Object.keys(estimates).length > 0;

  function reset(nextId = projectId) {
    if (nextId !== projectId) setSchedule(null);
    setProjectId(nextId); setResourceOverrides({}); setDurationOverrides({}); setEstimates({});
    setSelectedId(null); setStep(null); setPlaying(false); setCriticalOnly(false);
  }
  function updateEstimate(task, field, value) {
    const next = changeEstimate(estimateFor(task, estimates), field, value);
    setEstimates(current => ({ ...current, [task.id]: next }));
    setDurationOverrides(current => ({ ...current, [task.id]: next.likely }));
  }
  async function runMonteCarlo() {
    if (!schedule || busy || error) return;
    mcController.current?.abort();
    const controller = new AbortController();
    mcController.current = controller;
    setRunningMonteCarlo(true);
    setError("");
    try {
      const data = await request(`/projects/${projectId}/simulate-monte-carlo`, {
        num_trials: trialCount, resource_capacity_overrides: resourceOverrides,
        task_duration_estimate_overrides: Object.fromEntries(schedule.tasks.map(task => [task.id, estimateFor(task, estimates)])),
      }, controller.signal);
      if (!controller.signal.aborted) setMonteCarlo(data);
    } catch (err) { if (!controller.signal.aborted) setError(err.message); }
    finally { if (!controller.signal.aborted) setRunningMonteCarlo(false); }
  }

  return <div className="screen">
    <aside className="sidebar">
      <a className="brand" href="./"><span className="brand-icon"><GitBranch size={21} /></span>FlowDesk<span className="brand-tag">LAB</span></a>
      <div className="sidebar-intro">Make room for what’s next.</div>
      <label className="field-label" htmlFor="project">PROJECT</label>
      <select id="project" value={projectId} disabled={loading || mutating || !examples.length} onChange={event => reset(event.target.value)}>{!examples.length && <option>No projects available</option>}{examples.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <div className="sidebar-heading"><SlidersHorizontal size={16} /><h2>Scenario controls</h2><span className="pill">Sandbox</span></div>
      <p className="helper">Explore changes without saving them to your project.</p>
      <section className="control-section"><h3>Resource capacity</h3>{schedule?.resources.length === 0 && <p className="helper">No shared resources in this project.</p>}{schedule?.resources.map(resource => <label className="capacity-control" key={resource.id}><span>{resource.name}<b>{resourceOverrides[resource.id] ?? resource.capacity} <small>units</small></b></span><input type="range" min="1" max={Math.max(8, resource.capacity)} value={resourceOverrides[resource.id] ?? resource.capacity} onChange={event => setResourceOverrides(current => ({ ...current, [resource.id]: Number(event.target.value) }))} /></label>)}</section>
      <section className="control-section"><h3>Task duration estimates</h3><p className="helper">Time units · optimistic ≤ likely ≤ pessimistic</p>{schedule?.tasks.map(task => <details className="estimate-group" key={task.id}><summary><span>{task.title}</span><b>{estimateFor(task, estimates).likely}t</b><ChevronDown size={14} /></summary>{["optimistic", "likely", "pessimistic"].map(field => <label className="slider-row" key={field}><span>{field}</span><input aria-label={`${task.title}: ${field} duration`} type="range" min="1" max={Math.max(30, estimateFor(task, estimates)[field])} value={estimateFor(task, estimates)[field]} onChange={event => updateEstimate(task, field, Number(event.target.value))} /><b>{estimateFor(task, estimates)[field]}</b></label>)}</details>)}</section>
      <section className="control-section"><h3>Uncertainty analysis</h3><p className="helper">Sample task estimates to explore possible project durations.</p><label className="sr-only" htmlFor="trials">Simulation trials</label><select id="trials" value={trialCount} onChange={event => setTrialCount(Number(event.target.value))}>{[100, 1000, 5000].map(count => <option key={count} value={count}>{count.toLocaleString()} trials</option>)}</select><button className="primary run-button" onClick={runMonteCarlo} disabled={!schedule || busy || runningMonteCarlo || !!error}>{runningMonteCarlo ? <LoaderCircle className="spin" size={16} /> : <Activity size={16} />}{runningMonteCarlo ? "Running simulation…" : "Run simulation"}</button></section>
      <button className="reset-button" disabled={!changed} onClick={() => reset()}><RotateCcw size={14} />Reset scenario</button>
      <div className="sidebar-footer"><span className="live-dot" />Resource-constrained scheduling</div>
    </aside>
    <main className="workspace">
      <header className="page-header"><div><div className="eyebrow">WORKSPACE <span>/</span> SCHEDULE EXPLORER</div><h1>{project?.name ?? "Schedule explorer"}</h1><p>Understand dependencies. Uncover bottlenecks. Explore better schedules.</p></div><span className={`status-pill ${busy ? "pending" : error ? "failed" : ""}`} role="status">{busy ? <LoaderCircle size={14} className="spin" /> : error ? <X size={14} /> : <Check size={14} />}{busy ? "Updating schedule" : error ? "Needs attention" : "Scenario ready"}</span></header>
      {error && <div className="error" role="alert"><div><strong>Unable to complete the request</strong><p>{error === "Failed to fetch" ? "Cannot reach the scheduling API. Check that the backend is running, then retry." : error}</p>{schedule && <small>Charts show the last successful schedule.</small>}</div><button onClick={() => setRetry(current => current + 1)}>Retry</button></div>}
      <div className="metrics" aria-busy={busy}>{[["Baseline duration", schedule?.project_duration, "Without resource limits"], ["Constrained duration", schedule?.constrained_duration, "With shared resource capacity"], ["Resource delay", schedule ? `+${delay}` : undefined, `${inflation}% longer than baseline`], ["Critical tasks", schedule?.critical_path.length, `${schedule?.tasks.length ?? 0} tasks in this project`]].map(([label, value, caption], index) => <div className={`metric metric-${index}`} key={label}><span>{label}</span><strong>{value ?? "—"}{index < 3 && <small>time units</small>}</strong><p>{caption}</p></div>)}</div>
      {projectId && <TaskManager key={projectId} projectId={projectId} resources={schedule?.resources ?? []} revision={revision} onBusy={setMutating} onChanged={() => {
        setSchedule(null);
        setSimulating(true);
        reset();
        setRevision(current => current + 1);
      }} />}
      {!schedule ? <div className="empty-state">{busy ? <><LoaderCircle size={28} className="spin" /><h2>Building your schedule</h2><p>Arranging dependencies and resource assignments…</p></> : <><GitBranch size={28} /><h2>No schedule available</h2><p>{error ? "Resolve the request above to load the explorer." : "Add tasks to a project to explore its schedule."}</p></>}</div> : <>
        <section className="panel" aria-labelledby="graph-title" aria-busy={simulating}><div className="panel-head"><div><h2 id="graph-title"><GitBranch size={17} />Dependency graph</h2><p>Select a task to inspect its timing and resource needs.</p></div><label className="toggle"><input type="checkbox" checked={criticalOnly} onChange={event => setCriticalOnly(event.target.checked)} />Focus critical path</label></div>
          <div className="graph-panel"><ReactFlow nodes={flowNodes} edges={layout.edges} fitView minZoom={0.15} maxZoom={2} nodesDraggable={false} nodesConnectable={false} elementsSelectable onNodeClick={(_, node) => setSelectedId(Number(node.id))} onPaneClick={() => setSelectedId(null)} proOptions={{ hideAttribution: false }}><Background gap={20} color="#dce4df" /><Controls showInteractive={false} /><MiniMap pannable zoomable nodeColor={node => criticalIds.has(Number(node.id)) ? "#d07843" : "#39826c"} maskColor="rgba(240,245,242,.7)" /><FitGraph layout={layout} /></ReactFlow></div>
          <div className="panel-foot"><Legend items={[["#d07843", "Baseline critical path"], ["#39826c", "Other tasks"]]} /><span>Scroll to zoom · drag to pan</span></div>
          {selected && <div className="task-inspector"><div className="inspector-title"><strong>{selected.title}</strong><button aria-label="Close task details" onClick={() => setSelectedId(null)}><X size={16} /></button></div><dl>{[["Baseline", `t${selected.earliest_start} → t${selected.earliest_finish}`], ["Constrained", `t${selected.constrained_start} → t${selected.constrained_finish}`], ["Start delay", `${selected.constrained_start - selected.earliest_start} units`], ["Baseline slack", `${selected.slack} units`]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><p>Resources: {schedule.resources.filter(resource => selected.resource_requirements[resource.id]).map(resource => `${resource.name} × ${selected.resource_requirements[resource.id]}`).join(", ") || "None required"}</p>{trace?.blocked_by && <p className="blocking-note">Waiting on {trace.blocked_by.resource_name}, used by {trace.blocked_by.task_title} until t{trace.blocked_by.blocked_until}.</p>}</div>}
        </section>
        <section className="panel" aria-labelledby="timeline-title"><div className="panel-head"><div><h2 id="timeline-title">Schedule timeline</h2><p>Compare the baseline with the resource-constrained plan.</p></div><div className="playback"><span aria-live="polite">{step ?? schedule.trace.length} / {schedule.trace.length} assigned</span><button aria-label="Reset playback" title="Reset playback" disabled={busy} onClick={() => { setStep(0); setPlaying(false); }}><RotateCcw size={15} /></button><button className="primary" aria-label={playing ? "Pause playback" : "Play schedule"} disabled={busy || !schedule.trace.length} onClick={() => { if (step === null || step >= schedule.trace.length) setStep(0); setPlaying(current => !current); }}>{playing ? <Pause size={15} /> : <Play size={15} />}</button><button aria-label="Next assignment" title="Next assignment" disabled={busy || step === schedule.trace.length} onClick={() => { setPlaying(false); setStep(current => Math.min((current ?? 0) + 1, schedule.trace.length)); }}><SkipForward size={15} /></button><button disabled={busy || step === null} onClick={() => { setStep(null); setPlaying(false); }}>Show all</button></div></div>
          <div className="chart-scroll"><div className="timeline-chart"><TimeAxis horizon={horizon} />{schedule.tasks.map(task => <div key={task.id} className={`task-line ${selectedId === task.id ? "selected" : ""}`}><button className="task-label" title={task.title} onClick={() => setSelectedId(task.id)}><i className={criticalIds.has(task.id) ? "critical-dot" : "normal-dot"} />{task.title}</button><div className="bar-lane">{timelineTicks(horizon).map(tick => <i className="gridline" key={tick} style={{ left: `${tick / horizon * 100}%` }} />)}<div className="bar naive" title={`Baseline: t${task.earliest_start}–t${task.earliest_finish}`} style={{ left: `${task.earliest_start / horizon * 100}%`, width: `${(task.earliest_finish - task.earliest_start) / horizon * 100}%` }} />{activeIds.has(task.id) && <button aria-label={`${task.title}: t${task.constrained_start} to t${task.constrained_finish}, delay ${task.constrained_start - task.earliest_start} units`} className={`bar constrained ${task.constrained_start > task.earliest_start ? "delayed" : ""}`} onClick={() => setSelectedId(task.id)} title={`Scheduled: t${task.constrained_start}–t${task.constrained_finish} · Delay: ${task.constrained_start - task.earliest_start}`} style={{ left: `${task.constrained_start / horizon * 100}%`, width: `${(task.constrained_finish - task.constrained_start) / horizon * 100}%` }}>{task.duration}t</button>}</div></div>)}</div></div><div className="panel-foot"><Legend items={[["#dce6e1", "Baseline"], ["#39826c", "Constrained"], ["#d07843", "Delayed start"]]} /><span>All values in time units</span></div>
        </section>
        <section className="panel"><div className="panel-head"><div><h2>Resource utilization</h2><p>Spot capacity pressure across the schedule.</p></div><Legend items={[["#e9eeeb", "Idle"], ["#a6d4be", "Below 60%"], ["#efd08b", "60–99%"], ["#dd8e7c", "100%+"]]} /></div>{schedule.resources.length ? <div className="chart-scroll"><div className="timeline-chart"><TimeAxis horizon={horizon} />{schedule.resources.map(resource => <div className="resource-row" key={resource.id}><span>{resource.name}<small>{resource.capacity} units available</small></span><div className="resource-strip">{resourceSegments(schedule.tasks, resource, activeIds, horizon).map(segment => <div key={segment.start} className={segment.used === 0 ? "idle" : segment.pct >= 100 ? "hot" : segment.pct >= 60 ? "warm" : "cool"} style={{ width: `${(segment.end - segment.start) / horizon * 100}%` }} title={`t${segment.start}–t${segment.end}: ${segment.used}/${resource.capacity} units (${Math.round(segment.pct)}%)`}><span>{Math.round(segment.pct)}%</span></div>)}</div></div>)}</div></div> : <p className="empty-inline">No shared resources assigned.</p>}</section>
        <section className="panel"><div className="panel-head"><div><h2><Activity size={17} />Duration uncertainty</h2><p>{monteCarlo ? `${monteCarlo.num_trials.toLocaleString()} trials · estimated project completion distribution` : "See how variation in task estimates affects the finish date."}</p></div>{monteCarlo && <span className="pill">Mean {monteCarlo.summary.mean.toFixed(1)}t</span>}</div>{monteCarlo ? <><div className="percentiles">{[["p10", "10th percentile"], ["p50", "Median duration"], ["p90", "90th percentile"]].map(([key, label]) => <div key={key}><span>{label}</span><strong>{monteCarlo.summary[key]}<small> time units</small></strong></div>)}</div><Histogram data={monteCarlo.histogram} summary={monteCarlo.summary} /></> : <div className="uncertainty-empty"><Activity size={25} /><p>{runningMonteCarlo ? "Sampling possible schedules…" : "Your next insight is one simulation away."}</p><button disabled={busy || runningMonteCarlo || !!error} onClick={runMonteCarlo}>{runningMonteCarlo ? "Running…" : `Run ${trialCount.toLocaleString()} trials`}<ArrowRight size={14} /></button></div>}</section>
      </>}
      <footer className="workspace-footer">FlowDesk / Schedule explorer<span>Task changes saved · Scenario sliders temporary</span></footer>
    </main>
  </div>;
}

function Histogram({ data, summary }) {
  const width = 840, height = 240, left = 52, right = 24, top = 30, bottom = 44;
  const plotHeight = height - top - bottom;
  const maxCount = Math.max(...data.counts, 1);
  const min = data.bucket_edges[0] ?? 0, max = data.bucket_edges.at(-1) ?? 1;
  const x = value => min === max ? (left + width - right) / 2 : left + (value - min) / (max - min) * (width - left - right);
  return <div className="histogram"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Project duration distribution. Median ${summary.p50}, 90th percentile ${summary.p90} time units.`}><title>Project duration frequency</title>{[0, 0.5, 1].map(ratio => <g key={ratio}><line className="histogram-grid" x1={left} x2={width - right} y1={top + plotHeight * (1 - ratio)} y2={top + plotHeight * (1 - ratio)} /><text x={left - 10} y={top + plotHeight * (1 - ratio) + 4} textAnchor="end">{Math.round(maxCount * ratio)}</text></g>)}{data.counts.map((count, index) => <rect key={index} x={min === max ? x(min) - 20 : x(data.bucket_edges[index]) + 1} y={top + plotHeight * (1 - count / maxCount)} width={min === max ? 40 : Math.max(1, x(data.bucket_edges[index + 1]) - x(data.bucket_edges[index]) - 2)} height={count / maxCount * plotHeight} rx="3"><title>{data.bucket_edges[index]}–{data.bucket_edges[index + 1]} time units: {count} trials</title></rect>)}{["p10", "p50", "p90"].map((key, index) => <g key={key}><line className="percentile-line" x1={x(summary[key])} x2={x(summary[key])} y1={top} y2={height - bottom} /><text x={x(summary[key])} y={12 + index * 10} textAnchor="middle">{key}</text></g>)}<text x={left} y={height - 24}>{min}t</text><text x={width - right} y={height - 24} textAnchor="end">{max}t</text><text x={width / 2} y={height - 5} textAnchor="middle">Project duration (time units)</text><text x={left} y={14}>Trials</text></svg></div>;
}
