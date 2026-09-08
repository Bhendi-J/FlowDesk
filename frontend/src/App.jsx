import { useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, { Background, Controls, MarkerType } from "reactflow";
import dagre from "dagre";
import { Pause, Play, RotateCcw, SkipForward } from "lucide-react";
import "reactflow/dist/style.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const NODE_WIDTH = 172;
const NODE_HEIGHT = 64;

function layoutGraph(tasks, dependencies, criticalIds) {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "LR", nodesep: 42, ranksep: 84 });

  tasks.forEach((task) => graph.setNode(String(task.id), { width: NODE_WIDTH, height: NODE_HEIGHT }));
  dependencies.forEach((dep) => graph.setEdge(String(dep.depends_on_task_id), String(dep.task_id)));
  dagre.layout(graph);

  const nodes = tasks.map((task) => {
    const pos = graph.node(String(task.id));
    const critical = criticalIds.has(task.id);
    return {
      id: String(task.id),
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: {
        label: (
          <div className="flow-node">
            <strong>{task.title}</strong>
            <span>t{task.constrained_start} to t{task.constrained_finish}</span>
          </div>
        ),
      },
      className: critical ? "node-critical" : "node-normal",
      style: { width: NODE_WIDTH, height: NODE_HEIGHT },
    };
  });

  const edges = dependencies.map((dep) => {
    const critical = criticalIds.has(dep.depends_on_task_id) && criticalIds.has(dep.task_id);
    return {
      id: `${dep.depends_on_task_id}-${dep.task_id}`,
      source: String(dep.depends_on_task_id),
      target: String(dep.task_id),
      animated: critical,
      markerEnd: { type: MarkerType.ArrowClosed },
      className: critical ? "edge-critical" : "edge-normal",
    };
  });

  return { nodes, edges };
}

function useDebouncedEffect(effect, deps, delay) {
  useEffect(() => {
    const handle = setTimeout(effect, delay);
    return () => clearTimeout(handle);
  }, deps);
}

export default function App() {
  const [examples, setExamples] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [schedule, setSchedule] = useState(null);
  const [resourceOverrides, setResourceOverrides] = useState({});
  const [durationOverrides, setDurationOverrides] = useState({});
  const [step, setStep] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestSeq = useRef(0);

  useEffect(() => {
    async function seedAndLoad() {
      try {
        const response = await fetch(`${API_BASE}/projects/seed-examples`, { method: "POST" });
        if (!response.ok) throw new Error("Could not seed examples");
        const data = await response.json();
        setExamples(data.projects);
        setProjectId(String(data.projects[0]?.id ?? ""));
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    seedAndLoad();
  }, []);

  useDebouncedEffect(() => {
    if (!projectId) return;
    const seq = ++requestSeq.current;
    async function simulate() {
      try {
        setError("");
        const response = await fetch(`${API_BASE}/projects/${projectId}/simulate-schedule`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resource_capacity_overrides: resourceOverrides,
            task_duration_overrides: durationOverrides,
          }),
        });
        if (!response.ok) throw new Error(await response.text());
        const data = await response.json();
        if (requestSeq.current === seq) {
          setSchedule(data);
          setStep(null);
          setPlaying(false);
        }
      } catch (err) {
        setError(err.message);
      }
    }
    simulate();
  }, [projectId, resourceOverrides, durationOverrides], 250);

  useEffect(() => {
    if (!playing || !schedule) return undefined;
    const handle = setInterval(() => {
      setStep((current) => {
        const next = current === null ? 1 : current + 1;
        if (next >= schedule.trace.length) {
          setPlaying(false);
          return schedule.trace.length;
        }
        return next;
      });
    }, 700);
    return () => clearInterval(handle);
  }, [playing, schedule]);

  const visibleTrace = useMemo(() => {
    if (!schedule) return [];
    if (step === null) return schedule.trace;
    return schedule.trace.slice(0, step);
  }, [schedule, step]);

  const visibleTaskIds = useMemo(
    () => new Set(visibleTrace.map((entry) => entry.task_id)),
    [visibleTrace],
  );

  const criticalIds = useMemo(
    () => new Set(schedule?.critical_path ?? []),
    [schedule],
  );

  const flow = useMemo(() => {
    if (!schedule) return { nodes: [], edges: [] };
    return layoutGraph(schedule.tasks, schedule.dependencies, criticalIds);
  }, [schedule, criticalIds]);

  const horizon = Math.max(1, schedule?.constrained_duration ?? 1);
  const naiveDuration = Math.max(1, schedule?.project_duration ?? 1);
  const inflation = schedule
    ? Math.round(((schedule.constrained_duration - schedule.project_duration) / naiveDuration) * 100)
    : 0;

  const traceByTask = useMemo(() => {
    const byTask = new Map();
    schedule?.trace.forEach((entry) => byTask.set(entry.task_id, entry));
    return byTask;
  }, [schedule]);

  const utilization = useMemo(() => {
    if (!schedule) return [];
    const active = new Set(visibleTrace.map((entry) => entry.task_id));
    return schedule.resources.map((resource) => {
      const ticks = Array.from({ length: horizon }, (_, tick) => {
        const used = schedule.tasks.reduce((sum, task) => {
          if (!active.has(task.id)) return sum;
          const amount = task.resource_requirements[String(resource.id)] ?? task.resource_requirements[resource.id] ?? 0;
          if (task.constrained_start <= tick && tick < task.constrained_finish) return sum + amount;
          return sum;
        }, 0);
        return { tick, used, pct: Math.min(100, Math.round((used / resource.capacity) * 100)) };
      });
      return { ...resource, ticks };
    });
  }, [schedule, visibleTrace, horizon]);

  function resetOverridesForProject(nextProjectId) {
    setProjectId(nextProjectId);
    setResourceOverrides({});
    setDurationOverrides({});
    setStep(null);
    setPlaying(false);
  }

  if (loading) return <div className="screen"><div className="status">Loading examples...</div></div>;

  return (
    <div className="screen">
      <aside className="sidebar">
        <div className="brand">FlowDesk</div>
        <select value={projectId} onChange={(event) => resetOverridesForProject(event.target.value)}>
          {examples.map((project) => (
            <option value={project.id} key={project.id}>{project.name}</option>
          ))}
        </select>

        <div className="stat">
          <span>Schedule inflation</span>
          <strong>+{inflation}%</strong>
        </div>

        <div className="playbar">
          <button title="Reset" onClick={() => { setStep(0); setPlaying(false); }}><RotateCcw size={18} /></button>
          <button title={playing ? "Pause" : "Play"} onClick={() => setPlaying(!playing)}>
            {playing ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <button title="Step" onClick={() => setStep((current) => Math.min(schedule?.trace.length ?? 0, (current ?? 0) + 1))}>
            <SkipForward size={18} />
          </button>
        </div>

        <section>
          <h2>Resource Capacity</h2>
          {schedule?.resources.map((resource) => (
            <label className="slider-row" key={resource.id}>
              <span>{resource.name}</span>
              <input
                type="range"
                min="1"
                max="4"
                value={resourceOverrides[resource.id] ?? resource.capacity}
                onChange={(event) => setResourceOverrides({ ...resourceOverrides, [resource.id]: Number(event.target.value) })}
              />
              <b>{resourceOverrides[resource.id] ?? resource.capacity}</b>
            </label>
          ))}
        </section>

        <section>
          <h2>Task Duration</h2>
          {schedule?.tasks.map((task) => (
            <label className="slider-row" key={task.id}>
              <span>{task.title}</span>
              <input
                type="range"
                min="1"
                max="10"
                value={durationOverrides[task.id] ?? task.duration}
                onChange={(event) => setDurationOverrides({ ...durationOverrides, [task.id]: Number(event.target.value) })}
              />
              <b>{durationOverrides[task.id] ?? task.duration}</b>
            </label>
          ))}
        </section>
      </aside>

      <main className="workspace">
        {error && <div className="error">{error}</div>}
        <section className="graph-panel">
          <ReactFlow nodes={flow.nodes} edges={flow.edges} fitView nodesDraggable={false}>
            <Background gap={18} />
            <Controls />
          </ReactFlow>
        </section>

        <section className="timeline">
          <div className="axis" style={{ "--ticks": horizon + 1 }}>
            {Array.from({ length: horizon + 1 }, (_, tick) => <span key={tick}>t{tick}</span>)}
          </div>
          {schedule?.tasks.map((task) => {
            const delayed = task.constrained_start > task.earliest_start;
            const trace = traceByTask.get(task.id);
            const visible = visibleTaskIds.has(task.id);
            const tooltip = trace?.blocked_by
              ? `waiting on ${trace.blocked_by.resource_name} - in use by ${trace.blocked_by.task_title} until t=${trace.blocked_by.blocked_until}`
              : "";
            return (
              <div className={`task-line ${visible ? "is-visible" : ""}`} key={task.id} title={tooltip}>
                <span className="task-label">{task.title}</span>
                <div className="bar-lane">
                  <div
                    className="bar naive"
                    style={{ left: `${(task.earliest_start / horizon) * 100}%`, width: `${((task.earliest_finish - task.earliest_start) / horizon) * 100}%` }}
                  />
                  {visible && (
                    <div
                      className={`bar constrained ${delayed ? "delayed" : ""}`}
                      style={{ left: `${(task.constrained_start / horizon) * 100}%`, width: `${((task.constrained_finish - task.constrained_start) / horizon) * 100}%` }}
                    />
                  )}
                </div>
              </div>
            );
          })}
        </section>

        <section className="resources">
          {utilization.map((resource) => (
            <div className="resource-row" key={resource.id}>
              <span>{resource.name}</span>
              <div className="resource-strip">
                {resource.ticks.map((tick) => (
                  <i
                    key={tick.tick}
                    className={tick.pct >= 100 ? "hot" : tick.pct >= 60 ? "warm" : "cool"}
                    title={`t${tick.tick}: ${tick.used}/${resource.capacity}`}
                  />
                ))}
              </div>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
