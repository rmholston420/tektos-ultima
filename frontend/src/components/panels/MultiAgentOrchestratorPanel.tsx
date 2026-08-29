/**
 * Tektos-Ultima v1 — Multi-Agent Orchestrator Panel
 *
 * Dashboard for the multi-agent orchestrator:
 * - Agent roles and capabilities
 * - Task queue and execution status
 * - Parallel execution stats
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface OrchestratorStatus {
  status: string;
  hierarchical_agent: boolean;
  long_running_agent: boolean;
  coding_executor: boolean;
  error?: string;
}

interface AgentInfo {
  role: string;
  capabilities: string[];
  status: string;
}

export function MultiAgentOrchestratorPanel() {
  const [status, setStatus] = useState<OrchestratorStatus | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, agentsRes] = await Promise.all([
        fetch("/api/multi-agent-orchestrator/status"),
        fetch("/api/multi-agent-orchestrator/agents"),
      ]);
      if (!statusRes.ok) throw new Error(`HTTP ${statusRes.status}`);
      const statusData = await statusRes.json();
      setStatus(statusData);
      if (agentsRes.ok) {
        const agentsData = await agentsRes.json();
        setAgents(Array.isArray(agentsData) ? agentsData : []);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Loading orchestrator status...</div>
      </div>
    );
  }

  const statusColor = status?.status === "initialized" ? "text-green-400" : "text-red-400";

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">🤖</span>
          <h2 className="text-sm font-semibold text-text-primary">Multi-Agent Orchestrator</h2>
          <span className="text-xs text-text-muted">Parallel Agent Coordination</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${status?.status === "initialized" ? "bg-green-400" : "bg-red-400"}`} />
          <span className={`text-xs font-mono ${statusColor}`}>{status?.status}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Agent Roles */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Agent Roles</h3>
          <div className="space-y-2">
            {status && (
              <>
                {status.hierarchical_agent && (
                  <div className="flex items-center justify-between bg-bg-3 rounded-md p-2">
                    <span className="text-xs font-medium text-text-primary">Hierarchical Agent</span>
                    <span className="text-xs text-green-400">Active</span>
                  </div>
                )}
                {status.long_running_agent && (
                  <div className="flex items-center justify-between bg-bg-3 rounded-md p-2">
                    <span className="text-xs font-medium text-text-primary">Long-Running Agent</span>
                    <span className="text-xs text-green-400">Active</span>
                  </div>
                )}
                {status.coding_executor && (
                  <div className="flex items-center justify-between bg-bg-3 rounded-md p-2">
                    <span className="text-xs font-medium text-text-primary">Coding Executor</span>
                    <span className="text-xs text-green-400">Active</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Agent List */}
        {agents.length > 0 && (
          <div className="bg-surface rounded-lg p-3 border border-border">
            <h3 className="text-xs font-semibold text-text-muted mb-3">Agents ({agents.length})</h3>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {agents.map((agent, i) => (
                <div key={i} className="bg-bg-3 rounded-md p-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-accent">{agent.role}</span>
                    <span className="text-xs text-green-400 capitalize">{agent.status}</span>
                  </div>
                  {agent.capabilities.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {agent.capabilities.slice(0, 4).map((cap, j) => (
                        <span key={j} className="text-xs bg-surface text-text-muted px-1.5 py-0.5 rounded">
                          {cap}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-400/10 border border-red-400/30 rounded-lg p-3">
            <span className="text-xs text-red-400">{error}</span>
          </div>
        )}
      </div>
    </div>
  );
}
