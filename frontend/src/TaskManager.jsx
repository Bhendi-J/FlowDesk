import React, { useEffect, useRef, useState } from "react";
import { ClipboardList, LoaderCircle, Plus, Trash2, X } from "lucide-react";
import { request } from "./api.mjs";

const emptyForm = () => ({ title: "", description: "", duration_estimate: 1, status: "pending", priority: "medium", depends_on_task_ids: [], resource_requirements: {} });

export default function TaskManager({ projectId, resources, revision, onChanged, onBusy }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const dialog = useRef(null);
  const submitting = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    request(`/tasks/?project_id=${projectId}`, undefined, controller.signal, "GET")
      .then(data => { if (!controller.signal.aborted) setTasks(data); })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [projectId, revision, refresh]);

  useEffect(() => {
    if (modal && !dialog.current.open) dialog.current.showModal();
    else if (!modal && dialog.current.open) dialog.current.close();
  }, [modal]);

  function open(next) {
    setForm(emptyForm());
    setFormError("");
    setModal(next);
  }
  function update(field, value) { setForm(current => ({ ...current, [field]: value })); }

  async function submit(event) {
    event.preventDefault();
    if (submitting.current) return;
    if (modal.type === "add" && !form.title.trim()) {
      setFormError("Enter a task title.");
      return;
    }
    submitting.current = true;
    setSaving(true);
    onBusy(true);
    setFormError("");
    setNotice("");
    try {
      if (modal.type === "add") {
        await request("/tasks/", {
          ...form, title: form.title.trim(), description: form.description.trim() || null,
          project_id: Number(projectId), duration_estimate: Number(form.duration_estimate),
          resource_requirements: Object.fromEntries(Object.entries(form.resource_requirements).filter(([, amount]) => amount > 0)),
        });
        setNotice(`“${form.title.trim()}” added to the project.`);
      } else {
        await request(`/tasks/${modal.task.id}`, undefined, undefined, "DELETE");
        setNotice(`“${modal.task.title}” deleted. Its dependency links and resource assignments were removed.`);
      }
      setModal(null);
      onChanged();
    } catch (err) {
      setFormError(err.message === "Failed to fetch" ? "Cannot reach the API. Check the connection and try again." : err.message);
    } finally {
      submitting.current = false;
      setSaving(false);
      onBusy(false);
    }
  }

  return <section className="panel task-manager" aria-labelledby="tasks-title">
    <div className="panel-head">
      <div><h2 id="tasks-title"><ClipboardList size={17} />Project tasks <span className="pill">{loading ? "…" : tasks.length}</span></h2><p>Add and delete tasks here. These changes are saved to your project.</p></div>
      <button className="primary" disabled={loading || saving || !!error} onClick={() => open({ type: "add" })}><Plus size={15} />Add task</button>
    </div>
    {notice && <div className="task-notice" role="status">{notice}</div>}
    {error ? <div className="error" role="alert"><p>{error}</p><button onClick={() => setRefresh(value => value + 1)}>Reload tasks</button></div>
      : loading ? <p className="empty-inline" role="status">Loading tasks…</p>
      : tasks.length === 0 ? <div className="tasks-empty"><ClipboardList size={25} /><p>No tasks yet. Add your first task to build a schedule.</p><button onClick={() => open({ type: "add" })}><Plus size={14} />Create first task</button></div>
      : <div className="task-table-scroll"><table className="task-table"><thead><tr><th scope="col">Task</th><th scope="col">Status</th><th scope="col">Priority</th><th scope="col">Duration</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead><tbody>{tasks.map(task => <tr key={task.id}>
        <td><strong>{task.title}</strong>{task.description && <p>{task.description}</p>}</td>
        <td><span className={`task-status ${task.status}`}>{task.status.replaceAll("_", " ")}</span></td>
        <td><span className={`task-priority ${task.priority}`}>{task.priority}</span></td>
        <td>{task.duration_estimate} <span className="muted">units</span></td>
        <td><button className="danger-quiet" aria-label={`Delete ${task.title}`} title={`Delete ${task.title}`} disabled={saving} onClick={() => open({ type: "delete", task })}><Trash2 size={15} /></button></td>
      </tr>)}</tbody></table></div>}
    <dialog ref={dialog} className="task-dialog" aria-labelledby="task-dialog-title" onCancel={event => { if (saving) event.preventDefault(); else setModal(null); }} onClose={() => setModal(null)}>
      {modal && <form onSubmit={submit}>
        <div className="dialog-head"><div><h2 id="task-dialog-title">{modal.type === "add" ? "Add a task" : "Delete task?"}</h2><p>{modal.type === "add" ? "Define the work and where it fits in your schedule." : modal.task.title}</p></div><button type="button" aria-label="Close dialog" disabled={saving} onClick={() => setModal(null)}><X size={17} /></button></div>
        {formError && <div className="error" role="alert">{formError}</div>}
        {modal.type === "add" ? <fieldset disabled={saving} className="task-fields">
          <label>Task title<input autoFocus required maxLength={100} value={form.title} onChange={event => update("title", event.target.value)} placeholder="e.g. Review release checklist" /></label>
          <label>Description <span className="muted">(optional)</span><textarea maxLength={255} rows={3} value={form.description} onChange={event => update("description", event.target.value)} placeholder="What needs to be done?" /></label>
          <div className="form-grid">
            <label>Duration (time units)<input type="number" required min="1" step="1" value={form.duration_estimate} onChange={event => update("duration_estimate", event.target.value)} /></label>
            <label>Priority<select value={form.priority} onChange={event => update("priority", event.target.value)}>{["low", "medium", "high"].map(value => <option value={value} key={value}>{value}</option>)}</select></label>
            <label>Status<select value={form.status} onChange={event => update("status", event.target.value)}>{["pending", "in_progress", "completed"].map(value => <option value={value} key={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
          </div>
          {tasks.length > 0 && <fieldset className="choice-group"><legend>Prerequisites <span className="muted">(optional)</span></legend><p className="helper">This task starts after all selected tasks finish.</p><div className="prerequisite-list">{tasks.map(task => <label key={task.id}><input type="checkbox" checked={form.depends_on_task_ids.includes(task.id)} onChange={event => update("depends_on_task_ids", event.target.checked ? [...form.depends_on_task_ids, task.id] : form.depends_on_task_ids.filter(id => id !== task.id))} />{task.title}</label>)}</div></fieldset>}
          {resources.length > 0 && <fieldset className="choice-group"><legend>Resource requirements <span className="muted">(optional)</span></legend><p className="helper">Set required units. Leave at 0 for resources this task does not need.</p><div className="resource-inputs">{resources.map(resource => <label key={resource.id}>{resource.name}<input type="number" min="0" step="1" required value={form.resource_requirements[resource.id] ?? 0} onChange={event => update("resource_requirements", { ...form.resource_requirements, [resource.id]: event.target.value === "" ? "" : Number(event.target.value) })} /></label>)}</div></fieldset>}
        </fieldset> : <div className="delete-explanation"><p>This permanently deletes <strong>{modal.task.title}</strong> and its dependency links and resource assignments.</p><p>Other tasks remain. Tasks that depend on it may start earlier.</p></div>}
        <div className="dialog-actions"><button type="button" disabled={saving} onClick={() => setModal(null)}>Cancel</button><button className={modal.type === "add" ? "primary" : "danger"} disabled={saving} type="submit">{saving && <LoaderCircle className="spin" size={14} />}{saving ? "Saving…" : modal.type === "add" ? "Create task" : "Delete task"}</button></div>
      </form>}
    </dialog>
  </section>;
}
