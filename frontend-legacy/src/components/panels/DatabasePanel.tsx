/**
 * Tektos-Ultima v1 — Database Panel
 *
 * Full database management dashboard:
 * - Overview: table count, total size, row counts, backup status
 * - Schema explorer: tables with columns, types, indexes, row counts
 * - Table analysis: data quality, suggestions, missing indexes
 * - Sample data viewer: browse table contents
 * - Backup status: recent backups, last backup time
 *
 * Design: Overview cards + schema explorer with expandable tables + analysis tabs.
 */

import { useState, useEffect, useCallback } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ColumnInfo {
  name: string;
  type: string;
  notnull: boolean;
  pk: boolean;
  default: string | null;
}

interface IndexInfo {
  name: string;
  columns: string[];
  unique: boolean;
}

interface TableInfo {
  columns: ColumnInfo[];
  indexes: IndexInfo[];
  row_count: number;
  size_bytes: number;
}

interface SchemaData {
  tables: Record<string, TableInfo>;
}

interface TableAnalysis {
  table: string;
  row_count: number;
  column_stats: Record<string, Record<string, unknown>>;
  missing_indexes: string[];
  duplicate_indexes: string[];
  suggestions: string[];
  data_quality_issues: Array<{ column: string; issue: string; severity: string }>;
}

interface BackupInfo {
  path: string;
  timestamp: number;
  size_bytes: number;
  table_count: number;
  row_count: number;
  checksum: string;
}

interface DbStats {
  tables: number;
  total_rows: number;
  total_size_bytes: number;
  indexes: number;
  last_vacuum: string;
  journal_mode: string;
}

interface DatabaseState {
  stats: DbStats;
  schema: SchemaData;
  analyses: Record<string, TableAnalysis>;
  backups: BackupInfo[];
  selectedTable: string | null;
  sampleData: Record<string, unknown>[];
  loadingSample: boolean;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

const formatTime = (ts: number): string => {
  return new Date(ts * 1000).toLocaleString();
};

const severityColor = (severity: string): string => {
  switch (severity) {
    case "critical": return "text-red-400";
    case "warning": return "text-amber-400";
    case "info": return "text-blue-400";
    default: return "text-slate-400";
  }
};

// ─── Component ────────────────────────────────────────────────────────────────

export function DatabasePanel() {
  const [state, setState] = useState<DatabaseState | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [sampleData, setSampleData] = useState<Record<string, unknown>[]>([]);
  const [loadingSample, setLoadingSample] = useState(false);
  const [activeTab, setActiveTab] = useState<"schema" | "analysis" | "backups">("schema");

  const fetchDatabase = useCallback(async () => {
    try {
      const [statsRes, schemaRes, analyzeRes, backupsRes] = await Promise.all([
        fetch("/api/db"),
        fetch("/api/db/schema"),
        fetch("/api/db/analyze"),
        fetch("/api/db/backups"),
      ]);

      const stats = await statsRes.json();
      const schema = await schemaRes.json();
      const analyses = await analyzeRes.json();
      const backups = await backupsRes.json();

      setState({
        stats: stats || {},
        schema: schema || {},
        analyses: analyses || {},
        backups: Array.isArray(backups) ? backups : [],
        selectedTable: null,
        sampleData: [],
        loadingSample: false,
      });
    } catch (err) {
      console.error("Failed to load database:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDatabase();
    const interval = setInterval(fetchDatabase, 10000);
    return () => clearInterval(interval);
  }, [fetchDatabase]);

  const loadSampleData = useCallback(async (tableName: string) => {
    setLoadingSample(true);
    setSelectedTable(tableName);
    try {
      const res = await fetch(`/api/db/tables/${tableName}/sample?limit=50`);
      const data = await res.json();
      setSampleData(data.data || []);
    } catch (err) {
      console.error("Failed to load sample data:", err);
      setSampleData([]);
    } finally {
      setLoadingSample(false);
    }
  }, []);

  if (loading && !state) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading database...</div>
      </div>
    );
  }

  if (!state) return null;

  const { stats, schema, analyses, backups } = state;
  const tableNames = Object.keys(schema.tables || {});
  const selectedAnalysis = selectedTable ? analyses[selectedTable] : null;

  return (
    <div className="space-y-6">
      {/* ─── Overview Cards ────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <div className="text-2xl font-bold text-white">{stats.tables || 0}</div>
          <div className="text-xs text-slate-400">Tables</div>
        </div>
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <div className="text-2xl font-bold text-white">{(stats.total_rows || 0).toLocaleString()}</div>
          <div className="text-xs text-slate-400">Total Rows</div>
        </div>
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <div className="text-2xl font-bold text-white">{formatBytes(stats.total_size_bytes || 0)}</div>
          <div className="text-xs text-slate-400">Total Size</div>
        </div>
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <div className="text-2xl font-bold text-white">{stats.indexes || 0}</div>
          <div className="text-xs text-slate-400">Indexes</div>
        </div>
      </div>

      {/* ─── Schema / Analysis / Backups Tabs ──────────────────────────── */}
      <div className="bg-black/40 border border-slate-700 rounded-lg overflow-hidden">
        {/* Tab bar */}
        <div className="flex border-b border-slate-700">
          {[
            { key: "schema" as const, label: `Schema (${tableNames.length})` },
            { key: "analysis" as const, label: `Analysis (${tableNames.length})` },
            { key: "backups" as const, label: `Backups (${backups.length})` },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2.5 text-xs font-medium transition-all border-b-2 ${
                activeTab === tab.key
                  ? "border-accent text-accent bg-accent/5"
                  : "border-transparent text-slate-400 hover:text-slate-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="p-4">
          {activeTab === "schema" && (
            <div className="space-y-3">
              {tableNames.length === 0 ? (
                <div className="text-center py-8 text-slate-500">No tables found</div>
              ) : (
                tableNames.map((tableName) => {
                  const table = schema.tables[tableName];
                  return (
                    <div key={tableName} className="border border-slate-700 rounded-lg overflow-hidden">
                      {/* Table header */}
                      <div className="bg-black/30 px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-black/40 transition-colors"
                           onClick={() => loadSampleData(tableName)}>
                        <div className="flex items-center gap-3">
                          <span className="text-accent font-mono text-sm">{tableName}</span>
                          <span className="text-xs text-slate-500">{table.row_count.toLocaleString()} rows</span>
                          <span className="text-xs text-slate-500">{formatBytes(table.size_bytes)}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-500">{table.columns.length} cols</span>
                          <span className="text-xs text-slate-500">{table.indexes.length} idx</span>
                          <span className="text-xs text-accent">View →</span>
                        </div>
                      </div>

                      {/* Columns (expanded when selected) */}
                      {selectedTable === tableName && (
                        <div className="border-t border-slate-700">
                          {/* Sample data */}
                          {loadingSample ? (
                            <div className="p-4 text-center text-slate-500 text-sm">Loading sample data...</div>
                          ) : sampleData.length > 0 ? (
                            <div className="p-4">
                              <h4 className="text-xs font-medium text-slate-400 mb-2">Sample Data (50 rows)</h4>
                              <div className="overflow-x-auto">
                                <table className="w-full text-xs">
                                  <thead>
                                    <tr className="border-b border-slate-700">
                                      {Object.keys(sampleData[0] || {}).map((col) => (
                                        <th key={col} className="text-left px-3 py-2 text-slate-400 font-medium">{col}</th>
                                      ))}
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {sampleData.slice(0, 10).map((row, i) => (
                                      <tr key={i} className="border-b border-slate-800 hover:bg-black/20">
                                        {Object.values(row).map((val: unknown, j) => (
                                          <td key={j} className="px-3 py-2 text-slate-300 font-mono truncate max-w-[200px]">
                                            {val === null ? <span className="text-slate-600">NULL</span> : String(val)}
                                          </td>
                                        ))}
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                                {sampleData.length > 10 && (
                                  <div className="mt-2 text-xs text-slate-500 text-center">
                                    Showing 10 of {sampleData.length} rows
                                  </div>
                                )}
                              </div>
                            </div>
                          ) : null}

                          {/* Column list */}
                          <div className="px-4 py-3 border-t border-slate-700">
                            <h4 className="text-xs font-medium text-slate-400 mb-2">Columns</h4>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {table.columns.map((col) => (
                                <div key={col.name} className="flex items-center gap-2 text-xs">
                                  <span className={`font-mono ${col.pk ? "text-amber-400" : "text-slate-300"}`}>
                                    {col.name}
                                  </span>
                                  <span className="text-slate-500">{col.type}</span>
                                  {col.pk && <span className="text-amber-400 text-[10px]">PK</span>}
                                  {col.notnull && <span className="text-slate-600 text-[10px]">NOT NULL</span>}
                                </div>
                              ))}
                            </div>

                            {/* Indexes */}
                            {table.indexes.length > 0 && (
                              <div className="mt-3">
                                <h5 className="text-xs font-medium text-slate-500 mb-1">Indexes</h5>
                                <div className="flex flex-wrap gap-1">
                                  {table.indexes.map((idx) => (
                                    <span key={idx.name} className="text-xs bg-black/30 text-slate-400 px-2 py-0.5 rounded">
                                      {idx.name}
                                      {idx.unique && " (unique)"}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}

          {activeTab === "analysis" && (
            <div className="space-y-3">
              {tableNames.length === 0 ? (
                <div className="text-center py-8 text-slate-500">No tables to analyze</div>
              ) : (
                tableNames.map((tableName) => {
                  const analysis = analyses[tableName];
                  if (!analysis) return null;
                  return (
                    <div key={tableName} className="border border-slate-700 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-medium text-slate-300 font-mono">{tableName}</h4>
                        <span className="text-xs text-slate-500">{analysis.row_count.toLocaleString()} rows</span>
                      </div>

                      {/* Suggestions */}
                      {analysis.suggestions.length > 0 && (
                        <div className="mb-3">
                          <h5 className="text-xs font-medium text-amber-400 mb-1">Suggestions</h5>
                          <ul className="space-y-1">
                            {analysis.suggestions.map((s, i) => (
                              <li key={i} className="text-xs text-slate-400 flex items-start gap-2">
                                <span className="text-amber-400 mt-0.5">•</span>
                                {s}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Missing indexes */}
                      {analysis.missing_indexes.length > 0 && (
                        <div className="mb-3">
                          <h5 className="text-xs font-medium text-blue-400 mb-1">Missing Indexes</h5>
                          <div className="flex flex-wrap gap-1">
                            {analysis.missing_indexes.map((idx, i) => (
                              <span key={i} className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded">
                                {idx}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Data quality issues */}
                      {analysis.data_quality_issues.length > 0 && (
                        <div>
                          <h5 className="text-xs font-medium text-red-400 mb-1">Data Quality Issues</h5>
                          <div className="space-y-1">
                            {analysis.data_quality_issues.slice(0, 5).map((issue, i) => (
                              <div key={i} className="flex items-center gap-2 text-xs">
                                <span className={severityColor(issue.severity)}>●</span>
                                <span className="text-slate-400">{issue.column}</span>
                                <span className="text-slate-500">— {issue.issue}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {analysis.suggestions.length === 0 &&
                       analysis.missing_indexes.length === 0 &&
                       analysis.data_quality_issues.length === 0 && (
                        <div className="text-center py-4 text-green-400 text-sm">
                          ✓ Table looks healthy
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}

          {activeTab === "backups" && (
            <div className="space-y-3">
              {backups.length === 0 ? (
                <div className="text-center py-8 text-slate-500">No backups found</div>
              ) : (
                backups.map((backup, i) => (
                  <div key={i} className="border border-slate-700 rounded-lg p-4 flex items-center justify-between">
                    <div>
                      <div className="text-sm font-mono text-slate-300 truncate max-w-[300px]">
                        {backup.path.split("/").pop()}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {formatTime(backup.timestamp)} · {formatBytes(backup.size_bytes)} · {backup.table_count} tables · {backup.row_count.toLocaleString()} rows
                      </div>
                    </div>
                    <div className="text-xs text-slate-600 font-mono">
                      {backup.checksum.slice(0, 16)}...
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* ─── Database Info ─────────────────────────────────────────────── */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Database Configuration</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-xs text-slate-500">Journal Mode</span>
            <div className="text-slate-300 font-mono">{stats.journal_mode || "WAL"}</div>
          </div>
          <div>
            <span className="text-xs text-slate-500">Last Vacuum</span>
            <div className="text-slate-300 font-mono">{stats.last_vacuum || "Never"}</div>
          </div>
          <div>
            <span className="text-xs text-slate-500">SQLite Version</span>
            <div className="text-slate-300 font-mono">3.x</div>
          </div>
          <div>
            <span className="text-xs text-slate-500">Auto-vacuum</span>
            <div className="text-slate-300 font-mono">Incremental</div>
          </div>
        </div>
      </div>
    </div>
  );
}
