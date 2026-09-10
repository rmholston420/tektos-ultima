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
from tektos.runtime.loop_guard import get_guard
from tektos.runtime.external_evaluator import evaluator as external_evaluator
from tektos.runtime.session import LiveSession
from tektos.runtime.context_compactor import ContextCompactor
from tektos.runtime.embedder import EmbedderClient
from tektos.memory.file_based_memory import FileBasedMemory
from tektos.runtime.tool_router import ToolRouter, ToolCategory, ToolPerformance
from tektos.runtime.multi_agent_orchestrator import MultiAgentOrchestrator
from tektos.runtime.inference_engine import InferenceEngineMonitor, get_monitor
from tektos.runtime.repo_memory import get_repo_memory
from tektos.runtime.mcp_integration import get_mcp_registry, MCPClient
from tektos.runtime.context_engineering import get_ace_framework
from tektos.runtime.long_running_agent import get_long_running_agent, LongRunningAgent
from tektos.runtime.hierarchical_agent import get_hierarchical_agent
from tektos.metabolism import MetabolismEngine
from tektos.store.event_store import append_event
from tektos.memory.memory_system import MemorySystem, MemoryTier, Hemisphere
from tektos.memory.reflection_engine import ReflectionEngine
from tektos.memory.synthesis_engine import SynthesisEngine
from tektos.memory.experience_replay import ExperienceReplay
from tektos.runtime.self_modification import get_self_modification_engine
from tektos.runtime.evaluation_framework import get_evaluation_harness
from tektos.runtime.observability import get_observability_manager
from tektos.providers.unified_search import get_unified_search_provider

log = _log.getLogger("tektos.runtime")

# LLM endpoint configuration — configurable via environment
LLM_BASE_URL = _os.getenv("TEKTOS_LLM_BASE_URL", "http://127.0.0.1:8090/v1")
LLM_MODEL = "Qwen_Qwen3.6-35B-A3B-Q5_K_M"

# Secondary LLM (CPU-based, for offloading simple tasks)
LLM_SECONDARY_BASE_URL = _os.getenv("TEKTOS_LLM_SECONDARY_URL", "http://127.0.0.1:8092/v1")
LLM_SECONDARY_MODEL = "Granite4.1-8B-UD"

# Task routing: which tasks go to which LLM
# Simple tasks: file reads, simple edits, basic commands → secondary LLM
# Complex tasks: planning, multi-file refactoring, deep reasoning → primary LLM
SIMPLE_TASK_KEYWORDS = [
    "read file", "read the file", "open file", "view file", "check file",
    "write file", "create file", "save file", "edit file", "update file",
    "delete file", "delete", "remove file", "remove",
    "list directory", "list files", "ls",
    "create directory", "mkdir",
    "search", "find", "grep",
    "run", "execute", "install", "pip", "apt",
    "git status", "git log", "git diff", "git branch",
    "check", "verify", "test",
    "what is", "where is", "how many",
    "copy", "move", "rename",
]
COMPLEX_TASK_KEYWORDS = [
    "plan", "design", "architect", "refactor", "restructure",
    "implement", "build", "create a", "write a",
    "analyze", "review", "audit",
    "debug", "fix", "resolve",
    "optimize", "improve", "enhance",
    "multi-file", "across files", "multiple files",
    "system", "architecture", "framework",
    "strategy", "approach", "methodology",
]

# Tool definitions for function calling
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a shell command for any task: running programs, installing packages, checking system state, git operations, etc.",
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
            "name": "file_write",
            "description": "Write content to a file. Creates parent directories automatically. Handles large files (up to 8KB chunks) automatically. Use for creating or overwriting files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write to the file"},
                    "mode": {"type": "string", "description": "Write mode: 'write' (overwrite) or 'append'", "enum": ["write", "append"]}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for additional information. CRITICAL: You MUST search your own knowledge bases FIRST before using web_search. Always try these in order: (1) file_read to check relevant files, (2) search to grep file contents, (3) memory_search to check your own memory/experience, (4) THEN web_search for external information. Use web_search ONLY when your own knowledge bases don't have the answer. SearXNG is the primary search engine (self-hosted, free, private); Tavily is the automatic fallback if SearXNG is unavailable. Use web_search when: (1) you need facts not in your memory or local files, (2) you need current data (versions, dates, news), (3) you need documentation or API references not in the codebase, (4) you need research or external context. NEVER use web_search if the answer might be in your own files or memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {"type": "integer", "description": "Maximum number of results to return (default: 5)", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_extract",
            "description": "Extract and read the full text content from a web page URL. Use this after web_search to read the most relevant result, or when you have a specific URL you need to read. Returns clean markdown text from the page. Use this when: (1) a search result snippet isn't enough and you need the full article, (2) you need to read documentation, a blog post, or a technical page, (3) you need to extract structured data from a webpage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to extract content from"}
                },
                "required": ["url"]
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
        memory_dir: str = "./memory",
        repo_root: str = ".",
        embedder_base_url: str = "http://127.0.0.1:8091/v1",
        use_secondary_llm: bool = True,
    ) -> None:
        self._llm_base_url = llm_base_url
        self._llm_model = llm_model
        self._use_secondary_llm = use_secondary_llm
        self._client: httpx.AsyncClient | None = None
        self._secondary_client: httpx.AsyncClient | None = None
        self._lock = _asyncio.Lock()
        self._sandbox = SandboxProvider()
        self._loop_monitor = LoopSafetyMonitor(loop_safety_config or LoopSafetyConfig())
        # New integrations
        self._context_compactor = ContextCompactor(max_tokens=128000)
        self._embedder = EmbedderClient(llm_base_url=embedder_base_url)
        self._memory = FileBasedMemory(
            memory_dir=memory_dir,
            project_root=repo_root,
            embedder_client=self._embedder,
        )
        self._tool_router = ToolRouter()
        self._orchestrator = MultiAgentOrchestrator(max_concurrent_agents=3)
        # Metabolism engine — resource monitoring (VRAM, context, thermal)
        self._metabolism = MetabolismEngine()
        # Self-improvement loop components
        self._memory_system = MemorySystem()
        self._reflection_engine = ReflectionEngine(
            memory_system=self._memory_system,
            dreamtime_engine=self._memory_system.dreamtime,
        )
        self._synthesis_engine = SynthesisEngine(
            reflection_engine=self._reflection_engine,
            memory_system=self._memory_system,
        )
        self._experience_replay = ExperienceReplay(max_records=50)
        self._synthesis_guidance: str = ""  # Accumulated guidance from past cycles
        # Inference engine monitor
        self._inference_monitor: InferenceEngineMonitor | None = None
        # Unified search provider (SearXNG primary, Tavily fallback)
        self._unified_search = get_unified_search_provider()
        # ACE framework (context engineering)
        self._ace_framework = get_ace_framework()
        # Long-running agent support
        self._long_running_agent = None
        # Repo memory (CLAUDE.md, AGENTS.md, etc.)
        self._repo_memory = get_repo_memory()
        # Hierarchical multi-agent support
        self._hierarchical_agent = get_hierarchical_agent()

    async def start(self) -> None:
        """Create the httpx clients."""
        self._client = httpx.AsyncClient(
            base_url=self._llm_base_url,
            timeout=httpx.Timeout(30.0, read=300.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        # Validate primary connection
        try:
            resp = await self._client.get("/models")
            resp.raise_for_status()
            log.info(f"Primary LLM endpoint connected: {self._llm_base_url}")
        except Exception as exc:
            log.warning(f"Primary LLM endpoint not available at {self._llm_base_url}: {exc}")
            raise

        # Initialize inference engine monitor
        self._inference_monitor = get_monitor()
        await self._inference_monitor.start()
        log.info("[SDK] Inference engine monitor initialized")

        # Initialize MCP clients
        await self._initialize_mcp_clients()
        log.info("[SDK] MCP clients initialized")

        # Initialize ACE framework
        self._ace_framework.start_session()
        log.info("[SDK] ACE framework initialized")

        # Initialize long-running agent support
        self._long_running_agent = LongRunningAgent(
            session_id="default",
            checkpoint_dir="./checkpoints",
        )
        log.info("[SDK] Long-running agent initialized")

        # Initialize secondary client if enabled
        if self._use_secondary_llm:
            self._secondary_client = httpx.AsyncClient(
                base_url=LLM_SECONDARY_BASE_URL,
                timeout=httpx.Timeout(10.0, read=60.0),
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            )
            try:
                resp = await self._secondary_client.get("/models")
                resp.raise_for_status()
                log.info(f"Secondary LLM endpoint connected: {LLM_SECONDARY_BASE_URL}")
            except Exception as exc:
                log.warning(f"Secondary LLM endpoint not available at {LLM_SECONDARY_BASE_URL}: {exc}")
                log.info("Will fall back to primary LLM for all tasks")
                self._secondary_client = None

    async def _initialize_mcp_clients(self) -> None:
        """Initialize MCP clients from the registry.
        
        MCP clients connect to external MCP servers for tool extensibility.
        This is a no-op if no MCP servers are configured.
        """
        try:
            registry = get_mcp_registry()
            if registry:
                connected = await registry.connect_all()
                log.info(f"[MCP] {connected} client(s) connected")
        except Exception as exc:
            log.warning(f"[MCP] Failed to initialize MCP clients: {exc}")

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._secondary_client:
            await self._secondary_client.aclose()
            self._secondary_client = None
        if self._inference_monitor:
            await self._inference_monitor.stop()
            self._inference_monitor = None
        # MCP clients are cleaned up automatically
        if self._long_running_agent:
            await self._long_running_agent.stop("completed")

    def _route_task(self, prompt: str) -> tuple[str, str]:
        """Route a task to the appropriate LLM based on complexity.

        Args:
            prompt: The user's prompt.

        Returns:
            Tuple of (base_url, model) for the chosen LLM.
        """
        if not self._use_secondary_llm or self._secondary_client is None:
            return (self._llm_base_url, self._llm_model)

        prompt_lower = prompt.lower()

        # Check for complex task keywords first (higher priority)
        for keyword in COMPLEX_TASK_KEYWORDS:
            if keyword in prompt_lower:
                log.info(f"[Router] Complex task detected ('{keyword}') → primary LLM")
                return (self._llm_base_url, self._llm_model)

        # Check for simple task keywords
        for keyword in SIMPLE_TASK_KEYWORDS:
            if keyword in prompt_lower:
                log.info(f"[Router] Simple task detected ('{keyword}') → secondary LLM")
                return (LLM_SECONDARY_BASE_URL, LLM_SECONDARY_MODEL)

        # Default: use primary LLM for ambiguous tasks
        log.info("[Router] Ambiguous task → primary LLM")
        return (self._llm_base_url, self._llm_model)

    async def _stream_llm_secondary(
        self,
        session: LiveSession,
        prompt: str,
        system_prompt: str | None,
        on_event: Any,
        on_tool_approval: Any,
    ) -> None:
        """Stream LLM response from the secondary (CPU) LLM via SSE.

        The secondary LLM is simpler and doesn't support tool calling,
        so this is a single-turn completion. Results are stored in
        session history for the agent to act on.

        Args:
            session: The LiveSession to run against.
            prompt: The user's prompt.
            system_prompt: Optional system prompt override.
            on_event: Callback for each normalized event.
            on_tool_approval: Callback for tool approval requests (unused).
        """
        if self._secondary_client is None:
            raise RuntimeError("Secondary LLM not available")

        # Build messages
        messages = []
        memory_context = self._memory.get_context_prompt()
        system_prompt_text = system_prompt or (
            "You are a helpful coding assistant. Answer questions directly and concisely. "
            "For file operations, provide the exact commands or file contents. "
            "For simple tasks, respond directly without tool calls. "
            "Search Strategy — KNOWLEDGE BASE FIRST: "
            "Always search your own knowledge bases BEFORE using web_search. "
            "Follow this exact order: (1) file_read to check relevant files, "
            "(2) search to grep file contents, (3) memory_search to check your own memory, "
            "(4) THEN web_search for external information. "
            "Use web_search ONLY when your own knowledge bases don't have the answer. "
            "NEVER use web_search if the answer might be in your own files or memory. "
            "Always exhaust local resources first. "
            "After web_search, use web_extract to read the most relevant result."
        )
        if memory_context:
            system_prompt_text += "\n\n# Persistent Project Memory\n" + memory_context
        
        # Add repo memory (CLAUDE.md, AGENTS.md, etc.)
        repo_memory_context = self._repo_memory.get_context_prompt()
        if repo_memory_context:
            system_prompt_text += repo_memory_context
        
        # Add ACE framework curated context
        ace_context = self._ace_framework.get_curated_context()
        if ace_context:
            system_prompt_text += "\n\n# Context Engineering\n" + ace_context
        messages.append({"role": "system", "content": system_prompt_text})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": LLM_SECONDARY_MODEL,
            "messages": messages,
            "stream": True,
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        resp = await self._secondary_client.post(
            "/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()

        # Parse SSE stream
        current_text = ""
        async for line in resp.aiter_lines():
            if not line or line == "data: [DONE]":
                continue
            if not line.startswith("data: "):
                continue

            data_str = line[6:]
            try:
                chunk = _json.loads(data_str)
            except _json.JSONDecodeError:
                continue

            choices = chunk.get("choices", [])
            if not choices:
                continue

            delta = choices[0].get("delta", {})
            content = delta.get("content")

            if content:
                current_text += content
                await on_event(assistant_delta(session.id, content))

        # Store the secondary LLM's response in the event store
        # so it's available for the agent to act on in the next turn
        if current_text:
            from tektos.store.event_store import append_event
            await append_event(
                session.id,
                "assistant.completed",
                {
                    "message": current_text,
                    "model": LLM_SECONDARY_MODEL,
                },
            )
            log.info(f"[Secondary LLM] Response stored for session {session.id[:8]}")

            # Emit completion event
            if on_event:
                await on_event(assistant_completed(session.id, current_text))

    async def submit_prompt(
        self,
        session: LiveSession,
        prompt: str,
        system_prompt: str | None = None,
        on_event: Any = None,  # Callable[[WSEnvelope], Awaitable[None]]
        on_tool_approval: Any = None,  # Callable[[str, str], Awaitable[bool]]
    ) -> None:
        """Submit a prompt to the LLM. Routes to primary or secondary LLM.

        Simple tasks (file reads, basic commands) → secondary LLM (CPU)
        Complex tasks (planning, refactoring, deep reasoning) → primary LLM (GPU)

        After each session, runs reflection and synthesis to improve future cycles.

        Args:
            session: The LiveSession to run against.
            prompt: The user's prompt.
            system_prompt: Optional system prompt override.
            on_event: Callback for each normalized event.
            on_tool_approval: Callback for tool approval requests (manual mode).
        """
        if not self._client:
            raise RuntimeError("RuntimeSDK not started. Call start() first.")

        # Route task to appropriate LLM
        target_url, target_model = self._route_task(prompt)
        is_secondary = (target_url == LLM_SECONDARY_BASE_URL)

        # Track tool results for reflection
        tool_results: list[str] = []
        
        # Update ACE framework with session context
        self._ace_framework.update_context(
            new_context=prompt,
            new_constraints=[system_prompt or ""],
        )
        
        # Update long-running agent progress
        if self._long_running_agent:
            self._long_running_agent.update_progress(current_step=prompt[:100])
            await self._long_running_agent.checkpoint_if_needed()
        
        # Add task to hierarchical agent
        if self._hierarchical_agent:
            from tektos.runtime.hierarchical_agent import AgentTask, AgentRole
            task = AgentTask(
                task_id=f"task_{int(_time.time())}",
                role=AgentRole.CODER,
                description=prompt[:200],
            )
            self._hierarchical_agent.add_task(task)
        
        # Unified search provider (SearXNG primary, Tavily fallback)
        # Available via self._unified_search.search(query, max_results)
        # Usage: results = await self._unified_search.search("what is X")
        # Returns SearchResponse with results from SearXNG or Tavily

        async with self._lock:
            session.status = "running"
            session.updated_at = _time.monotonic()

            start_time = _time.monotonic()

            try:
                if is_secondary:
                    # Use secondary LLM for simple tasks (single-turn, no tool calling)
                    log.info(f"[SDK] Routing to secondary LLM ({target_model}) for session {session.id[:8]}")
                    await self._stream_llm_secondary(
                        session, prompt, system_prompt, on_event, on_tool_approval
                    )
                else:
                    # Use primary LLM for complex tasks (full agent loop with tool calling)
                    log.info(f"[SDK] Routing to primary LLM ({target_model}) for session {session.id[:8]}")
                    await self._stream_llm(
                        session, prompt, system_prompt, on_event, on_tool_approval
                    )
            except Exception as exc:
                log.error(f"LLM error in {session.id[:8]}: {exc}", exc_info=True)
                if on_event:
                    await on_event(session_failed(session.id, str(exc)))
                session.status = "failed"

                # Run reflection on failure for self-improvement
                await self._run_reflection_and_synthesis(
                    session, prompt, "failure", tool_results
                )
            else:
                session.status = "ready"

                # Run reflection and synthesis for self-improvement
                await self._run_reflection_and_synthesis(
                    session, prompt, "success", tool_results
                )

            finally:
                wall_time = _time.monotonic() - start_time

                # Run completion hook
                await hooks.run("session.completed", HookContext(
                    session_id=session.id,
                    model=target_model,
                    task_description=prompt[:200],
                    outcome="success" if session.status == "ready" else "failure",
                    wall_time=wall_time,
                ))

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
        """
        _completed_tools: set[str] = set()  # guard against double-emit (bug #3)
        self._loop_monitor.reset()  # Reset timer for each new prompt
        log.info(f"[SDK] Starting _stream_llm for session {session.id[:8]}")

        # Build conversation history
        messages = []

        # Load file-based memory for persistent context (CLAUDE.md style)
        memory_context = self._memory.get_context_prompt()

        system_prompt_text = system_prompt or (
            "You are a highly capable coding agent. You have access to a full suite of tools for file operations, shell commands, and search. Use them directly and efficiently — do not artificially limit yourself. For file writing, use the file_write tool with the full content; it handles large files automatically. For reading files, use file_read. For shell commands, use bash. For searching file contents, use search. For directory operations, use directory_list and directory_create.\n\n# Search Strategy — KNOWLEDGE BASE FIRST\nYou MUST always search your own knowledge bases BEFORE using web_search. Follow this exact order:\n1. file_read — Check relevant files in the codebase\n2. search — Grep file contents for keywords\n3. memory_search — Check your own memory/experience (if available)\n4. web_search — ONLY if your own knowledge bases don't have the answer\n\nUse web_search ONLY when:\n- The answer is NOT in your local files or memory\n- You need current data (versions, dates, news, releases)\n- You need documentation or API references not in the codebase\n- You need research or external context\n\nNEVER use web_search if the answer might be in your own files or memory. Always exhaust local resources first.\n\n# Web Search\nYou have web_search and web_extract tools for searching the internet. Use web_search when your knowledge bases are exhausted. After web_search, use web_extract to read the most relevant result.\n\nAlways think carefully before acting, and use the most direct tool for each task."
        )
        # Append synthesis guidance from past cycles (self-improvement)
        synthesis_guidance = self.get_synthesis_guidance()
        if synthesis_guidance:
            system_prompt_text += synthesis_guidance
        # Append persistent memory to system prompt
        if memory_context:
            system_prompt_text += "\n\n# Persistent Project Memory\n" + memory_context
        if system_prompt_text:
            messages.append({"role": "system", "content": system_prompt_text})
        messages.append({"role": "user", "content": prompt})
        log.info(f"[SDK] Messages: {len(messages)}, model: {self._llm_model}")

        turn = 0  # 1-indexed, checked by loop_safety_monitor
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

            try:
                # Truncate messages to stay within VRAM context window
                # Strategy: keep system prompt + last N messages, aggressively trim
                # to avoid OOM on 32GB GPU with q8_0 KV cache
                MAX_MESSAGES = 200
                if len(messages) > MAX_MESSAGES:
                    # Keep system prompt and last MAX_MESSAGES entries
                    system_msgs = [m for m in messages if m.get("role") == "system"]
                    user_assistant_msgs = [m for m in messages if m.get("role") != "system"]
                    messages = system_msgs + user_assistant_msgs[-(MAX_MESSAGES - len(system_msgs)):]
                    log.info(f"[SDK] Truncated messages from {len(messages)} to {MAX_MESSAGES}")

                # Build payload
                log.info(f"[SDK] Building payload for session {session.id[:8]} ({len(messages)} messages)")
                payload = {
                    "model": self._llm_model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.1,
                    "max_tokens": 8192,
                    "chat_template_kwargs": {
                        "preserve_thinking": True,
                        "enable_thinking": True,
                    },
                    "reasoning_effort": "xhigh",
                }

                # Enable function calling — full tool schema with rich descriptions
                # file_write is included; the sandbox handles large files via chunking
                payload["tools"] = TOOLS_SCHEMA

                resp = await self._client.post(
                    "/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                # Check status immediately (don't wait for full response for streaming)
                if resp.status_code != 200:
                    log.error(f"[SDK] LLM returned {resp.status_code}: {resp.text[:500]}")
                resp.raise_for_status()
                log.info(f"[SDK] LLM request started for session {session.id[:8]}")

                # Parse SSE stream
                current_text = ""
                current_tool_name = ""
                current_tool_id = ""
                current_tool_json = ""
                saw_any_text = False  # tracks whether ANY text was streamed this turn
                saw_text = False      # tracks text in current chunk only
                saw_real_text = False  # tracks actual text content (not reasoning)
                tool_calls_this_turn: list[dict] = []

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

                    # Handle text content (regular content)
                    if content:
                        saw_text = True
                        saw_any_text = True
                        current_text += content
                        await on_event(assistant_delta(session.id, content))

                    # Handle reasoning/thinking content (Qwen3.6, deep thinking models)
                    # Stream reasoning_content as the actual response — this IS the model's output
                    # Accumulate into current_text for message history
                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    if reasoning:
                        current_text += reasoning
                        await on_event(assistant_delta(session.id, reasoning))

                    # Handle tool calls
                    for tc in tool_calls:
                        _tc_idx = tc.get("index", 0)
                        # llama.cpp only sends ID on first chunk; reuse current_tool_id if empty
                        tc_id = tc.get("id") or current_tool_id or str(_uuid.uuid4())
                        _tc_type = tc.get("type", "function")
                        tc_func = tc.get("function", {})
                        tc_func_name = tc_func.get("name", "")
                        tc_func_args = tc_func.get("arguments", "")

                        if tc_func_name and not current_tool_name:
                            # Start of new tool call
                            current_tool_name = tc_func_name
                            current_tool_id = tc_id
                            current_tool_json = ""  # Start fresh; all fragments accumulate from here
                            log.info(f"[TOOL CALL] Start: name={tc_func_name} id={tc_id[:8]}")
                            await on_event(tool_started(session.id, tc_id, tc_func_name, {}))
                            # Track this tool call for later result injection
                            tool_calls_this_turn.append({
                                "id": tc_id,
                                "type": "function",
                                "function": {
                                    "name": tc_func_name,
                                    "arguments": "",
                                },
                            })

                        if tc_func_args:
                            # llama.cpp streams JSON arguments as fragments - accumulate
                            current_tool_json += tc_func_args
                            # Update the tracked tool call's arguments
                            if tool_calls_this_turn:
                                tool_calls_this_turn[-1]["function"]["arguments"] += tc_func_args

                    # Check if this is the last chunk
                    # llama.cpp puts finish_reason at choices[0], delta may have stop_reason
                    finish_reason = choices[0].get("finish_reason") or delta.get("finish_reason")
                    stop_reason = delta.get("stop_reason")
                    is_last = finish_reason in ("stop", "tool_calls", "length") or stop_reason == "end_turn"

                    if is_last:
                        # Parse and execute tool if present
                        if current_tool_name and current_tool_id:
                            result_text = await self._handle_tool_completion(
                                session, on_event, current_tool_id, current_tool_name,
                                current_tool_json, _completed_tools, on_tool_approval,
                            )
                            # Always add assistant message for valid conversation history
                            # (LLM may respond with tool calls only, no text)
                            messages.append({
                                "role": "assistant",
                                "tool_calls": tool_calls_this_turn,
                            })
                            if current_text:
                                messages.append({"role": "assistant", "content": current_text})
                            messages.append({
                                "role": "tool",
                                "tool_call_id": current_tool_id,
                                "content": result_text,
                            })
                            # Reset state for next tool or end of turn
                            current_text = ""
                            current_tool_name = ""
                            current_tool_id = ""
                            current_tool_json = ""
                            saw_any_text = False
                            saw_text = False
                        elif saw_any_text or current_text:
                            # Emit assistant.completed when text was streamed this turn.
                            # Use saw_any_text (not saw_text) because the final chunk
                            # may have finish_reason but empty content — the text was
                            # already emitted in previous chunks.
                            await on_event(assistant_completed(session.id, stop_reason or "end_turn"))
                            # Add assistant text to conversation
                            messages.append({"role": "assistant", "content": current_text})
                            # No more tool calls — agent loop complete, return from function
                            return

                        # Reset state
                        current_text = ""
                        current_tool_name = ""
                        current_tool_id = ""
                        current_tool_json = ""
                        saw_any_text = False
                        saw_text = False

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

        Returns the tool output string to inject into the conversation.
        """
        # Guard against double-emit (PlexClaw bug #3 fix)
        if tool_id in completed_tools:
            return ""

        # Parse tool input
        try:
            tool_input = _json.loads(tool_input_str) if tool_input_str else {}
        except _json.JSONDecodeError:
            tool_input = {}

        # Loop guard: check if this tool call is part of a repeated pattern
        guard = get_guard()
        guard_result = guard.record_call(tool_name, tool_input)
        if guard_result["blocked"]:
            log.warning(
                f"[LOOP GUARD] Tool '{tool_name}' blocked in {session.id[:8]}: "
                f"{guard_result['message']}"
            )
            if on_event:
                await on_event(loop_safety_warning(
                    session.id,
                    "loop_guard",
                    {
                        "tool": tool_name,
                        "message": guard_result["message"],
                        "suggestion": guard_result["suggestion"],
                    },
                ))
            return "BLOCKED: Tool call pattern detected. Change approach."

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
                # No approval callback in manual mode — reject to prevent
                # unauthorized execution (the original bug: fell through to
                # execution even in manual mode when on_tool_approval was None)
                completed_tools.add(tool_id)
                await on_event(tool_completed(session.id, tool_id, "rejected", "Tool rejected: no approval callback in manual mode"))
                return "Tool rejected: no approval callback in manual mode"

        # Execute tool (actual execution via SandboxProvider)
        try:
            result = await self._execute_tool(tool_name, tool_input)
            completed_tools.add(tool_id)  # Mark as completed BEFORE returning
            await on_event(tool_completed(session.id, tool_id, "success", str(result)))
            return str(result)
        except Exception as exc:
            completed_tools.add(tool_id)  # Mark as completed on error too
            error_msg = str(exc)
            await on_event(tool_completed(session.id, tool_id, "error", error_msg))
            return f"Error: {error_msg}"

    async def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool via the SandboxProvider with tool routing and recovery."""
        # Tool routing: log tool usage for performance tracking
        if tool_name not in self._tool_router.performance:
            self._tool_router.performance[tool_name] = ToolPerformance(tool_name=tool_name)
        self._tool_router.performance[tool_name].total_calls += 1
        self._tool_router.performance[tool_name].last_used = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())

        # MCP tools — try MCP registry first (before sandbox execution)
        try:
            registry = get_mcp_registry()
            if registry and registry.tools:
                # Only invoke MCP if this tool is actually provided by an MCP server
                mcp_tool_found = any(t.name == tool_name for t in registry.tools)
                if mcp_tool_found:
                    mcp_result = await registry.invoke_tool(tool_name, tool_input)
                    if mcp_result.success:
                        log.info(f"[MCP TOOL] {tool_name} → {len(mcp_result.content)} chars")
                        self._tool_router.performance[tool_name].successful_calls += 1
                        self._metabolism.record_tool_call()
                        return mcp_result.content
                    elif mcp_result.error:
                        # MCP tool exists but failed — report the error
                        log.warning(f"[MCP TOOL] {tool_name} failed: {mcp_result.error}")
                        self._tool_router.performance[tool_name].failed_calls += 1
                        return f"MCP error: {mcp_result.error}"
        except Exception as exc:
            log.warning(f"[MCP TOOL] {tool_name} dispatch failed: {exc}")

        # Web search tools — use unified search provider (SearXNG + Tavily fallback)
        if tool_name == "web_search":
            try:
                query = tool_input.get("query", "")
                max_results = tool_input.get("max_results", 5)
                if not query:
                    return "Error: web_search requires a 'query' parameter"
                log.info(f"[TOOL] web_search: {query[:100]}")
                response = await self._unified_search.search(query, max_results)
                if response.error:
                    return f"Search error: {response.error}"
                if not response.results:
                    return f"No results found for: {query}"
                # Format results for the LLM
                lines = [f"Found {response.total_results} results for '{query}':\n"]
                for i, r in enumerate(response.results, 1):
                    lines.append(f"{i}. {r.title}")
                    lines.append(f"   URL: {r.url}")
                    if r.content:
                        lines.append(f"   Snippet: {r.content[:300]}")
                    lines.append("")
                if response.answer:
                    lines.append(f"\nAI Answer: {response.answer[:500]}")
                result_text = "\n".join(lines)
                log.info(f"[TOOK] web_search → {len(result_text)} chars")
                self._tool_router.performance[tool_name].successful_calls += 1
                return result_text
            except Exception as exc:
                self._tool_router.performance[tool_name].failed_calls += 1
                self._tool_router.performance[tool_name].last_error = str(exc)
                log.error(f"[TOOL ERROR] web_search: {exc}", exc_info=True)
                return f"Error: {exc}"

        if tool_name == "web_extract":
            try:
                url = tool_input.get("url", "")
                if not url:
                    return "Error: web_extract requires a 'url' parameter"
                log.info(f"[TOOL] web_extract: {url[:100]}")
                # Use httpx to fetch and extract web content
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    # Simple extraction: strip HTML tags, return clean text
                    import re
                    text = re.sub(r'<[^>]+>', ' ', resp.text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if len(text) > 15000:
                        text = text[:15000] + "\n\n[... truncated]"
                    log.info(f"[TOOK] web_extract → {len(text)} chars")
                    self._tool_router.performance[tool_name].successful_calls += 1
                    return f"# {url}\n\n{text}"
            except Exception as exc:
                self._tool_router.performance[tool_name].failed_calls += 1
                self._tool_router.performance[tool_name].last_error = str(exc)
                log.error(f"[TOOL ERROR] web_extract: {exc}", exc_info=True)
                return f"Error: {exc}"

        try:
            # Chunked file writing for large content to avoid JSON parse errors
            if tool_name == "file_write":
                content = tool_input.get("content", "")
                if len(content) > 8192:
                    log.info(f"[TOOL] Writing large file in chunks: {tool_input.get('path', '?')} ({len(content)} bytes)")
                    # Write in chunks using bash heredoc
                    path = tool_input.get("path", "")
                    mode = tool_input.get("mode", "write")
                    actual_mode = "write"
                    for i in range(0, len(content), 8192):
                        chunk = content[i:i+8192]
                        cmd = f"cat > '{path}' << 'CHUNK_EOF'\n{chunk}\nCHUNK_EOF"
                        if actual_mode == "append":
                            cmd = f"cat >> '{path}' << 'CHUNK_EOF'\n{chunk}\nCHUNK_EOF"
                        result = self._sandbox.execute("bash", {"command": cmd})
                        actual_mode = "append"
                    self._tool_router.performance[tool_name].successful_calls += 1
                    return f"File written in {len(content)//8192 + 1} chunks ({len(content)} bytes)"

            result = self._sandbox.execute(tool_name, tool_input)
            log.info(f"[TOOK] {tool_name} → {len(str(result))} chars")
            self._tool_router.performance[tool_name].successful_calls += 1
            # Track tool call in metabolism engine
            self._metabolism.record_tool_call()
            return result
        except Exception as exc:
            self._tool_router.performance[tool_name].failed_calls += 1
            self._tool_router.performance[tool_name].last_error = str(exc)
            log.error(f"[TOOL ERROR] {tool_name}: {exc}", exc_info=True)
            raise RuntimeError(f"Tool execution failed: {exc}")

    async def _check_resources(self, session: LiveSession) -> None:
        """Check GPU temp, disk, VRAM and emit warnings if needed.

        Delegates to the MetabolismEngine for comprehensive resource monitoring.
        """
        try:
            state = self._metabolism.assess_health()
            # Emit resource warnings via event store if health degraded
            if state.overall_health.value in ("warning", "critical", "emergency"):
                await append_event(session.id, "resource.warning", {
                    "resource": "overall_health",
                    "level": state.overall_health.value,
                    "gpu_temp": state.gpu.temperature if state.gpu else 0,
                    "vram_pct": state.gpu.vram_pct if state.gpu else 0,
                    "disk_pct": state.system.disk_pct if state.system else 0,
                    "message": f"Resource health: {state.overall_health.value}",
                })
                log.warning(f"Resource health: {state.overall_health.value} "
                            f"(GPU: {state.gpu.temperature if state.gpu else 0}°C, "
                            f"VRAM: {state.gpu.vram_pct if state.gpu else 0}%, "
                            f"disk: {state.system.disk_pct if state.system else 0}%)")
        except Exception as exc:
            log.warning(f"Resource check failed: {exc}")

    async def interrupt(self, session: LiveSession) -> None:
        """Interrupt a running session."""
        # For llama.cpp SSE, we can't truly interrupt — mark as interrupted
        session.status = "interrupted"
        await append_event(session.id, "session.interrupted", {
            "message": "Session interrupted",
        })

    async def execute_parallel_tasks(
        self,
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Execute multiple tasks in parallel using the multi-agent orchestrator.

        Each task is a dict with 'description' and optionally 'priority' and
        'dependencies' (list of task IDs).

        Returns a dict with aggregated results.
        """
        task_ids = []
        for task in tasks:
            desc = task["description"]
            priority = task.get("priority", 0)
            deps = task.get("dependencies", [])
            task_id = self._orchestrator.create_task(desc, priority=priority, dependencies=deps)
            task_ids.append(task_id)

        result = self._orchestrator.execute_parallel(task_ids)
        reconciled = self._orchestrator.reconcile_results(result.results)
        reconciled["duration_seconds"] = result.total_duration_seconds
        return reconciled

    async def collect_inference_metrics(self) -> dict[str, Any]:
        """Collect inference engine metrics and store in memory.
        
        Returns:
            Dict of collected metrics.
        """
        if not self._inference_monitor:
            return {}
        
        try:
            state = await self._inference_monitor.collect_all_metrics()
            memory_entry = self._inference_monitor.to_memory_entry()
            
            # Store in memory system for self-improvement loop
            if self._memory_system:
                self._memory_system.add(
                    content=f"Inference metrics: {memory_entry['total_tokens_processed']:,.0f} tokens processed, "
                           f"{memory_entry['avg_cache_hit_rate']:.0%} cache hit rate, "
                           f"{memory_entry['high_priority_recommendations']} high-priority recommendations",
                    tier=MemoryTier.LONG_TERM,
                    hemisphere=Hemisphere.LEFT,
                    who="InferenceEngineMonitor",
                    what="metrics_collection",
                    why="Track inference performance for optimization",
                    how="Prometheus metrics from llama.cpp instances",
                    metadata=memory_entry,
                )
            
            log.info(f"[InferenceEngine] Collected metrics: {memory_entry['total_tokens_processed']:,.0f} tokens, "
                    f"{memory_entry['high_priority_recommendations']} high-priority recommendations")
            
            return memory_entry
        except Exception as exc:
            log.error(f"[InferenceEngine] Failed to collect metrics: {exc}", exc_info=True)
            return {}

    async def save_session_memory(self, session: LiveSession) -> None:
        """Save session context to file-based memory on session end."""
        # Extract key learnings from session
        if session.status == "ready":
            self._memory.add_memory(
                category="context",
                content=f"Session {session.id[:8]} completed successfully",
                source=session.id,
            )
        elif session.status == "failed":
            self._memory.add_memory(
                category="corrections",
                content=f"Session {session.id[:8]} failed — review error patterns",
                source=session.id,
            )

    async def _run_reflection_and_synthesis(
        self,
        session: LiveSession,
        prompt: str,
        outcome: str,
        tool_results: list[str],
    ) -> None:
        """Run reflection and synthesis after a session completes.

        This is the core of the self-improvement loop:
        1. Encode execution data into memory system
        2. Run active reflection on the data
        3. Synthesize insights into actionable guidance
        4. Store in experience replay for future cycles
        5. Accumulate guidance for next session

        Args:
            session: The completed LiveSession
            prompt: The original user prompt
            outcome: Session outcome ("success" or "failure")
            tool_results: List of tool execution results from the session
        """
        try:
            # Step 1: Encode execution data into memory system
            # Store the session as a direct experience entry
            execution_summary = (
                f"Session {session.id[:8]}: prompt='{prompt[:200]}', "
                f"outcome={outcome}, tools_used={len(tool_results)}"
            )
            self._memory_system.add(
                content=execution_summary,
                tier=MemoryTier.WORKING,
                hemisphere=Hemisphere.LEFT,
                is_novel=False,
                who="RuntimeSDK",
                what="session_execution",
                why=f"Direct experience from {outcome}",
                how="Encoded after session completion",
            )

            # Store tool results as direct experience
            for i, result in enumerate(tool_results):
                if result and len(result) > 10:
                    self._memory_system.add(
                        content=f"Tool result {i+1}: {result[:500]}",
                        tier=MemoryTier.LONG_TERM,
                        hemisphere=Hemisphere.LEFT,
                        is_novel=False,
                        who="RuntimeSDK",
                        what="tool_execution_result",
                        why="Direct observation of tool output",
                        how="Encoded after tool execution",
                    )

            # Step 2: Run active reflection
            reflection_state = self._reflection_engine.run_reflection(
                focus=f"Session {session.id[:8]}: {outcome}",
                max_memories=50,
            )

            # Step 3: Synthesize reflection into actionable guidance
            syntheses = self._synthesis_engine.process_reflection_session(
                session=reflection_state,
                thesis_context=prompt[:200],
            )

            # Step 4: Store actionable syntheses in experience replay
            for synth in syntheses:
                if synth.is_actionable and synth.confidence >= 0.7:
                    exp = self._experience_replay.store_from_synthesis(
                        synthesis=synth,
                        cycle_id=session.id[:8],
                        context="runtime_execution",
                    )
                    log.info(
                        f"[Self-Improvement] Stored experience: "
                        f"type={synth.insight_type}, confidence={synth.confidence:.2f}"
                    )

            # Step 5: Accumulate guidance for next session
            if syntheses:
                guidance_parts = []
                for synth in syntheses[:5]:  # Limit to top 5
                    if synth.is_actionable:
                        guidance_parts.append(
                            f"- {synth.insight_type}: {synth.synthesis[:200]}"
                        )

                if guidance_parts:
                    new_guidance = "\n\n[SYNTHESIS GUIDANCE — Incorporate these insights]\n" + "\n".join(guidance_parts)
                    self._synthesis_guidance += new_guidance
                    log.info(
                        f"[Self-Improvement] Synthesis guidance updated: "
                        f"{len(syntheses)} insights, {len(guidance_parts)} actionable"
                    )

        except Exception as exc:
            log.error(f"[Self-Improvement] Reflection/synthesis failed: {exc}", exc_info=True)

    def get_synthesis_guidance(self) -> str:
        """Get accumulated synthesis guidance for the next session."""
        return self._synthesis_guidance
