/**
 * Tektos-Ultima v1 — Schema Evolution Panel
 *
 * Self-improvement interface: introspect schema, detect patterns,
 * propose and apply schema changes.
 */

import { useState, useEffect, useCallback } from "react";

interface SchemaTable {
  name: string;
  columns: { cid: number; name: string; type: string; notnull: boolean; pk: boolean }[];
  indexes: string[];
  row_count: number;
}

interface SchemaData {
  version: number;
  tables: Record<string, SchemaTable>;
}

interface Pattern {
  field: string;
  table: string;
  percentage: number;
  confidence: number;
  suggested_type: string;
  pattern_type: string;
  example_values: unknown[];
}

interface Proposal {
  reason: string;
  proposed_sql: string;
  valid: boolean;
  errors: string[];
}

export function SchemaEvolutionPanel() {
  const [schema, setSchema] = useState<SchemaData | null>(null);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [selectedTable, setSelectedTable] = useState("sessions");
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);

  const fetchSchema = useCallback(async () => {
    try {
      const res = await fetch("/api/schema");
      const data = await res.json();
      setSchema(data.schema || null);
    } catch (err) {
      console.error("Failed to load schema:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchPatterns = useCallback(async () => {
    try {
      const res = await fetch(`/api/schema/patterns?table=${selectedTable}`);
      const data = await res.json();
      setPatterns(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to load patterns:", err);
    }
  }, [selectedTable]);

  useEffect(() => {
    fetchSchema();
    fetchPatterns();
  }, [fetchSchema, fetchPatterns]);

  const proposeChange = useCallback(async () => {
    if (!patterns.length) return;
    const p = patterns[0];
    try {
      const res = await fetch("/api/schema/propose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          table: p.table,
          field_name: p.field,
          percentage: p.percentage,
          confidence: p.confidence,
          suggested_type: p.suggested_type,
          example_values: p.example_values,
        }),
      });
      const data = await res.json();
      setProposal(data);
    } catch (err) {
      console.error("Proposal failed:", err);
    }
  }, [patterns]);

  const applyChange = useCallback(async () => {
    if (!proposal) return;
    setApplying(true);
    try {
      const res = await fetch("/api/schema/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason: proposal.reason,
          action: "add_column",
          table: proposal.proposed_sql.match(/ALTER TABLE (\w+)/)?.[1] || "",
          column: proposal.proposed_sql.match(/ADD COLUMN (\w+)/)?.[1] || "",
          column_type: proposal.proposed_sql.match(/ADD COLUMN \w+ (\w+)/)?.[1] || "TEXT",
          proposed_sql: proposal.proposed_sql,
        }),
      });
      const data = await res.json();
      setMessage({
        type: data.success ? "success" : "error",
        text: data.success ? `Applied! Schema now at v${data.version}` : `Failed: ${data.errors?.join(", ")}`,
      });
      if (data.success) {
        fetchSchema();
        fetchPatterns();
        setProposal(null);
      }
    } catch (err) {
      setMessage({ type: "error", text: `Apply failed: ${err}` });
    } finally {
      setApplying(false);
    }
  }, [proposal, fetchSchema, fetchPatterns]);

  if (loading && !schema) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading schema...</div>
      </div>
    );
  }

  const tables = schema?.tables || {};
  const tableNames = Object.keys(tables);
  const totalRows = Object.values(tables).reduce((s, t) => s + t.row_count, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border border-slate-700 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">Schema Evolution Engine</h2>
            <p className="text-xs text-slate-400">
              Version: <span className="text-accent font-mono">v{schema?.version || 0}</span> · {tableNames.length} tables · {totalRows.toLocaleString()} rows
            </p>
          </div>
          <button
            onClick={() => { fetchSchema(); fetchPatterns(); setMessage(null); }}
            className="px-3 py-1.5 text-xs bg-slate-700 hover:bg-slate-600 rounded-md text-slate-200 transition-colors"
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Table Selector */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Analyze Table</h3>
        <select
          value={selectedTable}
          onChange={(e) => setSelectedTable(e.target.value)}
          className="w-full bg-slate-800 border border-slate-600 rounded-md px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-accent"
        >
          {tableNames.map((name) => (
            <option key={name} value={name}>
              {name} ({tables[name]?.row_count || 0} rows, {tables[name]?.columns.length || 0} columns)
            </option>
          ))}
        </select>
        <button
          onClick={fetchPatterns}
          className="mt-2 w-full px-3 py-2 text-sm bg-accent/20 hover:bg-accent/30 text-accent rounded-md transition-colors"
        >
          🔍 Detect Patterns
        </button>
      </div>

      {/* Detected Patterns */}
      {patterns.length > 0 && (
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-3">
            Detected Patterns ({patterns.length})
          </h3>
          <div className="space-y-3">
            {patterns.map((p, i) => (
              <div key={i} className="p-3 bg-slate-800/50 rounded-md border border-slate-700">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-mono text-slate-200">{p.field}</span>
                  <span className={`text-xs ${p.confidence >= 0.8 ? "text-green-400" : p.confidence >= 0.6 ? "text-amber-400" : "text-slate-400"}`}>
                    {(p.confidence * 100).toFixed(0)}% confident
                  </span>
                </div>
                <div className="text-xs text-slate-400 mb-2">
                  Appears in {Math.round(p.percentage * 100)}% of {p.table} · Suggested type: <span className="text-accent font-mono">{p.suggested_type}</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${p.confidence >= 0.8 ? "bg-green-400" : p.confidence >= 0.6 ? "bg-amber-400" : "bg-slate-400"}`}
                    style={{ width: `${p.confidence * 100}%` }}
                  />
                </div>
                {p.example_values.length > 0 && (
                  <div className="mt-2 text-xs text-slate-500">
                    Examples: {JSON.stringify(p.example_values.slice(0, 3))}
                  </div>
                )}
              </div>
            ))}
          </div>
          <button
            onClick={proposeChange}
            className="mt-3 w-full px-3 py-2 text-sm bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 rounded-md transition-colors"
          >
            💡 Propose Schema Change
          </button>
        </div>
      )}

      {/* Proposal */}
      {proposal && (
        <div className={`border rounded-lg p-4 ${proposal.valid ? "border-green-700 bg-green-900/10" : "border-red-700 bg-red-900/10"}`}>
          <h3 className="text-sm font-medium text-slate-200 mb-2">Schema Proposal</h3>
          <p className="text-xs text-slate-300 mb-2">{proposal.reason}</p>
          <pre className="text-xs font-mono bg-black/50 p-2 rounded mb-2 text-accent overflow-x-auto">
            {proposal.proposed_sql}
          </pre>
          {proposal.valid ? (
            <div className="text-xs text-green-400 mb-2">✓ Valid — ready to apply</div>
          ) : (
            <div className="text-xs text-red-400 mb-2">
              ✗ Invalid: {proposal.errors.join(", ")}
            </div>
          )}
          <button
            onClick={applyChange}
            disabled={!proposal.valid || applying}
            className={`w-full px-3 py-2 text-sm rounded-md transition-colors ${
              proposal.valid && !applying
                ? "bg-green-500/30 hover:bg-green-500/40 text-green-200"
                : "bg-slate-700 text-slate-500 cursor-not-allowed"
            }`}
          >
            {applying ? "⏳ Applying..." : "⚡ Apply Schema Change"}
          </button>
        </div>
      )}

      {/* Message */}
      {message && (
        <div className={`p-3 rounded-lg text-sm ${
          message.type === "success"
            ? "bg-green-900/30 border border-green-700 text-green-300"
            : "bg-red-900/30 border border-red-700 text-red-300"
        }`}>
          {message.text}
        </div>
      )}

      {/* Schema Tables */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Current Schema</h3>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {tableNames.map((tableName) => {
            const table = tables[tableName];
            return (
              <div key={tableName} className="p-3 bg-slate-800/50 rounded-md border border-slate-700">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-mono text-accent">{tableName}</span>
                  <span className="text-xs text-slate-400">{table.row_count} rows · {table.columns.length} columns</span>
                </div>
                <div className="grid grid-cols-2 gap-1 text-xs">
                  {table.columns.map((col) => (
                    <div key={col.name} className="flex items-center gap-2 p-1 rounded bg-black/30">
                      <span className="font-mono text-slate-200">{col.name}</span>
                      <span className="text-slate-500">{col.type || "TEXT"}</span>
                      {col.pk && <span className="text-amber-400 text-[10px]">PK</span>}
                      {col.notnull && <span className="text-red-400 text-[10px]">NN</span>}
                    </div>
                  ))}
                </div>
                {table.indexes.length > 0 && (
                  <div className="mt-1 text-xs text-slate-500">
                    Indexes: {table.indexes.join(", ")}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
