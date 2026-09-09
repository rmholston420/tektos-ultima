/**
 * Tektos-Ultima v1 — Scheduling Panel
 *
 * Session scheduling with:
 * - One-shot scheduled prompts
 * - Recurring cron-like schedules
 * - Session timer management
 * - Scheduled task list with status
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

// ─── Types ───────────────────────────────────────────────────────────────────

type ScheduleType = "once" | "recurring";
type ScheduleStatus = "pending" | "active" | "completed" | "failed" | "paused";

interface ScheduledTask {
  id: string;
  title: string;
  message: string;
  type: ScheduleType;
  cron?: string;
  timezone: string;
  status: ScheduleStatus;
  nextRun?: string;
  lastRun?: string;
  runsCompleted: number;
  createdAt: string;
}

// ─── Schedule Templates ──────────────────────────────────────────────────────

const TIME_PRESETS = [
  { label: "In 5 minutes", value: 5 },
  { label: "In 15 minutes", value: 15 },
  { label: "In 1 hour", value: 60 },
  { label: "Tomorrow 9:00 AM", value: 1440 },
];

const RECURRING_PRESETS = [
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every 4 hours", value: "0 */4 * * *" },
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Daily at 9 AM", value: "0 9 * * *" },
  { label: "Daily at 6 PM", value: "0 18 * * *" },
  { label: "Weekdays 9-5", value: "0 9-17 * * 1-5" },
  { label: "Weekly Monday", value: "0 9 * * 1" },
  { label: "Monthly 1st", value: "0 9 1 * *" },
];

// ─── Main Component ──────────────────────────────────────────────────────────

export function SchedulingPanel() {
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTask, setNewTask] = useState<Partial<ScheduledTask>>({
    type: "once",
    timezone: "UTC",
    cron: "",
  });
  const [scheduleType, setScheduleType] = useState<ScheduleType>("once");
  const [timePreset, setTimePreset] = useState(0);
  const [recurringPreset, setRecurringPreset] = useState("");
  const [showSuccess, setShowSuccess] = useState(false);

  useEffect(() => {
    fetch("/api/schedule")
      .then((r) => r.json())
      .then((data) => {
        setTasks(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => {
        setTasks([]);
        setLoading(false);
      });
  }, []);

  const handleCreateTask = useCallback(() => {
    const task: ScheduledTask = {
      id: `task-${Date.now()}`,
      title: newTask.title || "Untitled Task",
      message: newTask.message || "No message",
      type: scheduleType,
      cron: scheduleType === "recurring" ? recurringPreset : undefined,
      timezone: newTask.timezone || "UTC",
      status: "pending",
      nextRun: scheduleType === "once"
        ? new Date(Date.now() + (timePreset + 1) * 60000).toISOString()
        : new Date(Date.now() + 60000).toISOString(),
      runsCompleted: 0,
      createdAt: new Date().toISOString(),
    };

    setTasks((prev) => [...prev, task]);
    setShowCreateForm(false);
    setShowSuccess(true);
    setTimeout(() => setShowSuccess(false), 3000);
  }, [newTask, scheduleType, timePreset, recurringPreset]);

  const handlePause = useCallback((taskId: string) => {
    setTasks((prev) =>
      prev.map((t) =>
        t.id === taskId
          ? {
              ...t,
              status: t.status === "paused" ? "active" : "paused",
            }
          : t
      )
    );
  }, []);

  const handleDelete = useCallback((taskId: string) => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId));
  }, []);

  const formatTime = (dateStr?: string) => {
    if (!dateStr) return "—";
    const date = new Date(dateStr);
    const now = new Date();
    const diff = date.getTime() - now.getTime();

    if (diff < 0) return "Overdue";
    if (diff < 60000) return "In 1 min";
    if (diff < 3600000) return `In ${Math.floor(diff / 60000)} min`;
    if (diff < 86400000) return `In ${Math.floor(diff / 3600000)}h ${Math.floor((diff % 3600000) / 60000)}m`;
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getStatusColor = (status: ScheduleStatus) => {
    switch (status) {
      case "active": return "text-status-success bg-status-success/10";
      case "pending": return "text-status-warning bg-status-warning/10";
      case "completed": return "text-text-muted bg-bg-3";
      case "failed": return "text-status-error bg-status-error/10";
      case "paused": return "text-text-muted bg-bg-3";
      default: return "text-text-muted bg-bg-3";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">Schedule Manager</h2>
          <p className="text-sm text-text-muted mt-1">
            Automate tasks with scheduled prompts and recurring sessions
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover transition-colors text-sm font-medium"
        >
          + New Schedule
        </button>
      </div>

      {/* Success notification */}
      {showSuccess && (
        <div className="p-3 bg-status-success/10 border border-status-success/20 rounded-lg text-sm text-status-success">
          ✓ Schedule created successfully
        </div>
      )}

      {/* Create Form Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-surface rounded-2xl p-6 w-full max-w-lg border border-border/50 shadow-2xl">
            <h3 className="text-lg font-semibold text-text-primary mb-4">Create New Schedule</h3>

            {/* Task title */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-text-muted mb-1.5">Task Title</label>
              <input
                type="text"
                value={newTask.title || ""}
                onChange={(e) => setNewTask((p) => ({ ...p, title: e.target.value }))}
                placeholder="e.g., Daily Backup"
                className="w-full px-3 py-2 bg-bg-2 border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-accent transition-colors"
              />
            </div>

            {/* Message */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-text-muted mb-1.5">Prompt Message</label>
              <textarea
                value={newTask.message || ""}
                onChange={(e) => setNewTask((p) => ({ ...p, message: e.target.value }))}
                placeholder="What should the AI do?"
                rows={2}
                className="w-full px-3 py-2 bg-bg-2 border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-accent transition-colors resize-none"
              />
            </div>

            {/* Schedule type */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-text-muted mb-1.5">Schedule Type</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setScheduleType("once")}
                  className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    scheduleType === "once"
                      ? "bg-accent text-white shadow-sm"
                      : "bg-bg-3 text-text-muted hover:text-text-primary hover:bg-bg-4"
                  }`}
                >
                  One-time
                </button>
                <button
                  onClick={() => setScheduleType("recurring")}
                  className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    scheduleType === "recurring"
                      ? "bg-accent text-white shadow-sm"
                      : "bg-bg-3 text-text-muted hover:text-text-primary hover:bg-bg-4"
                  }`}
                >
                  Recurring
                </button>
              </div>
            </div>

            {/* One-time presets */}
            {scheduleType === "once" && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-text-muted mb-1.5">When?</label>
                <div className="grid grid-cols-2 gap-2">
                  {TIME_PRESETS.map((preset, idx) => (
                    <button
                      key={preset.value}
                      onClick={() => setTimePreset(idx)}
                      className={`px-3 py-2 rounded-lg text-sm text-left transition-all ${
                        timePreset === idx
                          ? "bg-accent/10 text-accent border border-accent/20"
                          : "bg-bg-3 text-text-muted hover:text-text-primary hover:bg-bg-4"
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Recurring presets */}
            {scheduleType === "recurring" && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-text-muted mb-1.5">Frequency</label>
                <div className="grid grid-cols-2 gap-2">
                  {RECURRING_PRESETS.map((preset) => (
                    <button
                      key={preset.value}
                      onClick={() => setRecurringPreset(preset.value)}
                      className={`px-3 py-2 rounded-lg text-sm text-left transition-all ${
                        recurringPreset === preset.value
                          ? "bg-accent/10 text-accent border border-accent/20"
                          : "bg-bg-3 text-text-muted hover:text-text-primary hover:bg-bg-4"
                      }`}
                    >
                      {preset.label}
                      <div className="text-[10px] text-text-muted/60 mt-0.5 font-mono">{preset.value}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 mt-6">
              <button
                onClick={() => setShowCreateForm(false)}
                className="flex-1 px-4 py-2.5 bg-bg-3 text-text-secondary rounded-lg hover:bg-bg-4 transition-colors text-sm font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateTask}
                className="flex-1 px-4 py-2.5 bg-accent text-white rounded-lg hover:bg-accent-hover transition-colors text-sm font-medium"
              >
                Create Schedule
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Task list */}
      <div className="space-y-3">
        {tasks.map((task) => (
          <div
            key={task.id}
            className="p-4 bg-surface/80 rounded-xl border border-border/50 hover:border-accent/20 transition-all hover:shadow-lg hover:shadow-accent/5 group"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="text-sm font-medium text-text-primary truncate">{task.title}</h4>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider ${getStatusColor(task.status)}`}>
                    {task.status}
                  </span>
                </div>
                <p className="text-xs text-text-muted line-clamp-2">{task.message}</p>

                {/* Metadata */}
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-xs text-text-muted/70">
                    {task.type === "recurring" ? (
                      <>
                        <span className="font-mono text-accent/70">{task.cron}</span>
                        {task.timezone !== "UTC" && <span>· {task.timezone}</span>}
                      </>
                    ) : (
                      "One-time"
                    )}
                  </span>
                  <span className="text-xs text-text-muted/50">·</span>
                  <span className="text-xs text-text-muted/70">
                    Next: <span className="text-text-secondary">{formatTime(task.nextRun)}</span>
                  </span>
                  <span className="text-xs text-text-muted/50">·</span>
                  <span className="text-xs text-text-muted/70">
                    {task.runsCompleted} runs
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => handlePause(task.id)}
                  className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface-active rounded-md transition-colors"
                  title={task.status === "paused" ? "Resume" : "Pause"}
                >
                  {task.status === "paused" ? "▶" : "⏸"}
                </button>
                <button
                  onClick={() => handleDelete(task.id)}
                  className="p-1.5 text-text-muted hover:text-status-error hover:bg-status-error/10 rounded-md transition-colors"
                  title="Delete"
                >
                  ✕
                </button>
              </div>
            </div>
          </div>
        ))}

        {tasks.length === 0 && (
          <div className="text-center py-12 text-text-muted">
            <p className="text-sm">No scheduled tasks</p>
            <p className="text-xs mt-1">Create a schedule to automate your workflow</p>
          </div>
        )}
      </div>
    </div>
  );
}
