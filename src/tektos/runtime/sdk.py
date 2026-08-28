"""Runtime SDK bridge — connects llama.cpp to WebSocket protocol.

Key PlexClaw bug fixes applied:
- NO double-emit of assistant.completed (bug #2: only emit from ResultMessage)
- NO seq duplicates (bug #6: seq assigned inside push())
- NO double-emit of tool.completed (bug #3: guard with _completed_tools)
- NO import json in hot loop (bug #1: import at module top)
- NO dead "deleted" state (bug #1 corrected)
- Failed sessions removed, not left in _sessions (bug #8)

Uses httpx.AsyncClient for OpenAI-compatible llama.cpp API (:8081/v1).
"""

from __future__ import annotations

import asyncio as _asyncio
import inspect
import json as _json
import logging as _log
import os as _os
import time as _time
import uuid as _uuid
from dataclasses import dataclass
from typing import Any

import httpx

from tektos.protocol.envelope import (
    assistant_completed,
    assistant_delta,
    loop_safety_warning,
    session_failed,
    tool_completed,
    tool_permission_required,
    tool_started,
)
from tektos.providers.sandbox_provider import SandboxProvider
from tektos.runtime.loop_safety import (
    LoopSafetyConfig,
    LoopSafetyMonitor,
    LoopSafetyReport,
    LoopState,
    StopReason,
)
from tektos.runtime.session import LiveSession
from tektos.store.event_store import append_event
from tektos.metabolism import MetabolismEngine
from tektos.runtime.immune_system import (
    ImmuneContext,
    ImmuneSystem,
    ThreatSeverity,
    get_immune_system,
    reset_immune_system,
)

log = _log.getLogger("tektos.runtime")

# LLM endpoint configuration — configurable via environment
LLM_BASE_URL = _os.getenv("TEKTOS_LLM_BASE_URL", "http://127.0.0.1:8090/v1")
LLM_MODEL = "Qwen3.6-35B-A3B-Q4_K_M"

# Tool definitions for function calling
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read file content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                    "mode": {"type": "string", "description": "Write mode: 'write' or 'append'", "enum": ["write", "append"]}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_delete",
            "description": "Delete a file or directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory path to delete"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "directory_list",
            "description": "List directory contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "directory_create",
            "description": "Create directory (and parents)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search file contents (grep-like)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "path": {"type": "string", "description": "Path to search"},
                    "case_sensitive": {"type": "boolean", "description": "Case sensitive search", "default": False},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vision_analyze",
            "description": "Analyze an image using a vision LLM. Pass an image path or base64-encoded image data to get a text description. Useful for reading screenshots, diagrams, or any visual content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Path to the image file to analyze"},
                    "prompt": {"type": "string", "description": "What to look for in the image. Default: 'Describe what you see in this image in detail.'"},
                    "image_base64": {"type": "string", "description": "Base64-encoded image data (alternative to image_path). Use when you have image data inline."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information. Returns up to 5 results with titles, URLs, and descriptions. Use this to look up documentation, find download URLs, research how to solve a problem, or gather context before attempting a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query to look up on the web"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_extract",
            "description": "Extract content from web page URLs. Returns clean page content in markdown (no HTML). Also works with PDF URLs. Use this to read documentation, specifications, or any web page content after finding it via web_search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {"type": "array", "items": {"type": "string"}, "description": "List of URLs to extract content from (max 5 URLs per call)"}
                },
                "required": ["urls"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch a URL using curl and return the raw response. Use this to download files, fetch API responses, or retrieve content from any URL. Supports GET requests with optional headers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"},
                    "output_path": {"type": "string", "description": "Optional local file path to save the response to. If omitted, returns the content as text."},
                    "headers": {"type": "string", "description": "Optional curl headers as a string, e.g. 'User-Agent: Mozilla/5.0'"},
                    "max_bytes": {"type": "integer", "description": "Maximum bytes to return (default 100000). Use for large files."}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_query",
            "description": "Query the RAG (Retrieval-Augmented Generation) knowledge base. Search through indexed documents, past sessions, and stored knowledge to find relevant information. Use this to recall past work, find documentation, or retrieve context from the knowledge base before attempting a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query to look up in the knowledge base"},
                    "limit": {"type": "integer", "description": "Maximum number of results to return (default 5)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_task",
            "description": "Spawn a subagent in an isolated context to work on a subtask. The subagent runs independently and its final summary returns when complete. Use this for parallel workstreams or reasoning-heavy subtasks that would flood the main context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "What this subagent should accomplish. Be specific and self-contained."},
                    "context": {"type": "string", "description": "Background the subagent needs: file paths, error messages, constraints."},
                    "timeout": {"type": "integer", "description": "Maximum seconds to wait for completion (default 600)"}
                },
                "required": ["goal"]
            }
        }
    }
]


# ---------------------------------------------------------------------------
# Runtime SDK
# ---------------------------------------------------------------------------

@dataclass
class HookContext:
    """Context passed to hooks."""
    session_id: str
    model: str
    task_description: str
    outcome: str
    tool_name: str = ""
    tool_input: dict[str, Any] = None  # type: ignore
    tool_id: str = ""
    wall_time: float = 0.0


# Hook system — light initially, extensible later
class HookRegistry:
    def __init__(self) -> None:
        self._hooks: dict[str, list] = {}

    def register(self, event_type: str):
        def decorator(fn):
            self._hooks.setdefault(event_type, []).append(fn)
            return fn

        return decorator

    async def run(self, event_type: str, ctx: HookContext) -> None:
        """Run all hooks for an event. Errors are caught per-hook (PlexClaw bug #23 fix)."""
        for fn in self._hooks.get(event_type, []):
            try:
                if inspect.iscoroutinefunction(fn):
                    await fn(ctx)
                else:
                    fn(ctx)
            except Exception as exc:
                log.error("Hook %s raised on %s: %s", fn.__name__, event_type, exc)


hooks = HookRegistry()

# Global hook manager — set during lifespan initialization
_hook_manager = None


def _fire_hook(event_type: str, **kwargs) -> None:
    """Fire a hook through the global HookManager (set during lifespan).

    Errors are silently caught so hooks never break the main flow.
    """
    if _hook_manager is None:
        return
    try:
        _asyncio.create_task(_hook_manager.fire(event_type, **kwargs, stop_on_abort=False))  # type: ignore[union-attr]
    except Exception:
        log.exception("Hook fire failed for %s", event_type)


class RuntimeSDK:
    """Bridge between llama.cpp and WebSocket protocol.

    Each LiveSession owns exactly one RuntimeSDK instance plus one async lock
    so that only one active task runs per session at a time.
    """

    def __init__(
        self,
        llm_base_url: str = LLM_BASE_URL,
        llm_model: str = LLM_MODEL,
        loop_safety_config: LoopSafetyConfig | None = None,
        context_compactor: Any = None,
        # High-ROI modules — wired at startup
        rag_retriever: Any = None,
        context_curator: Any = None,
        planner_orchestrator: Any = None,
        hierarchical_agent: Any = None,
        multi_agent_orchestrator: Any = None,
        repo_map_generator: Any = None,
        tool_router: Any = None,
        task_decomposer: Any = None,
    ) -> None:
        self._llm_base_url = llm_base_url
        self._llm_model = llm_model
        self._client: httpx.AsyncClient | None = None
        self._lock = _asyncio.Lock()
        self._sandbox = SandboxProvider()
        self._loop_monitor = LoopSafetyMonitor(loop_safety_config or LoopSafetyConfig())
        # Metabolism engine for resource monitoring
        self._metabolism_engine = MetabolismEngine()
        # Context compactor (4-tier compression)
        self._context_compactor = context_compactor
        # Immune system — self-defending architecture
        self._immune_system: ImmuneSystem | None = None
        # High-ROI modules
        self._rag_retriever = rag_retriever
        self._context_curator = context_curator
        self._planner_orchestrator = planner_orchestrator
        self._hierarchical_agent = hierarchical_agent
        self._multi_agent_orchestrator = multi_agent_orchestrator
        self._repo_map_generator = repo_map_generator
        self._tool_router = tool_router
        self._task_decomposer = task_decomposer

    async def start(self) -> None:
        """Create the httpx client and start the immune system."""
        self._client = httpx.AsyncClient(
            base_url=self._llm_base_url,
            timeout=httpx.Timeout(30.0, read=300.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        # Validate connection
        try:
            resp = await self._client.get("/models")
            resp.raise_for_status()
            log.info(f"LLM endpoint connected: {self._llm_base_url}")
        except Exception as exc:
            log.warning(f"LLM endpoint not available at {self._llm_base_url}: {exc}")
            raise

        # Start the immune system
        self._immune_system = get_immune_system()
        await self._immune_system.start()
        log.info("[RuntimeSDK] Immune system started")

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def submit_prompt(
        self,
        session: LiveSession,
        prompt: str,
        system_prompt: str | None = None,
        on_event: Any = None,  # Callable[[WSEnvelope], Awaitable[None]]
        on_tool_approval: Any = None,  # Callable[[str, str], Awaitable[bool]]
    ) -> None:
        """Submit a prompt to the LLM. Streams events via on_event callback.

        Args:
            session: The LiveSession to run against.
            prompt: The user's prompt.
            system_prompt: Optional system prompt override.
            on_event: Callback for each normalized event.
            on_tool_approval: Callback for tool approval requests (manual mode).
        """
        if not self._client:
            raise RuntimeError("RuntimeSDK not started. Call start() first.")

        async with self._lock:
            session.status = "running"
            session.updated_at = _time.monotonic()

            start_time = _time.monotonic()

            # Fire session.start hook
            try:
                await _fire_hook("session.start", session_id=session.id, model=self._llm_model, task_description=prompt[:200])
            except Exception:
                log.exception("Hook session.start failed")

            try:
                await self._stream_llm(session, prompt, system_prompt, on_event, on_tool_approval)
            except Exception as exc:
                log.error(f"LLM error in {session.id[:8]}: {exc}", exc_info=True)
                if on_event:
                    await on_event(session_failed(session.id, str(exc)))
                session.status = "failed"

                # Fire session.fail hook
                try:
                    await _fire_hook("session.fail", session_id=session.id, model=self._llm_model, task_description=prompt[:200], outcome="exception")
                except Exception:
                    log.exception("Hook session.fail failed")
            else:
                session.status = "ready"

                # Fire session.complete hook
                try:
                    await _fire_hook("session.complete", session_id=session.id, model=self._llm_model, task_description=prompt[:200], outcome="success")
                except Exception:
                    log.exception("Hook session.complete failed")

            finally:
                wall_time = _time.monotonic() - start_time

                # Check resource constraints
                await self._check_resources(session)

    async def _stream_llm(
        self,
        session: LiveSession,
        prompt: str,
        system_prompt: str | None,
        on_event: Any,
        on_tool_approval: Any,
    ) -> None:
        """Stream LLM response via SSE to llama.cpp.

        Key fixes from PlexClaw audit:
        - assistant.completed emitted ONLY at end_turn (not from partial deltas)
        - tool.completed emitted exactly once per tool_id
        - seq assigned by event store, not passed through
        - Full agent loop: LLM → tools → LLM → ... until no tool_calls
        - Immune system checks before each tool execution
        """
        _completed_tools: set[str] = set()  # guard against double-emit (bug #3)
        self._loop_monitor.reset()  # Reset timer for each new prompt
        log.info(f"[SDK] Starting _stream_llm for session {session.id[:8]}")

        # Immune system context for this session
        immune_ctx = ImmuneContext(
            session_id=session.id,
            task_description=prompt[:500],
            context_max_tokens=128000,
        )

        # Check for prompt injection before first LLM call
        if self._immune_system:
            injection_threats = await self._immune_system._detectors["prompt_injection"].detect(immune_ctx)
            if injection_threats:
                log.warning(f"[SDK] Prompt injection detected in session {session.id[:8]}")
                for t in injection_threats:
                    await self._immune_system.responses.respond(t)
                    immune_ctx.metadata["_injection_detected"] = True
                # If injection detected, emit warning and break
                if on_event:
                    await on_event(session_failed(
                        session.id,
                        f"Prompt injection detected: {injection_threats[0].description}",
                    ))
                session.status = "failed"
                return

        # Build conversation history — load previous turns from event store
        messages = []
        
        # ── High-ROI wiring: RAG retrieval + planning + context curation ──
        # These run ONCE before the first LLM call to prime the agent
        _pre_prompt_context = ""
        
        # 1. RAG retrieval — inject relevant past solutions/docs
        if self._rag_retriever and prompt:
            try:
                rag_results = await self._rag_retriever.retrieve(prompt, top_k=5)
                if rag_results:
                    _pre_prompt_context += "## Retrieved Context (from knowledge base)\n"
                    for i, result in enumerate(rag_results[:5], 1):
                        content = result.content if hasattr(result, 'content') else str(result)[:500]
                        source = result.source if hasattr(result, 'source') else 'knowledge base'
                        score = result.score if hasattr(result, 'score') else 0.0
                        _pre_prompt_context += f"\n### Source {i}: {source} (score: {score:.2f})\n{content}\n"
                    log.info(f"[SDK] RAG retrieved {len(rag_results)} results for session {session.id[:8]}")
            except Exception as exc:
                log.debug(f"[SDK] RAG retrieval failed (non-fatal): {exc}")
        
        # 2. Planning — break complex tasks into steps before execution
        if self._planner_orchestrator and prompt:
            try:
                plan_id = self._planner_orchestrator.create_plan(prompt)
                plan = self._planner_orchestrator.get_plan(plan_id)
                if plan and plan.steps:
                    _pre_prompt_context += "\n## Task Plan\n"
                    for step in plan.steps[:5]:
                        _pre_prompt_context += f"- [{step.status}] {step.description}\n"
                    log.info(f"[SDK] Planner created plan with {len(plan.steps)} steps for session {session.id[:8]}")
            except Exception as exc:
                log.debug(f"[SDK] Planning failed (non-fatal): {exc}")
        
        # 3. Hierarchical decomposition — break complex tasks into sub-tasks
        if self._hierarchical_agent and prompt:
            try:
                from tektos.runtime.hierarchical_agent import AgentTask, AgentRole
                import uuid
                task = AgentTask(
                    task_id=str(uuid.uuid4())[:8],
                    role=AgentRole.PLANNER,
                    description=prompt,
                    context={"session_id": session.id},
                )
                self._hierarchical_agent.add_task(task)
                _pre_prompt_context += f"\n## Task Decomposition\nHierarchical agent registered task for decomposition. Break this task into sub-tasks and solve each independently.\n"
                log.info(f"[SDK] Hierarchical agent registered task for session {session.id[:8]}")
            except Exception as exc:
                log.debug(f"[SDK] Hierarchical agent failed (non-fatal): {exc}")
        
        # 4. Multi-agent delegation — identify parallelizable subtasks
        if self._multi_agent_orchestrator and prompt:
            try:
                task_id = self._multi_agent_orchestrator.create_task(
                    description=prompt,
                    priority=1,
                )
                _pre_prompt_context += f"\n## Delegation Opportunities\nMulti-agent orchestrator created task {task_id}. Consider delegating independent subtasks to parallel agents.\n"
                log.info(f"[SDK] Multi-agent created task {task_id} for session {session.id[:8]}")
            except Exception as exc:
                log.debug(f"[SDK] Multi-agent delegation failed (non-fatal): {exc}")
        
        # 5. Repo map — inject project structure awareness
        if self._repo_map_generator and prompt:
            try:
                file_count = self._repo_map_generator.build_map()
                if file_count > 0:
                    _pre_prompt_context += f"\n## Project Structure\n{file_count} files indexed in repo map. Use this to understand the codebase before writing code.\n"
                    log.info(f"[SDK] Repo map built with {file_count} entries for session {session.id[:8]}")
            except Exception as exc:
                log.debug(f"[SDK] Repo map build failed (non-fatal): {exc}")
        
        # 6. Tool routing — inject best tool recommendations
        if self._tool_router and prompt:
            try:
                best_tool = self._tool_router.get_best_tool_for_task(prompt)
                if best_tool:
                    _pre_prompt_context += f"\n## Tool Recommendations\nBest tool for this task: {best_tool}. Use this tool first, then fall back to alternatives if needed.\n"
                    log.info(f"[SDK] Tool router recommended {best_tool} for session {session.id[:8]}")
            except Exception as exc:
                log.debug(f"[SDK] Tool routing failed (non-fatal): {exc}")
        
        # 7. Context curation — track token usage
        if self._context_curator and prompt:
            try:
                self._context_curator.record_usage(len(prompt))
                snapshot = self._context_curator.get_snapshot()
                if snapshot:
                    compact_status = "compact" if snapshot.compaction_needed else "healthy"
                    _pre_prompt_context += f"\n## Context Status\nToken usage: {snapshot.used_tokens}/{snapshot.total_tokens}. Context is {compact_status}.\n"
                    log.info(f"[SDK] Context curator tracked usage for session {session.id[:8]}")
            except Exception as exc:
                log.debug(f"[SDK] Context curation failed (non-fatal): {exc}")
        

        # 8. Task decomposition — break complex tasks into numbered sub-tasks
        if self._task_decomposer and prompt:
            try:
                plan = self._task_decomposer.decompose(prompt)
                _pre_prompt_context += "\n" + self._task_decomposer.format_for_prompt(plan) + "\n"
                log.info(f"[SDK] Task decomposer created {len(plan.sub_tasks)} sub-tasks for session {session.id[:8]}")
            except Exception as exc:
                log.debug(f"[SDK] Task decomposition failed (non-fatal): {exc}")

        # ── End high-ROI wiring ──
        
        # Inject pre-prompt context into system prompt
        if _pre_prompt_context:
            base_system = (
                "You are Tektos, an autonomous coding agent. You have access to the following tools:\n"
                "- bash: Execute shell commands (timeout: 300s)\n"
                "- file_read: Read file contents\n"
                "- file_write: Write file contents (MANDATORY for all coding tasks)\n"
                "- file_delete: Delete files or directories\n"
                "- directory_list: List directory contents\n"
                "- directory_create: Create directories\n"
                "- search: Search file contents (grep-like)\n"
                "- web_search: Search the web for information (MAX 1 call)\n"
                "- web_extract: Extract content from web page URLs\n"
                "- web_fetch: Fetch/download URLs using curl\n"
                "- rag_query: Query the knowledge base for past work and documentation\n"
                "- delegate_task: Spawn a subagent for parallel workstreams\n"
                "\n"
                "CRITICAL WORKFLOW — FOLLOW THIS EXACTLY:\n"
                "STEP 1: QUICK RESEARCH (MAX 1 web_search call) — Search once for the key information you need.\n"
                "  → AFTER 1 SEARCH, YOU MUST STOP AND WRITE CODE. No more searching.\n"
                "STEP 2: WRITE — IMMEDIATELY write your implementation to a file using file_write.\n"
                "  → This is MANDATORY. Do NOT skip. Do NOT keep researching.\n"
                "STEP 3: EXECUTE — Run your code using bash.\n"
                "STEP 4: VERIFY — Check the output and verify correctness.\n"
                "\n"
                "HARDEST RULE — RESEARCH LIMIT:\n"
                "- You may call web_search AT MOST ONCE per task.\n"
                "- After that single search, you MUST transition to file_write.\n"
                "- If you don't know something, use your best knowledge and write the code.\n"
                "- It is better to write imperfect code than to research forever.\n"
                "- Research loops are the #1 cause of task failure. BREAK THE LOOP.\n"
                "\n"
                "RULES:\n"
                "- ALWAYS write code to a file using file_write before running it.\n"
                "- After researching (max 1 search), IMMEDIATELY write your implementation.\n"
                "- Do NOT keep researching — once you have enough information, WRITE THE CODE.\n"
                "- If you don't know how to do something, use your best knowledge and write code.\n"
                "- If a command takes >30s, it's normal (downloads, builds).\n"
                "- You can write to /tmp/, /app/, /usr/local/bin/.\n"
                "- Always verify your output before finishing.\n"
                "- When downloading files, use web_fetch with output_path parameter.\n"
                "- For builds, check what tools are available first (gcc, make, cmake, etc.).\n"
                "- The FINAL deliverable is always a file or executable — make sure it exists.\n"
                "- If you're doing a Terminal-Bench task, the output file path is specified in the task.\n"
                "- Write to the EXACT path specified in the task.\n"
            )
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt + "\n\n" + _pre_prompt_context})
            else:
                messages.append({"role": "system", "content": base_system + "\n\n" + _pre_prompt_context})
        elif system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": (
                    "You are Tektos, an autonomous coding agent. You have access to the following tools:\n"
                    "- bash: Execute shell commands (timeout: 300s)\n"
                    "- file_read: Read file contents\n"
                    "- file_write: Write file contents (MANDATORY for all coding tasks)\n"
                    "- file_delete: Delete files or directories\n"
                    "- directory_list: List directory contents\n"
                    "- directory_create: Create directories\n"
                    "- search: Search file contents (grep-like)\n"
                    "- web_search: Search the web for information (use this FIRST for unfamiliar tasks)\n"
                    "- web_extract: Extract content from web page URLs\n"
                    "- web_fetch: Fetch/download URLs using curl\n"
                    "- rag_query: Query the knowledge base for past work and documentation\n"
                    "- delegate_task: Spawn a subagent for parallel workstreams\n"
                    "\n"
                    "CRITICAL WORKFLOW — FOLLOW THIS EXACTLY:\n"
                    "STEP 1: RESEARCH — Use web_search to find relevant information. "
                    "Use web_extract to read the pages. Use web_fetch to download files.\n"
                    "STEP 2: WRITE — IMMEDIATELY write your implementation to a file using file_write. "
                    "DO NOT skip this step. DO NOT keep researching. Once you have enough info, WRITE THE CODE.\n"
                    "STEP 3: EXECUTE — Run your code using bash.\n"
                    "STEP 4: VERIFY — Check the output and verify correctness.\n"
                    "\n"
                    "RULES:\n"
                    "- ALWAYS write code to a file using file_write before running it.\n"
                    "- After researching, IMMEDIATELY write your implementation to a file.\n"
                    "- Do NOT keep researching — once you have enough information, WRITE THE CODE.\n"
                    "- If you don't know how to do something, SEARCH THE WEB first.\n"
                    "- Don't guess — look up documentation.\n"
                    "- If a command takes >30s, it's normal (downloads, builds).\n"
                    "- You can write to /tmp/, /app/, /usr/local/bin/.\n"
                    "- If you get stuck, try a different search query or approach.\n"
                    "- Always verify your output before finishing.\n"
                    "- When downloading files, use web_fetch with output_path parameter.\n"
                    "- For builds, check what tools are available first (gcc, make, cmake, etc.).\n"
                    "- The FINAL deliverable is always a file or executable — make sure it exists.\n"
                    "- If you're doing a Terminal-Bench task, the output file path is specified in the task.\n"
                    "- Write to the EXACT path specified in the task.\n"
                ),
            })

        # Load prior conversation history from event store
        try:
            from tektos.store.event_store import get_events as _get_events
            prior_events = await _get_events(session.id, since_seq=0, limit=500)
            # Reconstruct user/assistant message pairs from events
            assistant_text = ""
            for ev in prior_events:
                et = ev.get("type", "")
                payload = ev.get("payload", {})
                if et == "assistant.delta":
                    text = payload.get("text", "") or payload.get("delta", "")
                    if text:
                        assistant_text += text
                elif et == "assistant.completed":
                    if assistant_text.strip():
                        messages.append({"role": "assistant", "content": assistant_text.strip()})
                        assistant_text = ""
            # If there's leftover assistant text (no completed event yet), include it
            if assistant_text.strip():
                messages.append({"role": "assistant", "content": assistant_text.strip()})
            log.info(f"[SDK] Loaded {len(prior_events)} prior events, {len(messages)} messages in history")
        except Exception as exc:
            log.warning(f"[SDK] Failed to load conversation history: {exc}")

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        # Apply context compaction if available — 4-tier compression
        if self._context_compactor:
            # Estimate token count (rough: 4 chars per token)
            estimated_tokens = sum(len(m.get("content", "")) for m in messages) // 4
            if estimated_tokens > 262144:
                try:
                    compaction = self._context_compactor.compact_context(messages, estimated_tokens)
                    log.info(f"[SDK] Context compaction: {compaction.summary}")
                    # Use compacted context from tiers
                    messages = self._context_compactor.get_compacted_context()
                    # Reconstruct as messages for LLM
                    messages = [{"role": "system", "content": system_prompt or ""}, {"role": "user", "content": messages}]
                except Exception as exc:
                    log.warning(f"[SDK] Context compaction failed: {exc}")

        # Truncate conversation history to prevent context overflow (500 error from llama.cpp)
        # Keep system prompt + last 50 messages
        MAX_MESSAGES = 50
        if isinstance(messages, list) and len(messages) > MAX_MESSAGES:
            system_msgs = [m for m in messages if m.get("role") == "system"]
            user_assistant_msgs = [m for m in messages if m.get("role") != "system"]
            messages = system_msgs + user_assistant_msgs[-(MAX_MESSAGES - len(system_msgs)):]
            log.info(f"[SDK] Truncated messages from {len(messages) + (MAX_MESSAGES - len(system_msgs))} to {len(messages)}")

        log.info(f"[SDK] Messages: {len(messages)}, model: {self._llm_model}")

        turn = 0  # 1-indexed, checked by loop_safety_monitor
        stall_count = 0  # Track consecutive stalls
        max_stalls = 2  # Allow up to 2 stall recoveries before giving up
        max_turns = 100  # Hard limit on total turns to prevent infinite loops
        last_tool_calls_this_turn: list[str] = []
        last_text_length_this_turn = 0
        while True:
            # Check loop safety before this turn
            safety_report = self._loop_monitor.check_turn(
                turn_num=turn + 1,
                tool_calls=[],  # will be updated after LLM response
                text_length=0,  # will be updated after LLM response
            )

            if not safety_report.is_safe():
                log.info(f"[SDK] Loop safety triggered")
                log.warning(
                    f"Loop safety triggered in {session.id[:8]}: "
                    f"state={safety_report.state.value} "
                    f"reason={safety_report.stop_reason.value if safety_report.stop_reason else None} "
                    f"turns={safety_report.current_turn}/{safety_report.max_turns} "
                    f"tokens={safety_report.tokens_used}/{safety_report.tokens_total} "
                    f"warnings={safety_report.warnings}"
                )
                if on_event:
                    await on_event(loop_safety_warning(
                        session.id,
                        safety_report.state.value,
                        {
                            "stop_reason": safety_report.stop_reason.value if safety_report.stop_reason else None,
                            "current_turn": safety_report.current_turn,
                            "max_turns": safety_report.max_turns,
                            "tokens_used": safety_report.tokens_used,
                            "tokens_total": safety_report.tokens_total,
                            "warnings": safety_report.warnings,
                        },
                    ))
                # Break out of the loop — safety mechanism activated
                break

            turn += 1

            # Hard turn limit to prevent infinite loops
            if turn > max_turns:
                log.warning(f"[SDK] Max turns ({max_turns}) reached for session {session.id[:8]}")
                if on_event:
                    await on_event(assistant_completed(session.id, "max_turns"))
                    await append_event(session.id, "assistant.completed", {"stop_reason": "max_turns"})
                # Inject final completion message
                messages.append({
                    "role": "assistant",
                    "content": (
                        "I've reached the maximum number of turns. Here's what I've accomplished:\n"
                        "1. I researched the task using web_search and web_extract\n"
                        "2. I wrote my implementation to a file\n"
                        "3. I executed the code\n"
                        "Please check the output files for the results.\n"
                        "If the task is incomplete, try breaking it into smaller steps."
                    )
                })
                return

            # Update immune context with current message count (proxy for token usage)
            total_chars = sum(len(m.get("content", "") or "") + len(m.get("tool_calls", [])) * 100 for m in messages)
            immune_ctx.context_tokens = total_chars
            immune_ctx.model = self._llm_model

            # Check for context overflow
            if self._immune_system:
                ctx_threats = await self._immune_system._detectors["context_collapse"].detect(immune_ctx)
                if ctx_threats:
                    log.warning(f"[SDK] Context threat in session {session.id[:8]}")
                    for t in ctx_threats:
                        await self._immune_system.responses.respond(t)
                    if ctx_threats[0].severity >= ThreatSeverity.HIGH:
                        if on_event:
                            await on_event(session_failed(
                                session.id,
                                f"Context overflow: {ctx_threats[0].description}",
                            ))
                        session.status = "failed"
                        return

            try:
                # Build payload
                log.info(f"[SDK] Building payload for session {session.id[:8]}")
                payload = {
                    "model": self._llm_model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                }

                # Enable function calling with available tools
                if TOOLS_SCHEMA:
                    payload["tools"] = TOOLS_SCHEMA

                resp = await self._client.post(
                    "/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                # Check status immediately (don't wait for full response for streaming)
                resp.raise_for_status()
                log.info(f"[SDK] LLM request started for session {session.id[:8]}")

                # Parse SSE stream — two-phase pattern (following Hermes Agent):
                # Phase 1: Accumulate all chunks (text + tool_calls) from the stream
                # Phase 2: After finish_reason signals completion, execute tools
                #
                # Key insight: llama.cpp streams tool_calls as multiple chunks.
                # The model sends: [name] -> [args fragment 1] -> [args fragment 2] -> ... -> [finish_reason: tool_calls]
                # We must wait for finish_reason before executing — executing mid-stream
                # breaks the conversation because the model hasn't finished generating yet.
                #
                # This follows Hermes Agent's pattern in chat_completion_helpers.py:
                # tool_calls_acc accumulates all tool calls, then after the loop ends,
                # a single assistant message with ALL tool_calls is built, then tools execute.

                current_text = ""
                saw_any_text = False  # tracks whether ANY text was streamed this turn
                saw_text = False      # tracks text in current chunk only
                saw_real_text = False  # tracks actual text content (not reasoning)

                # Accumulate tool calls like Hermes' tool_calls_acc dict
                # Key: raw_index (from tc_delta.index), Value: {id, type, function: {name, arguments}}
                tool_calls_acc: dict = {}
                _last_id_at_idx: dict = {}      # raw_index -> last seen non-empty id
                _active_slot_by_idx: dict = {}  # raw_index -> current slot in tool_calls_acc

                # Track the finish_reason from the last chunk
                finish_reason = None
                stop_reason = None

                log.info(f"[SDK] Starting SSE stream for session {session.id[:8]}")
                reasoning_chunk_count = 0
                async for line in resp.aiter_lines():
                    if not line or line == "data: [DONE]":
                        continue
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # strip "data: "
                    try:
                        chunk = _json.loads(data_str)
                    except _json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    tool_calls = delta.get("tool_calls", [])

                    # Track finish_reason from this chunk
                    finish_reason = choices[0].get("finish_reason") or delta.get("finish_reason")
                    stop_reason = delta.get("stop_reason")

                    # Handle text content (regular content)
                    if content:
                        saw_text = True
                        saw_any_text = True
                        current_text += content
                        await on_event(assistant_delta(session.id, content))
                        # Persist assistant delta to event store for conversation history
                        try:
                            await append_event(session.id, "assistant.delta", {"text": content})
                        except Exception:
                            pass  # Non-fatal — don't break streaming on store failure

                    # Handle reasoning/thinking content (Qwen3.6, deep thinking models)
                    # Stream reasoning_content as the actual response — this IS the model's output
                    # Accumulate into current_text for message history
                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    if reasoning:
                        current_text += reasoning
                        await on_event(assistant_delta(session.id, reasoning))
                        # Persist assistant delta to event store for conversation history
                        try:
                            await append_event(session.id, "assistant.delta", {"text": reasoning})
                        except Exception:
                            pass  # Non-fatal — don't break streaming on store failure

                    # Handle tool calls — accumulate into tool_calls_acc (Hermes pattern)
                    for tc_delta in tool_calls:
                        raw_index = tc_delta.get("index", 0)
                        delta_id = tc_delta.get("id") or ""

                        # Ollama fix: detect a new tool call reusing the same raw index
                        # (different id) and redirect to a fresh slot
                        if raw_index not in _active_slot_by_idx:
                            _active_slot_by_idx[raw_index] = raw_index
                        if (
                            delta_id
                            and raw_index in _last_id_at_idx
                            and delta_id != _last_id_at_idx[raw_index]
                        ):
                            new_slot = max(tool_calls_acc, default=-1) + 1
                            _active_slot_by_idx[raw_index] = new_slot
                        if delta_id:
                            _last_id_at_idx[raw_index] = delta_id
                        idx = _active_slot_by_idx[raw_index]

                        if idx not in tool_calls_acc:
                            # Poolside may send integer id instead of string
                            _tc_id = tc_delta.get("id")
                            if isinstance(_tc_id, int):
                                _tc_id = str(_tc_id)
                            tool_calls_acc[idx] = {
                                "id": _tc_id or "",
                                "type": tc_delta.get("type", "function"),
                                "function": {"name": "", "arguments": ""},
                            }
                        entry = tool_calls_acc[idx]
                        tc_id = tc_delta.get("id")
                        if tc_id is not None:
                            _new_id = tc_id
                            if isinstance(_new_id, int):
                                _new_id = str(_new_id)
                            if _new_id:
                                entry["id"] = _new_id
                        tc_function = tc_delta.get("function")
                        if tc_function:
                            function_name = tc_function.get("name")
                            if function_name:
                                # Use assignment, not +=. Function names are atomic
                                # identifiers delivered complete in the first chunk.
                                # Some providers resend the full name in every chunk;
                                # concatenation would produce "read_fileread_file".
                                entry["function"]["name"] = function_name
                            function_args = tc_function.get("arguments")
                            if function_args:
                                entry["function"]["arguments"] += function_args

                    # Update stall detection counters
                    if tool_calls:
                        stall_count = 0  # Reset on progress

                # Phase 2: Stream complete — now process accumulated data
                log.info(f"[SDK] Stream complete. finish_reason={finish_reason} text_len={len(current_text)} tool_calls={len(tool_calls_acc)}")

                # Build the complete assistant message with ALL accumulated tool calls
                tool_calls_this_turn = list(tool_calls_acc.values())
                for _k, _v in tool_calls_acc.items():
                    _id = _v.get("id", "")[:20]
                    _name = _v.get("function", {}).get("name", "")
                    _args = len(_v.get("function", {}).get("arguments", ""))
                if finish_reason in ("stop", "tool_calls", "length") or stop_reason == "end_turn":
                    if tool_calls_this_turn:
                        # Execute all tools after the stream ends
                        for tc in tool_calls_this_turn:
                            tc_name = tc["function"]["name"]
                            tc_args = tc["function"]["arguments"]
                            tc_id = tc["id"]

                            if tc_name and tc_id:
                                log.info(f"[TOOL CALL] Executing: name={tc_name} id={tc_id[:8]} args_len={len(tc_args)}")
                                await on_event(tool_started(session.id, tc_id, tc_name, {}))
                                # Persist tool_started to event store
                                try:
                                    await append_event(session.id, "tool.started", {
                                        "tool_id": tc_id,
                                        "tool_name": tc_name,
                                        "tool_input": {},
                                    })
                                except Exception:
                                    pass

                                result_text = await self._handle_tool_completion(
                                    session, on_event, tc_id, tc_name,
                                    tc_args, _completed_tools, on_tool_approval,
                                )

                                messages.append({
                                    "role": "assistant",
                                    "tool_calls": [tc],
                                })
                                if current_text:
                                    messages.append({"role": "assistant", "content": current_text})
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "content": result_text,
                                })

                                # Check for stall after tool execution
                                if len(current_text) < 100:
                                    stall_detected = self._loop_monitor.detect_stall(
                                        event_count=len(tool_calls_this_turn),
                                        tool_call_count=1,
                                        text_length=len(current_text),
                                    )
                                    if stall_detected:
                                        stall_count += 1
                                        if stall_count <= max_stalls:
                                            recovery_msg = (
                                                "You seem to be stuck. Try a different approach:\n"
                                                "- Use web_search to look up documentation for what you're trying to do\n"
                                                "- Use web_extract to read the pages you find\n"
                                                "- Use web_fetch to download files\n"
                                                "- Break the task into smaller steps\n"
                                                "- If you're downloading something, use web_fetch with output_path\n"
                                                "- If you're building something, check what tools are available first\n"
                                                "Try again with a new strategy."
                                            )
                                            messages.append({"role": "user", "content": recovery_msg})
                                            log.info(f"[SDK] Stall recovery #{stall_count} injected for session {session.id[:8]}")
                                            current_text = ""
                                            continue
                                        else:
                                            log.warning(f"[SDK] Max stalls ({max_stalls}) reached for session {session.id[:8]}")
                                    else:
                                        stall_count = 0
                                else:
                                    stall_count = 0
                    elif saw_any_text or current_text:
                        # Text-only response — no tool calls
                        await on_event(assistant_completed(session.id, stop_reason or "end_turn"))
                        # Persist assistant.completed to event store
                        try:
                            await append_event(session.id, "assistant.completed", {"stop_reason": stop_reason or "end_turn"})
                        except Exception:
                            pass  # Non-fatal
                        messages.append({"role": "assistant", "content": current_text})
                        # No more tool calls — agent loop complete, return from function
                        return

            except httpx.ConnectError as exc:
                raise RuntimeError(f"Cannot connect to LLM at {self._llm_base_url}: {exc}")
            except httpx.TimeoutException as exc:
                raise RuntimeError(f"LLM request timed out: {exc}")
            except Exception as exc:
                raise RuntimeError(f"LLM streaming error: {exc}")

    async def _handle_tool_completion(
        self,
        session: LiveSession,
        on_event: Any,
        tool_id: str,
        tool_name: str,
        tool_input_str: str,
        completed_tools: set[str],
        on_tool_approval: Any,
    ) -> str:
        """Handle tool completion. Emits tool.completed exactly once per tool_id.

        Immune system checks run before execution:
        - Dangerous command detection (bash)
        - Secret exposure detection (all tools)
        - Self-modification detection (file_write, bash)
        """
        # Guard against double-emit (PlexClaw bug #3 fix)
        if tool_id in completed_tools:
            return ""

        # Parse tool input
        try:
            tool_input = _json.loads(tool_input_str) if tool_input_str else {}
        except _json.JSONDecodeError:
            tool_input = {}

        # Run immune system checks before execution
        if self._immune_system:
            immune_ctx = ImmuneContext(
                session_id=session.id,
                tool_name=tool_name,
                tool_input=tool_input,
                task_description=session.title[:500] if session.title else "",
            )

            # Check dangerous commands
            danger_threats = await self._immune_system._detectors["dangerous_command"].detect(immune_ctx)
            if danger_threats:
                log.warning(f"[SDK] Dangerous command detected in {session.id[:8]}: {danger_threats[0].description}")
                for t in danger_threats:
                    response = await self._immune_system.responses.respond(t)
                    if t.metadata.get("_emergency") or t.metadata.get("_halted"):
                        completed_tools.add(tool_id)
                        await on_event(tool_completed(session.id, tool_id, "blocked", f"Blocked by immune system: {t.description}"))
                        return f"BLOCKED: {t.description}"
                # For HIGH severity, require approval
                if danger_threats[0].severity >= ThreatSeverity.HIGH:
                    if on_tool_approval:
                        approved = await on_tool_approval(tool_id, f"immune_check:{danger_threats[0].category.value}")
                        if not approved:
                            completed_tools.add(tool_id)
                            await on_event(tool_completed(session.id, tool_id, "rejected", "Tool blocked by immune system"))
                            return "Tool blocked by immune system"

            # Check secret exposure
            secret_threats = await self._immune_system._detectors["secret_exposure"].detect(immune_ctx)
            if secret_threats:
                log.warning(f"[SDK] Secret exposure detected in {session.id[:8]}: {secret_threats[0].description}")
                for t in secret_threats:
                    response = await self._immune_system.responses.respond(t)
                    completed_tools.add(tool_id)
                    await on_event(tool_completed(session.id, tool_id, "blocked", f"Blocked by immune system: {t.description}"))
                    return f"BLOCKED: {t.description}"

            # Check self-modification
            self_mod_threats = await self._immune_system._detectors["self_modification"].detect(immune_ctx)
            if self_mod_threats:
                log.warning(f"[SDK] Self-modification attempt in {session.id[:8]}: {self_mod_threats[0].description}")
                for t in self_mod_threats:
                    response = await self._immune_system.responses.respond(t)
                    if on_tool_approval:
                        approved = await on_tool_approval(tool_id, f"immune_check:self_modification")
                        if not approved:
                            completed_tools.add(tool_id)
                            await on_event(tool_completed(session.id, tool_id, "rejected", "Self-modification blocked by immune system"))
                            return "Self-modification blocked by immune system"

        # Check permission mode
        if session.permission_mode == "manual":
            # Request human approval
            await on_event(tool_permission_required(session.id, tool_id, tool_name, tool_input))

            # Wait for approval
            if on_tool_approval:
                approved = await on_tool_approval(tool_id, tool_name)
                if not approved:
                    completed_tools.add(tool_id)
                    await on_event(tool_completed(session.id, tool_id, "rejected", "Tool rejected by user"))
                    return "Tool rejected by user"
            else:
                # No approval callback provided — reject to prevent unauthorized execution
                completed_tools.add(tool_id)
                await on_event(tool_completed(session.id, tool_id, "rejected", "Tool approval callback not provided in manual mode"))
                return "Tool rejected: no approval callback"

        # Execute tool (actual execution via SandboxProvider or MCP registry)
        try:
            # Fire tool.before hook before execution
            try:
                await _fire_hook("tool.before", session_id=session.id, tool_name=tool_name, tool_input=tool_input)  # type: ignore[misc]
            except Exception:
                log.exception("Hook tool.before failed")

            # Fire tool.execute hook before execution
            try:
                await _fire_hook("tool.execute", session_id=session.id, tool_name=tool_name, tool_input=tool_input)  # type: ignore[misc]
            except Exception:
                log.exception("Hook tool.execute failed")

            result = await self._execute_tool(tool_name, tool_input)
            completed_tools.add(tool_id)  # Mark as completed BEFORE returning
            await on_event(tool_completed(session.id, tool_id, "success", str(result)))
            # Persist tool_completed to event store
            try:
                await append_event(session.id, "tool.completed", {
                    "tool_id": tool_id,
                    "tool_name": tool_name,
                    "status": "success",
                    "output": str(result),
                })
            except Exception:
                pass

            # Fire tool.after hook after successful execution
            try:
                await _fire_hook("tool.after", session_id=session.id, tool_name=tool_name, tool_input=tool_input, outcome="success")  # type: ignore[misc]
            except Exception:
                log.exception("Hook tool.after failed")

            return str(result)
        except Exception as exc:
            completed_tools.add(tool_id)  # Mark as completed on error too
            error_msg = str(exc)
            await on_event(tool_completed(session.id, tool_id, "error", error_msg))
            # Persist tool_completed to event store
            try:
                await append_event(session.id, "tool.completed", {
                    "tool_id": tool_id,
                    "tool_name": tool_name,
                    "status": "error",
                    "output": error_msg,
                })
            except Exception:
                pass

            # Fire tool.after hook after failed execution
            try:
                await _fire_hook("tool.after", session_id=session.id, tool_name=tool_name, tool_input=tool_input, outcome="error", message=error_msg)  # type: ignore[misc]
            except Exception:
                log.exception("Hook tool.after failed")

            return f"Error: {error_msg}"

    async def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool via the SandboxProvider or MCP registry.

        MCP tools take priority — if a tool is registered in the MCP registry,
        invoke it there. Otherwise fall back to sandbox execution.
        """
        # Check MCP registry first
        from tektos.runtime.mcp_integration import get_mcp_registry
        registry = get_mcp_registry()
        if tool_name in registry._tools:
            result = await registry.invoke_tool(tool_name, tool_input)
            if result.success:
                log.info(f"[MCP] {tool_name} → {len(result.content)} chars")
                return result.content
            else:
                log.error(f"[MCP] {tool_name} failed: {result.error}")
                raise RuntimeError(f"MCP tool execution failed: {result.error}")

        # Fall back to sandbox execution
        try:
            result = self._sandbox.execute(tool_name, tool_input)
            log.info(f"[TOOK] {tool_name} → {len(str(result))} chars")
            return result
        except Exception as exc:
            log.error(f"[TOOL ERROR] {tool_name}: {exc}", exc_info=True)
            raise RuntimeError(f"Tool execution failed: {exc}")

    async def _check_resources(self, session: LiveSession) -> None:
        """Check GPU temp, disk, VRAM and emit warnings if needed.

        Delegates to MetabolismEngine for comprehensive resource monitoring.
        """
        # Delegate to MetabolismEngine for full resource assessment
        health = self._metabolism_engine.assess_health()
        state_dict = health.to_dict()

        # Emit resource warnings based on MetabolismEngine assessment
        if health.overall_health.value != "normal":
            await append_event(session.id, "resource.warning", {
                "resource": "overall",
                "level": health.overall_health.value,
                "details": state_dict,
            })
            log.warning(f"Resource alert: {health.overall_health.value}")

        # Also check GPU temp specifically for backward compatibility
        if health.gpu:
            gpu_temp = health.gpu.temperature
            if gpu_temp > 80:  # Operational ceiling
                await append_event(session.id, "resource.warning", {
                    "resource": "gpu_temp",
                    "current": gpu_temp,
                    "threshold": 80,
                    "message": f"GPU temperature {gpu_temp}°C exceeds operational ceiling (80°C)",
                })
                log.warning(f"GPU temp {gpu_temp}°C — above operational ceiling")
            elif gpu_temp > 51:  # Yellow zone
                log.info(f"GPU temp {gpu_temp}°C — in yellow zone (monitoring)")

    async def interrupt(self, session: LiveSession) -> None:
        """Interrupt a running session."""
        # For llama.cpp SSE, we can't truly interrupt — mark as interrupted
        session.status = "interrupted"
        await append_event(session.id, "session.interrupted", {
            "message": "Session interrupted",
        })
