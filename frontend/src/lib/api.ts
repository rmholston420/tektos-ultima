/**
 * Tektos-Ultima v1 — Unified API Client
 *
 * Centralized HTTP client for all backend REST endpoints.
 * Provides typed responses, error handling, and request caching.
 *
 * Exemplar pattern: Single API layer with typed interfaces.
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export interface SessionSnapshot {
  id: string;
  title: string;
  model: string;
  cwd?: string;
  status: "created" | "ready" | "running" | "interrupted" | "failed";
  is_active: boolean;
  is_archived: boolean;
  is_failed: boolean;
  root_session_id?: string;
  tag?: string;
  created_at: string;
  updated_at: string;
  current_seq: number;
}

export interface SessionEvent {
  id: string;
  session_id: string;
  type: string;
  payload: Record<string, unknown>;
  seq: number;
  timestamp: string;
}

export interface TelemetryData {
  gpu_temp: number;
  gpu_util: number;
  cpu_temp: number;
  cpu_util: number;
  ram_used: number;
  ram_total: number;
  ram_util: number;
  disk_used: number;
  disk_total: number;
  fan_speed: number;
  power_draw: number;
  timestamp: string;
}

export interface ModelProfile {
  name: string;
  api_base: string;
  model_name: string;
  tier: "fast" | "balanced" | "power" | "expert";
  category: string;
  is_default: boolean;
  context_window: number;
  max_tokens: number;
}

export interface RoutingDecision {
  selected_model: string;
  tier: string;
  confidence: number;
  reason: string;
  fallback_model?: string;
}

export interface Axiom {
  id: string;
  category: string;
  status: "in_progress" | "verified" | "blocked";
  description: string;
  prerequisites: string[];
  verified_at?: string;
}

export interface RepographNode {
  filepath: string;
  language: string;
  classes: string[];
  functions: string[];
  imports: string[];
  dependencies: string[];
  pagerank: number;
}

export interface GitStatus {
  is_repo: boolean;
  branch: string;
  is_dirty: boolean;
  staged_files: string[];
  head_hash: string;
}

export interface LogEntry {
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR";
  logger: string;
  message: string;
  timestamp: string;
}

export interface PluginInfo {
  name: string;
  enabled: boolean;
  version: string;
  description: string;
}

export interface MemorySystemStats {
  sensory: { size: number; capacity: number };
  working: { size: number; capacity: number };
  longterm: { size: number; capacity: number };
  procedural: { size: number; capacity: number };
}

// ─── API Client ──────────────────────────────────────────────────────────────

class ApiClient {
  private baseUrl: string;
  private cache = new Map<string, { data: unknown; timestamp: number }>();
  private cacheTtl = 5000; // 5s cache for list endpoints

  constructor(baseUrl: string = "") {
    this.baseUrl = baseUrl || window.location.origin;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...options?.headers },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`API Error ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  // Sessions
  async getSessions(archived?: boolean): Promise<SessionSnapshot[]> {
    const params = archived ? "?archived=true" : "";
    return this.request(`/api/sessions${params}`);
  }

  async getSession(id: string): Promise<SessionSnapshot> {
    return this.request(`/api/sessions/${id}`);
  }

  async createSession(model?: string): Promise<SessionSnapshot> {
    return this.request("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ model }),
    });
  }

  async deleteSession(id: string): Promise<void> {
    await this.request(`/api/sessions/${id}`, { method: "DELETE" });
  }

  async renameSession(id: string, title: string): Promise<void> {
    await this.request(`/api/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
  }

  async tagSession(id: string, tag: string): Promise<void> {
    await this.request(`/api/sessions/${id}/tag`, {
      method: "POST",
      body: JSON.stringify({ tag }),
    });
  }

  async forkSession(id: string): Promise<SessionSnapshot> {
    return this.request(`/api/sessions/${id}/fork`, { method: "POST" });
  }

  async getSessionEvents(id: string): Promise<SessionEvent[]> {
    const data = await this.request<{ events?: SessionEvent[] }>(`/api/sessions/${id}/events`);
    return data.events || [];
  }

  // Telemetry
  async getHealth(): Promise<{ status: string; uptime: number }> {
    return this.request("/health");
  }

  // Routing
  async getModels(): Promise<ModelProfile[]> {
    return this.request("/api/routing/models");
  }

  async getRoutingDecision(task: string, complexity: number): Promise<RoutingDecision> {
    return this.request("/api/routing/decide", {
      method: "POST",
      body: JSON.stringify({ task, complexity }),
    });
  }

  // Axioms
  async getAxioms(): Promise<Axiom[]> {
    return this.request("/api/axioms");
  }

  async verifyAxiom(id: string): Promise<void> {
    await this.request(`/api/axioms/${id}/verify`, { method: "POST" });
  }

  // Repograph
  async getRepograph(): Promise<RepographNode[]> {
    return this.request("/api/repograph");
  }

  // Git
  async getGitStatus(): Promise<GitStatus> {
    return this.request("/api/git/status");
  }

  async getGitCommits(count: number = 10): Promise<any[]> {
    return this.request(`/api/git/commits?count=${count}`);
  }

  // Plugins
  async getPlugins(): Promise<PluginInfo[]> {
    return this.request("/api/plugins");
  }

  async togglePlugin(name: string, enabled: boolean): Promise<void> {
    await this.request(`/api/plugins/${name}/toggle`, {
      method: "POST",
      body: JSON.stringify({ enabled }),
    });
  }

  // Memory
  async getMemoryStats(): Promise<MemorySystemStats> {
    return this.request("/api/memory/stats");
  }

  // Logs
  async getLogs(level?: string, count: number = 100): Promise<LogEntry[]> {
    const params = new URLSearchParams();
    if (level) params.set("level", level);
    params.set("count", String(count));
    return this.request(`/api/logs?${params}`);
  }

  // Hooks
  async getHooks(): Promise<any[]> {
    return this.request("/api/hooks");
  }

  async triggerHook(name: string): Promise<any> {
    return this.request(`/api/hooks/${name}/trigger`, { method: "POST" });
  }

  // Config
  async getConfig(): Promise<any> {
    return this.request("/api/config");
  }

  async updateConfig(key: string, value: any): Promise<void> {
    await this.request("/api/config", {
      method: "PATCH",
      body: JSON.stringify({ key, value }),
    });
  }

  // Keys
  async getKeys(): Promise<any[]> {
    return this.request("/api/keys");
  }

  // Search
  async search(query: string, scope?: string): Promise<any[]> {
    const params = new URLSearchParams({ q: query });
    if (scope) params.set("scope", scope);
    return this.request(`/api/search?${params}`);
  }
}

export const api = new ApiClient();
