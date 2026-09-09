/**
 * Tektos-Ultima — Ops Panel
 *
 * Compact grid of operator utilities that don't warrant their own panel:
 *   - Delegate a subtask to a subagent
 *   - Memory: run decay pass, delete an entry by tier/id
 *   - Re-probe the LLM endpoint
 *   - Fire an arbitrary hook
 *   - Analyze an image URL via vision
 */

"use client";

import { useState } from "react";
import { useStore } from "@nanostores/react";
import { $sessionId } from "@/lib/stores/session";

interface Result {
  ok: boolean;
  message: string;
}

async function postJson(url: string, body: unknown): Promise<Result> {
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) return { ok: false, message: data.detail || data.error || res.statusText };
    return { ok: true, message: JSON.stringify(data).slice(0, 240) };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : String(err) };
  }
}

async function del(url: string): Promise<Result> {
  try {
    const res = await fetch(url, { method: "DELETE" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, message: data.detail || data.error || res.statusText };
    return { ok: true, message: JSON.stringify(data).slice(0, 240) };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : String(err) };
  }
}

function OpCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="panel-card space-y-2">
      <div className="text-sm font-medium text-text-primary">{title}</div>
      {children}
    </div>
  );
}

function ResultLine({ result }: { result: Result | null }) {
  if (!result) return null;
  return (
    <div className={`text-11 font-mono truncate ${result.ok ? "text-status-success" : "text-status-error"}`}>
      {result.ok ? "\u2713 " : "\u2717 "}
      {result.message}
    </div>
  );
}

export function OpsPanel() {
  const sessionId = useStore($sessionId);

  // Delegate
  const [goal, setGoal] = useState("");
  const [context, setContext] = useState("");
  const [delegateResult, setDelegateResult] = useState<Result | null>(null);
  const runDelegate = async () => {
    if (!goal.trim()) return;
    setDelegateResult(null);
    setDelegateResult(
      await postJson("/api/delegate", {
        session_id: sessionId || "ops-panel",
        goal,
        context: context || null,
      }),
    );
  };

  // Memory
  const [decayResult, setDecayResult] = useState<Result | null>(null);
  const [memTier, setMemTier] = useState<"episodic" | "long_term" | "procedural">("episodic");
  const [memId, setMemId] = useState("");
  const [memDeleteResult, setMemDeleteResult] = useState<Result | null>(null);

  // LLM probe
  const [probeResult, setProbeResult] = useState<Result | null>(null);

  // Hooks
  const [hookName, setHookName] = useState("");
  const [hookPayload, setHookPayload] = useState("{}");
  const [hookResult, setHookResult] = useState<Result | null>(null);
  const runHook = async () => {
    if (!hookName.trim()) return;
    let payload: unknown = {};
    try {
      payload = JSON.parse(hookPayload || "{}");
    } catch {
      setHookResult({ ok: false, message: "payload is not valid JSON" });
      return;
    }
    setHookResult(await postJson("/api/hooks/fire", { hook: hookName, payload }));
  };

  // Vision URL
  const [imageUrl, setImageUrl] = useState("");
  const [visionPrompt, setVisionPrompt] = useState("");
  const [visionResult, setVisionResult] = useState<Result | null>(null);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <OpCard title="Delegate subtask">
        <input
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Goal"
          className="w-full bg-bg-3 border border-border rounded px-2 py-1 text-xs"
        />
        <textarea
          value={context}
          onChange={(e) => setContext(e.target.value)}
          placeholder="Context (optional)"
          className="w-full h-20 bg-bg-3 border border-border rounded px-2 py-1 text-xs"
        />
        <button
          onClick={runDelegate}
          disabled={!goal.trim()}
          className="rounded bg-accent px-3 py-1 text-xs font-medium text-black disabled:opacity-40"
        >
          Delegate
        </button>
        <ResultLine result={delegateResult} />
      </OpCard>

      <OpCard title="Memory">
        <div className="flex gap-2">
          <button
            onClick={async () => setDecayResult(await postJson("/api/memory/decay", {}))}
            className="rounded border border-border px-3 py-1 text-xs text-text-primary hover:bg-bg-3"
          >
            Run decay
          </button>
          <ResultLine result={decayResult} />
        </div>
        <div className="flex gap-2 items-center">
          <select
            value={memTier}
            onChange={(e) => setMemTier(e.target.value as typeof memTier)}
            className="bg-bg-3 border border-border rounded px-2 py-1 text-xs"
          >
            <option value="episodic">episodic</option>
            <option value="long_term">long_term</option>
            <option value="procedural">procedural</option>
          </select>
          <input
            value={memId}
            onChange={(e) => setMemId(e.target.value)}
            placeholder="entry id"
            className="flex-1 bg-bg-3 border border-border rounded px-2 py-1 text-xs"
          />
          <button
            onClick={async () => {
              if (!memId.trim()) return;
              setMemDeleteResult(await del(`/api/memory/${memTier}/${encodeURIComponent(memId)}`));
            }}
            disabled={!memId.trim()}
            className="rounded border border-border px-3 py-1 text-xs text-text-primary hover:bg-bg-3 disabled:opacity-40"
          >
            Delete
          </button>
        </div>
        <ResultLine result={memDeleteResult} />
      </OpCard>

      <OpCard title="LLM probe">
        <button
          onClick={async () => setProbeResult(await postJson("/api/llm/probe", {}))}
          className="rounded border border-border px-3 py-1 text-xs text-text-primary hover:bg-bg-3"
        >
          Re-probe LLM endpoint
        </button>
        <ResultLine result={probeResult} />
      </OpCard>

      <OpCard title="Fire hook">
        <input
          value={hookName}
          onChange={(e) => setHookName(e.target.value)}
          placeholder="hook name (e.g. session.started)"
          className="w-full bg-bg-3 border border-border rounded px-2 py-1 text-xs"
        />
        <textarea
          value={hookPayload}
          onChange={(e) => setHookPayload(e.target.value)}
          className="w-full h-20 bg-bg-3 border border-border rounded px-2 py-1 text-xs font-mono"
        />
        <button
          onClick={runHook}
          disabled={!hookName.trim()}
          className="rounded bg-accent px-3 py-1 text-xs font-medium text-black disabled:opacity-40"
        >
          Fire
        </button>
        <ResultLine result={hookResult} />
      </OpCard>

      <OpCard title="Vision — analyze image URL">
        <input
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          placeholder="https://…image.png"
          className="w-full bg-bg-3 border border-border rounded px-2 py-1 text-xs"
        />
        <input
          value={visionPrompt}
          onChange={(e) => setVisionPrompt(e.target.value)}
          placeholder="Prompt (optional)"
          className="w-full bg-bg-3 border border-border rounded px-2 py-1 text-xs"
        />
        <button
          onClick={async () => {
            if (!imageUrl.trim()) return;
            setVisionResult(
              await postJson("/api/vision/analyze-url", {
                url: imageUrl,
                prompt: visionPrompt || null,
              }),
            );
          }}
          disabled={!imageUrl.trim()}
          className="rounded bg-accent px-3 py-1 text-xs font-medium text-black disabled:opacity-40"
        >
          Analyze
        </button>
        <ResultLine result={visionResult} />
      </OpCard>
    </div>
  );
}
