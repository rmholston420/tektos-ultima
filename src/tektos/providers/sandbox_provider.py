"""SandboxProvider — real tool execution for the agent loop.

Provides safe execution of bash commands, file operations, and search
within a configurable filesystem root (TEKTOS_FS_ROOT env var).

Tools:
  - bash: Execute shell commands
  - file_read: Read files
  - file_write: Write files (with append mode)
  - file_delete: Delete files
  - directory_list: List directory contents
  - directory_create: Create directories
  - search: Search file contents (grep-like)
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger("tektos.sandbox")

# FS_ROOT configurable via env var (PlexClaw bug #12 fix)
# Expanded to allow /tmp/, /app/, /usr/local/bin/ for Terminal-Bench tasks
FS_ROOT = Path(os.getenv("TEKTOS_FS_ROOT", "/")).resolve()

# Security: max execution time for bash commands (seconds)
# Increased from 30s to 300s for downloads, builds, and multi-step operations
BASH_TIMEOUT = int(os.getenv("TEKTOS_BASH_TIMEOUT", "300"))


def _docker_exec(container: str, command: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """Execute a shell command inside a Docker container via docker exec.

    Used by the Terminal-Bench integration to proxy tool execution into
    per-task containers managed by Harbor. The command runs as root in
    the container with /app as working directory (TB convention).
    """
    return subprocess.run(
        ["docker", "exec", "-w", "/app", container, "bash", "-c", command],
        shell=False, capture_output=True, text=True, timeout=timeout,
    )

# Security: max output size (bytes)
MAX_OUTPUT_SIZE = 100_000


class SandboxProvider:
    """Execute tools safely within a filesystem root sandbox."""

    def __init__(
        self,
        fs_root: Path | None = None,
        bash_timeout: int = BASH_TIMEOUT,
        max_output_size: int = MAX_OUTPUT_SIZE,
        docker_container: str | None = None,
    ) -> None:
        self.fs_root = (fs_root or FS_ROOT).resolve()
        self.bash_timeout = bash_timeout
        self.max_output_size = max_output_size
        # When set, all file/bash operations are proxied into this Docker
        # container via `docker exec` (Terminal-Bench Harbor integration).
        self.docker_container = docker_container

        # Verify sandbox root exists
        if not self.fs_root.exists():
            log.warning("Sandbox root %s does not exist, creating it", self.fs_root)
            self.fs_root.mkdir(parents=True, exist_ok=True)

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool by name with given input. Returns result string."""
        handlers = {
            "bash": self._execute_bash,
            "file_read": self._file_read,
            "file_write": self._file_write,
            "file_delete": self._file_delete,
            "directory_list": self._directory_list,
            "directory_create": self._directory_create,
            "search": self._search,
            "web_search": self._web_search,
            "web_extract": self._web_extract,
            "web_fetch": self._web_fetch,
            "rag_query": self._rag_query,
            "delegate_task": self._delegate_task,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return f"Unknown tool: {tool_name}"

        try:
            result = handler(tool_input)
            return result
        except Exception as exc:
            log.error(f"Tool {tool_name} failed: {exc}", exc_info=True)
            return f"Error: {exc}"

    # ------------------------------------------------------------------
    # Bash execution
    # ------------------------------------------------------------------

    def _execute_bash(self, params: dict[str, Any]) -> str:
        """Execute a shell command within timeout.

        Recovery behaviors (added for Terminal-Bench task success):
        - If the command fails with a permission error and does not already
          use sudo, automatically retry once with `sudo -n` (passwordless).
        - If the command fails with PEP 668 (externally-managed-environment),
          append a hint suggesting --break-system-packages or pipx/venv.
        """
        command = params.get("command", "")
        if not command:
            return "Error: No command provided"

        log.info(f"[TOOL: bash] {command[:200]}")
        note = ""

        # Terminal-Bench mode: proxy into the task's Docker container.
        if self.docker_container:
            try:
                result = _docker_exec(self.docker_container, command, timeout=self.bash_timeout)
                output = (result.stdout or "") + ((("\n" + result.stderr) if result.stderr else ""))
                return f"Exit {result.returncode}: {'success' if result.returncode == 0 else 'failed'}\n{output[:self.max_output_size]}"
            except subprocess.TimeoutExpired:
                return f"Error: Command timed out after {self.bash_timeout}s"
            except Exception as exc:
                return f"Error executing command in container: {exc}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.bash_timeout,
                cwd=str(self.fs_root),
            )

            # Permission denied without sudo -> auto-retry with sudo -n.
            # Piping to tail/head masks the exit code (pipe status = last
            # segment), so detect permission errors from the output text too.
            combined_out = (result.stdout or "") + (result.stderr or "")
            if (
                "sudo" not in command.split()[0:2]
                and (
                    (result.returncode != 0 and self._is_permission_error(result))
                    or ("are you root?" in combined_out)
                )
            ):
                log.info(f"[TOOL: bash] permission error, retrying with sudo -n")
                sudo_cmd = f"sudo -n {command}"
                result = subprocess.run(
                    sudo_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=self.bash_timeout,
                    cwd=str(self.fs_root),
                )
                if "interactive authentication is required" in (result.stdout or "") + (result.stderr or ""):
                    note = (
                        "[auto-retried with sudo -n, but passwordless sudo is NOT available]\n"
                        "You do NOT have root access on this system. Do NOT attempt sudo again.\n"
                        "Work around it: install Python packages with pip --break-system-packages, "
                        "use user-level tools, or write code that avoids needing root.\n"
                    )
                else:
                    note = "[auto-retried with sudo -n]\n"

            output = ""
            if result.stdout:
                output += result.stdout[: self.max_output_size]
            if result.stderr:
                if output:
                    output += "\n--- stderr ---\n"
                output += result.stderr[: self.max_output_size]

            exit_code = result.returncode
            status = "success" if exit_code == 0 else "failed"

            # PEP 668 hint: pip install blocked by externally-managed-environment
            if exit_code != 0 and "externally-managed-environment" in output:
                output += (
                    "\n[HINT] This system uses PEP 668. To install a Python package, "
                    "use one of:\n"
                    "  pip install --break-system-packages <pkg>\n"
                    "  pipx install <pkg>\n"
                    "  python3 -m venv /tmp/venv && /tmp/venv/bin/pip install <pkg>\n"
                )

            return f"{note}Exit {exit_code}: {status}\n{output}" if note else f"Exit {exit_code}: {status}\n{output}"

        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {self.bash_timeout}s"
        except Exception as exc:
            return f"Error executing command: {exc}"

    @staticmethod
    def _is_permission_error(result: subprocess.CompletedProcess) -> bool:
        """Detect permission-denied style failures in output."""
        text = (result.stdout or "") + (result.stderr or "")
        markers = (
            "Permission denied",
            "permission denied",
            "are you root?",
            "requires root",
            "insufficient permissions",
            "dpkg frontend lock",
            "interactive authentication is required",
        )
        return any(m in text for m in markers)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _file_read(self, params: dict[str, Any]) -> str:
        """Read file content with path validation."""
        file_path = params.get("path", "")
        if not file_path:
            return "Error: No path provided"

        # Terminal-Bench mode: read from the task container.
        if self.docker_container:
            try:
                result = _docker_exec(self.docker_container, f"cat {file_path} 2>&1", timeout=30)
                if result.returncode != 0:
                    return f"Error: File not found: {file_path}"
                content = result.stdout or ""
                if len(content) > self.max_output_size:
                    content = content[: self.max_output_size] + "\n... (truncated)"
                return content
            except Exception as exc:
                return f"Error reading file in container: {exc}"

        resolved = self._safe_path(file_path)
        if not resolved:
            return f"Error: Path '{file_path}' is outside sandbox"

        if not resolved.exists():
            return f"Error: File not found: {file_path}"

        if not resolved.is_file():
            return f"Error: Not a file: {file_path}"

        try:
            content = resolved.read_text(encoding="utf-8", errors="replace")
            # Truncate if too large
            if len(content) > self.max_output_size:
                content = content[: self.max_output_size] + "\n... (truncated)"
            return content
        except Exception as exc:
            return f"Error reading file: {exc}"

    def _file_write(self, params: dict[str, Any]) -> str:
        """Write file content with path validation."""
        file_path = params.get("path", "")
        content = params.get("content", "")
        mode = params.get("mode", "write")  # "write" or "append"

        if not file_path:
            return "Error: No path provided"

        resolved = self._safe_path(file_path)
        if not resolved:
            return f"Error: Path '{file_path}' is outside sandbox"

        # Create parent directories
        resolved.parent.mkdir(parents=True, exist_ok=True)

        try:
            if mode == "append":
                existing = resolved.read_text(encoding="utf-8", errors="replace")
                resolved.write_text(existing + content, encoding="utf-8")
            else:
                resolved.write_text(content, encoding="utf-8")

            log.info(f"[TOOL: file_write] {file_path} ({len(content)} bytes)")
            return f"Written {len(content)} bytes to {file_path}"

        except Exception as exc:
            return f"Error writing file: {exc}"

    def _file_delete(self, params: dict[str, Any]) -> str:
        """Delete a file or directory."""
        file_path = params.get("path", "")
        if not file_path:
            return "Error: No path provided"

        resolved = self._safe_path(file_path)
        if not resolved:
            return f"Error: Path '{file_path}' is outside sandbox"

        try:
            if resolved.is_dir():
                shutil.rmtree(resolved)
                log.info(f"[TOOL: file_delete] Deleted directory: {file_path}")
                return f"Deleted directory: {file_path}"
            else:
                resolved.unlink()
                log.info(f"[TOOL: file_delete] Deleted file: {file_path}")
                return f"Deleted file: {file_path}"

        except Exception as exc:
            return f"Error deleting: {exc}"

    def _directory_list(self, params: dict[str, Any]) -> str:
        """List directory contents."""
        dir_path = params.get("path", ".")
        resolved = self._safe_path(dir_path)
        if not resolved:
            return f"Error: Path '{dir_path}' is outside sandbox"

        if not resolved.exists():
            return f"Error: Path not found: {dir_path}"

        if not resolved.is_dir():
            return f"Error: Not a directory: {dir_path}"

        try:
            entries = sorted(resolved.iterdir())
            lines = []
            for entry in entries:
                suffix = "/" if entry.is_dir() else ""
                lines.append(f"{'DIR' if entry.is_dir() else 'FILE'} {entry.name}{suffix}")
            return "\n".join(lines) if lines else "(empty directory)"
        except Exception as exc:
            return f"Error listing directory: {exc}"

    def _directory_create(self, params: dict[str, Any]) -> str:
        """Create directory (and parents)."""
        dir_path = params.get("path", "")
        if not dir_path:
            return "Error: No path provided"

        resolved = self._safe_path(dir_path)
        if not resolved:
            return f"Error: Path '{dir_path}' is outside sandbox"

        try:
            resolved.mkdir(parents=True, exist_ok=True)
            return f"Created directory: {dir_path}"
        except Exception as exc:
            return f"Error creating directory: {exc}"

    def _search(self, params: dict[str, Any]) -> str:
        """Search file contents (grep-like)."""
        query = params.get("query", "")
        path = params.get("path", ".")
        case_sensitive = params.get("case_sensitive", False)
        max_results = params.get("max_results", 50)

        if not query:
            return "Error: No search query provided"

        resolved = self._safe_path(path)
        if not resolved:
            return f"Error: Path '{path}' is outside sandbox"

        if not resolved.exists():
            return f"Error: Path not found: {path}"

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(re.escape(query), flags)

            matches = []
            if resolved.is_file():
                matches = self._search_file(resolved, pattern, max_results)
            elif resolved.is_dir():
                for root, dirs, files in resolved.walk():
                    for name in files:
                        if name.startswith("."):
                            continue
                        file_path = root / name
                        matches.extend(self._search_file(file_path, pattern, max_results - len(matches)))
                        if len(matches) >= max_results:
                            break
                    if len(matches) >= max_results:
                        break

            if not matches:
                return f"No matches for '{query}'"

            results = []
            for file_path, line_num, line in matches:
                results.append(f"{file_path}:{line_num}: {line.strip()}")
            return "\n".join(results)

        except Exception as exc:
            return f"Error searching: {exc}"

    def _search_file(self, file_path: Path, pattern: re.Pattern, limit: int) -> list[tuple]:
        """Search a single file for pattern matches."""
        matches = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(content.split("\n"), 1):
                if pattern.search(line):
                    matches.append((str(file_path), i, line))
                    if len(matches) >= limit:
                        break
        except Exception as e:
            log.warning("Sandbox operation failed: %s", e)
        return matches

    # ------------------------------------------------------------------
    # Web tools
    # ------------------------------------------------------------------

    def _web_search(self, params: dict[str, Any]) -> str:
        """Search the web using SearXNG or curl fallback."""
        query = params.get("query", "")
        if not query:
            return "Error: No query provided"

        # Try SearXNG first (if configured)
        searxng_url = os.getenv("TEKTOS_SEARXNG_URL", "")
        if searxng_url:
            try:
                import urllib.request
                import urllib.parse
                import json

                search_url = f"{searxng_url}?q={urllib.parse.quote(query)}&format=json"
                req = urllib.request.Request(search_url, headers={"User-Agent": "Tektos-Agent/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())

                results = data.get("results", [])
                if results:
                    lines = []
                    for i, r in enumerate(results[:5], 1):
                        lines.append(f"{i}. {r.get('title', 'N/A')}")
                        lines.append(f"   URL: {r.get('url', 'N/A')}")
                        lines.append(f"   {r.get('content', 'N/A')[:200]}")
                        lines.append("")
                    return "\n".join(lines) or "No results found"
            except Exception as e:
                log.warning(f"SearXNG search failed: {e}")

        # Fallback: use curl to search via a public API
        try:
            import urllib.parse as _urllib_parse
            result = subprocess.run(
                f'curl -s --max-time 15 "https://html.duckduckgo.com/html/?q={_urllib_parse.quote(query)}" 2>/dev/null | grep -oP \'(?<=<a rel="nofollow" href=")[^"]+\' | head -5',
                shell=True, capture_output=True, text=True, timeout=20,
            )
            if result.stdout.strip():
                urls = result.stdout.strip().split("\n")
                lines = [f"Search results for '{query}':"]
                for i, url in enumerate(urls, 1):
                    lines.append(f"{i}. {url}")
                return "\n".join(lines)
            return "No results found"
        except Exception as e:
            return f"Error: {e}"

    def _web_extract(self, params: dict[str, Any]) -> str:
        """Extract content from web page URLs using curl."""
        urls = params.get("urls", [])
        if not urls:
            return "Error: No URLs provided"

        results = []
        for url in urls[:5]:
            try:
                result = subprocess.run(
                    f'curl -s --max-time 15 -L -A "Mozilla/5.0" "{url}" 2>/dev/null | head -c 50000',
                    shell=True, capture_output=True, text=True, timeout=20,
                )
                content = result.stdout.strip()
                if content:
                    results.append(f"=== {url} ===\n{content[:5000]}")
                else:
                    results.append(f"=== {url} ===\n(No content retrieved)")
            except Exception as e:
                results.append(f"=== {url} ===\nError: {e}")

        return "\n\n".join(results)

    def _web_fetch(self, params: dict[str, Any]) -> str:
        """Fetch a URL using curl. Can download files or return content."""
        url = params.get("url", "")
        if not url:
            return "Error: No URL provided"

        output_path = params.get("output_path", "")
        headers = params.get("headers", "")
        max_bytes = params.get("max_bytes", 100000)

        curl_cmd = f'curl -s --max-time 60 -L -A "Mozilla/5.0"'
        if headers:
            curl_cmd += f' -H "{headers}"'

        if output_path:
            # Download to file
            resolved = Path(output_path).resolve()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            curl_cmd += f' -o "{resolved}"'
            result = subprocess.run(curl_cmd + f' "{url}"', shell=True, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and resolved.exists():
                size = resolved.stat().st_size
                return f"Downloaded {size} bytes to {output_path}"
            else:
                return f"Download failed (exit {result.returncode}): {result.stderr[:500]}"
        else:
            # Return content as text
            result = subprocess.run(curl_cmd + f' "{url}"', shell=True, capture_output=True, text=True, timeout=60)
            content = result.stdout[:max_bytes]
            if result.returncode != 0:
                return f"Fetch failed (exit {result.returncode}): {result.stderr[:500]}"
            return content[:max_bytes]

    # ------------------------------------------------------------------
    # RAG tool
    # ------------------------------------------------------------------

    def _rag_query(self, params: dict[str, Any]) -> str:
        """Query the RAG knowledge base (synchronous fallback)."""
        query = params.get("query", "")
        limit = params.get("limit", 5)
        if not query:
            return "Error: No query provided"

        # Try async RAG retriever via asyncio
        try:
            import asyncio as _asyncio
            from tektos.runtime.rag_retriever import get_rag_retriever
            retriever = get_rag_retriever()
            if retriever and retriever._initialized:
                results = _asyncio.run(retriever.retrieve(query, top_k=limit))
                if results:
                    lines = []
                    for i, r in enumerate(results[:limit], 1):
                        lines.append(f"{i}. [{r.source}] {r.content[:300]}")
                    return "\n".join(lines)
                return "No results found in knowledge base"
        except Exception as exc:
            log.warning(f"RAG query failed: {exc}")

        # Fallback: search SQLite FTS5 memory database directly
        try:
            import sqlite3
            db_path = Path("/home/rmholston/dev/tektos-ultima-v1/data/memory.db")
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                # Search long-term memory with FTS5
                cursor.execute(
                    "SELECT content FROM long_term_memory WHERE content MATCH ? LIMIT ?",
                    (query, limit),
                )
                rows = cursor.fetchall()
                conn.close()
                if rows:
                    lines = [f"Knowledge base results for '{query}':"]
                    for i, (content,) in enumerate(rows, 1):
                        lines.append(f"{i}. {content[:300]}")
                    return "\n".join(lines)
        except Exception as exc2:
            log.warning(f"Fallback memory search failed: {exc2}")

        return "Knowledge base unavailable or empty. Try web_search for external information."

    # ------------------------------------------------------------------
    # Delegation tool
    # ------------------------------------------------------------------

    def _delegate_task(self, params: dict[str, Any]) -> str:
        """Spawn a subagent to work on a subtask."""
        goal = params.get("goal", "")
        context = params.get("context", "")
        timeout = params.get("timeout", 600)

        if not goal:
            return "Error: No goal provided"

        # Use the Tektos API to spawn a subagent
        try:
            import urllib.request
            import urllib.parse
            import json

            data = json.dumps({
                "goal": goal,
                "context": context,
                "timeout": timeout,
            }).encode()

            req = urllib.request.Request(
                "http://localhost:8020/api/delegate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                subagent_id = result.get("subagent_id", result.get("id", "unknown"))
                return f"Subagent spawned: {subagent_id}. Goal: {goal}"
        except Exception as e:
            return f"Delegation failed: {e}. Note: subagent spawning requires the delegation API endpoint."

    # ------------------------------------------------------------------
    # Security: path validation
    # ------------------------------------------------------------------

    def _safe_path(self, path: str) -> Path | None:
        """Resolve and validate a path is within the sandbox root."""
        if not path:
            return None

        resolved = (self.fs_root / path).resolve()

        # Security: ensure path is within sandbox root
        if not str(resolved).startswith(str(self.fs_root)):
            log.warning(f"Path escape attempt: {path} -> {resolved}")
            return None

        return resolved


# Singleton instance for global use
sandbox = SandboxProvider()
