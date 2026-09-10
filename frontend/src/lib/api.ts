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

export interface GPUTelemetryData {
  temperature: number;
  utilization: number;
  memory_used: number;
  memory_total: number;
  power_draw: number;
  power_limit: number;
  fan_speed: number;
  clocks_graphics: number;
  clocks_memory: number;
  memory_utilization: number;
}

export interface SystemMetricsData {
  cpu_util: number;
  mem_used_gb: number;
  mem_total_gb: number;
  mem_percent: number;
  disk_used_gb: number;
  disk_total_gb: number;
  disk_percent: number;
}

export interface TelemetryData {
  gpu: GPUTelemetryData;
  system: SystemMetricsData;
  timestamp: number;
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

export interface MemorySummary {
  sensory_count?: number;
  working_count?: number;
  long_term_count?: number;
  procedural_count?: number;
  novelty_count?: number;
  hemisphere_balance?: { left?: number; right?: number };
  transfer_count?: number;
}

export interface MemorySystemStats {
  working_count?: number;
  working_novel?: number;
  long_term_count?: number;
  long_term_novel?: number;
  procedural_count?: number;
  procedural_novel?: number;
  transfers?: number;
  // Backend returns an object; keep string as a legacy fallback.
  summary?: MemorySummary | string;
  error?: string;
}

export interface ArchiveSession {
  id: string;
  title: string;
  model: string;
  created_at: string;
  archived_at: string;
}

export interface ArchiveMessage {
  id: string;
  role: string;
  content: string;
  timestamp: string;
}

export interface SchemaEvolution {
  current_version: number;
  migrations: string[];
  last_applied: string;
}

export interface VisionStatus {
  available: boolean;
  model: string;
  max_image_size_mb: number;
}

export interface SessionState {
  session_id: string;
  state: Record<string, unknown>;
  version: number;
  updated_at: string;
}

// ─── API Client ──────────────────────────────────────────────────────────────

class ApiClient {
  private baseUrl: string;
  private cache = new Map<string, { data: unknown; timestamp: number }>();
  private cacheTtl = 5000; // 5s cache for list endpoints

  constructor(baseUrl: string = "") {
    // Defer window access so this class is safe to import during SSR / prerender.
    this.baseUrl = baseUrl || (typeof window !== "undefined" ? window.location.origin : "");
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const method = (options?.method || "GET").toUpperCase();

    // Backend restarts (e.g. after `git pull`) leave a brief window where
    // Next.js's /api proxy returns 500 ECONNREFUSED. Without a retry the
    // user sees a red toast on the very next click after a restart, even
    // though the backend comes back within a second or two. Retry a small
    // number of times with exponential backoff on transient failures.
    //
    // Only retried:
    //   * network errors thrown by fetch itself (backend not listening),
    //   * 502 / 503 / 504 (proxy layer says upstream is down),
    //   * 500 ONLY for idempotent methods (GET / HEAD / OPTIONS) or when
    //     the caller explicitly opts in via an X-Retry-500 header.
    // Never retried:
    //   * 4xx (client error — will keep failing),
    //   * 500 on POST/PATCH/DELETE by default (may have side-effected),
    //   * caller-issued AbortController signal.
    //
    // POST /api/sessions is explicitly whitelisted because it is
    // idempotent-enough in practice (worst case: an orphan empty session
    // no user ever prompted) and it is the request most likely to hit the
    // restart gap.
    const isIdempotent =
      method === "GET" || method === "HEAD" || method === "OPTIONS";
    const optIn500Retry =
      (options?.headers as Record<string, string> | undefined)?.[
        "X-Retry-500"
      ] === "1" ||
      (method === "POST" && endpoint === "/api/sessions");

    const maxAttempts = 3;
    const baseDelayMs = 250;
    let lastErr: Error = new Error("API request failed");

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      let response: Response | null = null;
      let fetchErr: unknown = null;
      try {
        response = await fetch(url, {
          headers: { "Content-Type": "application/json", ...options?.headers },
          ...options,
        });
      } catch (err) {
        fetchErr = err;
      }

      // Success path.
      if (response && response.ok) {
        return response.json();
      }

      // fetch() itself threw — network-level failure (backend not
      // listening, DNS, connection reset). The request never reached the
      // server, so retrying is safe on any method.
      if (fetchErr) {
        lastErr =
          fetchErr instanceof Error
            ? fetchErr
            : new Error(String(fetchErr));
        if (attempt >= maxAttempts) throw lastErr;
        await new Promise((r) => setTimeout(r, baseDelayMs * 2 ** (attempt - 1)));
        continue;
      }

      // HTTP error response. Decide whether to retry based on status +
      // method safety.
      const status = response!.status;
      lastErr = new Error(`API Error ${status}: ${response!.statusText}`);

      const retryableStatus =
        status === 502 ||
        status === 503 ||
        status === 504 ||
        (status === 500 && (isIdempotent || optIn500Retry));

      if (!retryableStatus || attempt >= maxAttempts) {
        throw lastErr;
      }

      await new Promise((r) => setTimeout(r, baseDelayMs * 2 ** (attempt - 1)));
    }

    throw lastErr;
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
    return this.request("/api/health");
  }

  // Routing
  async getModels(): Promise<ModelProfile[]> {
    return this.request("/api/models");
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

  // Plugins
  async getPlugins(): Promise<PluginInfo[]> {
    const data = await this.request<any>("/api/plugins");
    const raw = Array.isArray(data) ? data : Array.isArray(data?.plugins) ? data.plugins : [];
    return raw.map((p: any) => ({
      name: p?.name ?? "unknown",
      enabled: p?.enabled ?? true,
      version: p?.version ?? "",
      description: p?.description ?? "",
    }));
  }

  async togglePlugin(name: string, enabled: boolean): Promise<void> {
    await this.request(`/api/plugins/${encodeURIComponent(name)}/toggle`, {
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
    const data = await this.request<any>("/api/hooks");
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.hooks)) return data.hooks;
    return [];
  }

  /**
   * Manually fire an event through the hook manager.
   * Backend endpoint is POST /api/hooks/fire with `{event_type, ...}` body.
   */
  async triggerHook(eventType: string, extra: Record<string, unknown> = {}): Promise<any> {
    return this.request(`/api/hooks/fire`, {
      method: "POST",
      body: JSON.stringify({ event_type: eventType, ...extra }),
    });
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

  // Archive
  async getArchiveSessions(): Promise<ArchiveSession[]> {
    return this.request("/api/archive/sessions");
  }

  async getArchiveSession(id: string): Promise<ArchiveSession> {
    return this.request(`/api/archive/sessions/${id}`);
  }

  async getArchiveMessages(id: string): Promise<ArchiveMessage[]> {
    return this.request(`/api/archive/sessions/${id}/messages`);
  }

  async renameArchiveSession(id: string, title: string): Promise<void> {
    await this.request(`/api/archive/sessions/${id}/rename`, {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  }

  async tagArchiveSession(id: string, tag: string): Promise<void> {
    await this.request(`/api/archive/sessions/${id}/tag`, {
      method: "POST",
      body: JSON.stringify({ tag }),
    });
  }

  // Session State
  async getSessionState(id: string): Promise<SessionState> {
    return this.request(`/api/state/${id}`);
  }

  async saveSessionState(id: string, state: Record<string, unknown>): Promise<void> {
    await this.request(`/api/state/${id}/save`, {
      method: "POST",
      body: JSON.stringify({ state }),
    });
  }

  async createSessionSnapshot(id: string): Promise<void> {
    await this.request(`/api/state/${id}/snapshot`, {
      method: "POST",
    });
  }

  // Vision
  async getVisionStatus(): Promise<VisionStatus> {
    return this.request("/api/vision/status");
  }

  async analyzeImage(file: File): Promise<any> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("/api/vision/analyze", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`Vision analyze error: ${response.statusText}`);
    }
    return response.json();
  }

  async analyzeImageUrl(url: string): Promise<any> {
    return this.request("/api/vision/analyze-url", {
      method: "POST",
      body: JSON.stringify({ url }),
    });
  }

  // Session interruption & model switching
  async interruptSession(id: string): Promise<void> {
    await this.request(`/api/sessions/${id}/interrupt`, {
      method: "POST",
    });
  }

  async changeSessionModel(id: string, model: string): Promise<void> {
    await this.request(`/api/sessions/${id}/model`, {
      method: "POST",
      body: JSON.stringify({ model }),
    });
  }

  async getSessionReplay(id: string): Promise<SessionEvent[]> {
    const data = await this.request<{ events?: SessionEvent[] }>(`/api/sessions/${id}/replay`);
    return data.events || [];
  }

  // Schema evolution
  async getSchema(): Promise<SchemaEvolution> {
    return this.request("/api/schema");
  }

  // Models (direct)
  async getModelsDirect(): Promise<ModelProfile[]> {
    return this.request("/api/models");
  }
}

export const api = new ApiClient();
