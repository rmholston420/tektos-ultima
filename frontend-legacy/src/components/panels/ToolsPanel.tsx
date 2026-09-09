/**
 * Tektos-Ultima v1 — Tools Panel
 *
 * Dynamic visualization of the ToolRegistry: all registered tools,
 * MCP status, and runtime tool management.
 */

import { useState, useEffect } from "react";

interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, any>;
  enabled: boolean;
  timeout: number;
  call_count: number;
  last_call: number;
}

interface ToolListResponse {
  error?: string;
  [key: string]: any;
}

export function ToolsPanel() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [mcpStatus, setMcpStatus] = useState<{ connected: boolean; url: string | null; imported_count: number } | null>(null);
  const [mcpUrl, setMcpUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [execResult, setExecResult] = useState<Record<string, string>>({});
  const [execTool, setExecTool] = useState("");
  const [execParams, setExecParams] = useState("{}");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [toolsRes, mcpRes] = await Promise.all([
          fetch("/api/tools"),
          fetch("/api/mcp/status"),
        ]);
        const toolsData = await toolsRes.json();
        setTools(Array.isArray(toolsData) ? toolsData : []);
        const mcpData = await mcpRes.json();
        setMcpStatus(mcpData as typeof mcpStatus);
      } catch (err) {
        console.error("Failed to load tools data:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleMcpConnect = async () => {
    if (!mcpUrl) return;
    try {
      const res = await fetch("/api/mcp/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: mcpUrl, transport: "http" }),
      });
      const data = await res.json();
      alert(`MCP: ${data.status} (${data.tools_imported || 0} tools)`);
      // Reload tools list
      const toolsRes = await fetch("/api/tools");
      setTools(await toolsRes.json());
      const mcpRes = await fetch("/api/mcp/status");
      setMcpStatus(await mcpRes.json());
    } catch (err) {
      alert(`MCP connect failed: ${err}`);
    }
  };

  const handleToggle = async (name: string, enabled: boolean) => {
    const endpoint = enabled ? `/api/tools/${name}/enable` : `/api/tools/${name}/disable`;
    await fetch(endpoint, { method: "POST" });
    // Reload tools
    const res = await fetch("/api/tools");
    setTools(await res.json());
  };

  const handleExecute = async () => {
    if (!execTool) return;
    let params: any = {};
    try {
      params = JSON.parse(execParams);
    } catch {
      alert("Invalid JSON parameters");
      return;
    }
    try {
      const res = await fetch(`/api/tools/${execTool}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      const data = await res.json();
      setExecResult((prev) => ({ ...prev, [execTool]: data.result }));
    } catch (err) {
      setExecResult((prev) => ({ ...prev, [execTool]: `Error: ${err}` }));
    }
  };

  if (loading && !tools.length) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading tools...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* MCP Connection */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">MCP Server Connection</h3>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={mcpUrl}
            onChange={(e) => setMcpUrl(e.target.value)}
            placeholder="http://localhost:3001/mcp"
            className="flex-1 bg-black/30 border border-slate-700 rounded px-3 py-2 text-sm text-white placeholder-slate-500"
          />
          <button
            onClick={handleMcpConnect}
            className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover"
          >
            Connect
          </button>
        </div>
        {mcpStatus && (
          <div className="flex items-center gap-3 text-sm">
            <span className={`w-2 h-2 rounded-full ${mcpStatus.connected ? "bg-green-400" : "bg-red-400"}`} />
            <span className="text-slate-400">
              {mcpStatus.connected ? `Connected to ${mcpStatus.url}` : "Not connected"}
            </span>
            {mcpStatus.imported_count > 0 && (
              <span className="text-amber-400">({mcpStatus.imported_count} tools imported)</span>
            )}
          </div>
        )}
      </div>

      {/* Tools List */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">
          Registered Tools ({tools.length})
        </h3>
        <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
          {tools.map((tool) => (
            <div key={tool.name} className="bg-black/30 border border-slate-700/50 rounded-lg p-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-accent">{tool.name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${tool.enabled ? "bg-green-400/20 text-green-400" : "bg-red-400/20 text-red-400"}`}>
                      {tool.enabled ? "enabled" : "disabled"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">{tool.description}</p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                    <span>Timeout: {tool.timeout}s</span>
                    <span>Calls: {tool.call_count}</span>
                    {tool.last_call > 0 && (
                      <span>Last: {new Date(tool.last_call * 1000).toLocaleTimeString()}</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleToggle(tool.name, !tool.enabled)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    tool.enabled
                      ? "bg-red-400/20 text-red-400 hover:bg-red-400/30"
                      : "bg-green-400/20 text-green-400 hover:bg-green-400/30"
                  }`}
                >
                  {tool.enabled ? "Disable" : "Enable"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Execute */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Quick Execute</h3>
        <div className="space-y-3">
          <select
            value={execTool}
            onChange={(e) => setExecTool(e.target.value)}
            className="w-full bg-black/30 border border-slate-700 rounded px-3 py-2 text-sm text-white"
          >
            <option value="">Select a tool...</option>
            {tools.filter((t) => t.enabled).map((t) => (
              <option key={t.name} value={t.name}>{t.name}</option>
            ))}
          </select>
          <textarea
            value={execParams}
            onChange={(e) => setExecParams(e.target.value)}
            placeholder='{"param": "value"}'
            className="w-full h-20 bg-black/30 border border-slate-700 rounded px-3 py-2 text-sm text-white font-mono placeholder-slate-500"
          />
          <button
            onClick={handleExecute}
            disabled={!execTool}
            className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50"
          >
            Execute
          </button>
        </div>
        {execResult[execTool] && (
          <div className="mt-3 bg-black/30 border border-slate-700 rounded p-3">
            <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">
              {execResult[execTool]}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
