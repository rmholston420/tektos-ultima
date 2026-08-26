"""Tests for src/tektos/runtime/tool_router.py

Covers: ToolCategory, ErrorType, ToolCapability, ToolPerformance, ToolRoute,
ToolRouter (routing, execution with recovery, error classification, stats).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tektos.runtime.tool_router import (
    ToolCategory,
    ErrorType,
    ToolCapability,
    ToolPerformance,
    ToolRoute,
    ToolRouter,
)


# ── ToolCategory ─────────────────────────────────────────────────────────────

class TestToolCategory:
    def test_all_categories_exist(self):
        assert ToolCategory.FILE_OPERATIONS.value == "file_operations"
        assert ToolCategory.TERMINAL.value == "terminal"
        assert ToolCategory.BROWSER.value == "browser"
        assert ToolCategory.SEARCH.value == "search"
        assert ToolCategory.DELEGATION.value == "delegation"
        assert ToolCategory.MEMORY.value == "memory"
        assert ToolCategory.COMPUTER_USE.value == "computer_use"


# ── ErrorType ────────────────────────────────────────────────────────────────

class TestErrorType:
    def test_all_error_types_exist(self):
        assert ErrorType.TIMEOUT.value == "timeout"
        assert ErrorType.PERMISSION.value == "permission"
        assert ErrorType.NETWORK.value == "network"
        assert ErrorType.SYNTAX.value == "syntax"
        assert ErrorType.RUNTIME.value == "runtime"
        assert ErrorType.RESOURCE.value == "resource"
        assert ErrorType.UNKNOWN.value == "unknown"


# ── ToolCapability ───────────────────────────────────────────────────────────

class TestToolCapability:
    def test_creation(self):
        cap = ToolCapability(
            tool_name="terminal",
            category=ToolCategory.TERMINAL,
            description="Execute shell commands",
            max_retries=3,
            timeout_seconds=300,
            fallback_tools=["execute_code"],
            requires_permission=False,
        )
        assert cap.tool_name == "terminal"
        assert cap.category == ToolCategory.TERMINAL
        assert cap.max_retries == 3
        assert cap.timeout_seconds == 300
        assert cap.fallback_tools == ["execute_code"]
        assert cap.requires_permission is False

    def test_default_fallback_tools(self):
        cap = ToolCapability(
            tool_name="read_file",
            category=ToolCategory.FILE_OPERATIONS,
            description="Read file contents",
        )
        assert cap.fallback_tools == []
        assert cap.max_retries == 3
        assert cap.timeout_seconds == 300
        assert cap.requires_permission is False


# ── ToolPerformance ──────────────────────────────────────────────────────────

class TestToolPerformance:
    def test_default_values(self):
        perf = ToolPerformance(tool_name="terminal")
        assert perf.total_calls == 0
        assert perf.successful_calls == 0
        assert perf.failed_calls == 0
        assert perf.total_duration_seconds == 0.0
        assert perf.last_error == ""
        assert perf.last_used == ""

    def test_success_rate_zero_calls(self):
        perf = ToolPerformance(tool_name="terminal")
        assert perf.success_rate == 0.0

    def test_success_rate_all_success(self):
        perf = ToolPerformance(tool_name="terminal")
        perf.total_calls = 10
        perf.successful_calls = 10
        assert perf.success_rate == 1.0

    def test_success_rate_mixed(self):
        perf = ToolPerformance(tool_name="terminal")
        perf.total_calls = 10
        perf.successful_calls = 7
        assert perf.success_rate == 0.7

    def test_success_rate_all_fail(self):
        perf = ToolPerformance(tool_name="terminal")
        perf.total_calls = 5
        perf.failed_calls = 5
        assert perf.success_rate == 0.0

    def test_average_duration_zero_calls(self):
        perf = ToolPerformance(tool_name="terminal")
        assert perf.average_duration == 0.0

    def test_average_duration(self):
        perf = ToolPerformance(tool_name="terminal")
        perf.total_calls = 4
        perf.total_duration_seconds = 2.0
        assert perf.average_duration == 0.5


# ── ToolRoute ────────────────────────────────────────────────────────────────

class TestToolRoute:
    def test_creation(self):
        route = ToolRoute(
            primary_tool="terminal",
            fallback_tools=["execute_code"],
            category=ToolCategory.TERMINAL,
            confidence=0.95,
            reason="Shell command execution",
        )
        assert route.primary_tool == "terminal"
        assert route.fallback_tools == ["execute_code"]
        assert route.category == ToolCategory.TERMINAL
        assert route.confidence == 0.95
        assert route.reason == "Shell command execution"

    def test_default_values(self):
        route = ToolRoute(
            primary_tool="terminal",
            fallback_tools=[],
            category=ToolCategory.TERMINAL,
        )
        assert route.confidence == 1.0
        assert route.reason == ""


# ── ToolRouter ───────────────────────────────────────────────────────────────

class TestToolRouter:
    def test_init_default_capabilities(self):
        router = ToolRouter()
        assert len(router.capabilities) == 7
        assert "terminal" in router.capabilities
        assert "execute_code" in router.capabilities
        assert "read_file" in router.capabilities
        assert "write_file" in router.capabilities
        assert "search_files" in router.capabilities
        assert "web_search" in router.capabilities
        assert "delegate_task" in router.capabilities

    def test_init_default_performance(self):
        router = ToolRouter()
        assert len(router.performance) == 7
        for tool_name in router.capabilities:
            assert tool_name in router.performance

    def test_init_with_embedder(self):
        mock_embedder = MagicMock()
        router = ToolRouter(embedder_client=mock_embedder)
        assert router._embedder is mock_embedder

    def test_init_without_embedder(self):
        router = ToolRouter()
        assert router._embedder is None

    def test_route_tool_terminal(self):
        router = ToolRouter()
        route = router.route_tool("run a shell command")
        assert route.primary_tool == "terminal"
        assert route.category == ToolCategory.TERMINAL
        assert "shell command execution" in route.reason

    def test_route_tool_execute_code(self):
        router = ToolRouter()
        route = router.route_tool("execute python code")
        assert route.primary_tool == "terminal"  # "execute" matches terminal first
        assert route.category == ToolCategory.TERMINAL

    def test_route_tool_read_file(self):
        router = ToolRouter()
        route = router.route_tool("read the file contents")
        assert route.primary_tool == "read_file"
        assert route.category == ToolCategory.FILE_OPERATIONS

    def test_route_tool_write_file(self):
        router = ToolRouter()
        route = router.route_tool("write a new file")
        assert route.primary_tool == "write_file"
        assert route.category == ToolCategory.FILE_OPERATIONS

    def test_route_tool_search_files(self):
        router = ToolRouter()
        route = router.route_tool("search for patterns in files")
        assert route.primary_tool == "search_files"
        assert route.category == ToolCategory.SEARCH

    def test_route_tool_web_search(self):
        router = ToolRouter()
        route = router.route_tool("look up information on the internet")
        assert route.primary_tool == "web_search"
        assert route.category == ToolCategory.SEARCH

    def test_route_tool_delegate(self):
        router = ToolRouter()
        route = router.route_tool("delegate this task to a subagent")
        assert route.primary_tool == "delegate_task"
        assert route.category == ToolCategory.DELEGATION

    def test_route_tool_default(self):
        router = ToolRouter()
        route = router.route_tool("do something unknown")
        assert route.primary_tool == "terminal"
        assert route.category == ToolCategory.TERMINAL
        assert "Default routing" in route.reason

    def test_execute_tool_success(self):
        router = ToolRouter()
        result = router.execute_with_recovery("read_file", {"path": "/test.py"})
        assert result["success"] is True
        assert result["tool"] == "read_file"
        assert "Executed read_file" in result["result"]

    def test_execute_tool_unknown_raises(self):
        router = ToolRouter()
        with pytest.raises(ValueError, match="Unknown tool"):
            router.execute_with_recovery("nonexistent_tool", {})

    def test_execute_tool_tracks_performance(self):
        router = ToolRouter()
        router.execute_with_recovery("read_file", {"path": "/test.py"})
        perf = router.performance["read_file"]
        assert perf.total_calls == 1
        assert perf.successful_calls == 1
        assert perf.last_error == ""

    def test_execute_tool_failure_tracks_performance(self):
        router = ToolRouter()
        # Override _execute_tool to raise
        def failing_execute(tool_name, args):
            raise RuntimeError("File not found")
        router._execute_tool = failing_execute

        result = router.execute_with_recovery("read_file", {"path": "/missing.py"}, max_retries=1)
        assert result["success"] is False
        assert result["error"] == "File not found"
        perf = router.performance["read_file"]
        assert perf.failed_calls == 1
        assert perf.last_error == "File not found"

    def test_execute_tool_retry_on_failure(self):
        router = ToolRouter()
        call_count = [0]
        def flaky_execute(tool_name, args):
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("Transient error")
            return {"success": True, "tool": tool_name}
        router._execute_tool = flaky_execute

        result = router.execute_with_recovery("read_file", {"path": "/test.py"}, max_retries=3)
        assert result["success"] is True
        assert call_count[0] == 3

    def test_execute_tool_exhausts_retries(self):
        router = ToolRouter()
        def always_fails(tool_name, args):
            raise RuntimeError("Permanent error")
        router._execute_tool = always_fails

        result = router.execute_with_recovery("read_file", {"path": "/test.py"}, max_retries=2)
        assert result["success"] is False
        assert result["error"] == "Permanent error"
        assert result["attempts"] == 2

    def test_classify_error_timeout(self):
        router = ToolRouter()
        assert router._classify_error(Exception("Operation timed out")) == ErrorType.TIMEOUT
        assert router._classify_error(Exception("timeout")) == ErrorType.TIMEOUT

    def test_classify_error_permission(self):
        router = ToolRouter()
        assert router._classify_error(Exception("Permission denied")) == ErrorType.PERMISSION
        assert router._classify_error(Exception("access denied")) == ErrorType.PERMISSION

    def test_classify_error_network(self):
        router = ToolRouter()
        assert router._classify_error(Exception("Network error")) == ErrorType.NETWORK
        assert router._classify_error(Exception("connection refused")) == ErrorType.NETWORK

    def test_classify_error_syntax(self):
        router = ToolRouter()
        assert router._classify_error(Exception("Syntax error")) == ErrorType.SYNTAX
        assert router._classify_error(Exception("invalid argument")) == ErrorType.SYNTAX

    def test_classify_error_resource(self):
        router = ToolRouter()
        assert router._classify_error(Exception("Out of memory")) == ErrorType.RESOURCE
        assert router._classify_error(Exception("disk full")) == ErrorType.RESOURCE

    def test_classify_error_unknown(self):
        router = ToolRouter()
        assert router._classify_error(Exception("Something weird happened")) == ErrorType.UNKNOWN

    def test_apply_recovery_strategy_timeout(self):
        router = ToolRouter()
        # Should not raise
        router._apply_recovery_strategy(ErrorType.TIMEOUT, "terminal", {})

    def test_apply_recovery_strategy_permission(self):
        router = ToolRouter()
        # Should not raise
        router._apply_recovery_strategy(ErrorType.PERMISSION, "terminal", {})

    def test_apply_recovery_strategy_network(self):
        router = ToolRouter()
        # Should not raise
        router._apply_recovery_strategy(ErrorType.NETWORK, "terminal", {})

    def test_apply_recovery_strategy_resource(self):
        router = ToolRouter()
        # Should not raise
        router._apply_recovery_strategy(ErrorType.RESOURCE, "terminal", {})

    def test_get_tool_stats(self):
        router = ToolRouter()
        router.execute_with_recovery("read_file", {"path": "/test.py"})
        stats = router.get_tool_stats()
        assert "read_file" in stats
        assert stats["read_file"]["total_calls"] == 1
        assert "100.0%" in stats["read_file"]["success_rate"]
        assert "None" in stats["read_file"]["last_error"]

    def test_get_tool_stats_empty(self):
        router = ToolRouter()
        stats = router.get_tool_stats()
        assert len(stats) == 7

    def test_get_best_tool_for_task_default(self):
        router = ToolRouter()
        tool = router.get_best_tool_for_task("run a command")
        assert tool == "terminal"

    def test_get_best_tool_for_task_prefers_high_success(self):
        router = ToolRouter()
        # Set primary tool to have low success rate
        router.performance["terminal"].total_calls = 10
        router.performance["terminal"].successful_calls = 1  # 10% success
        # Set fallback to have high success rate
        router.performance["execute_code"].total_calls = 10
        router.performance["execute_code"].successful_calls = 10  # 100% success

        tool = router.get_best_tool_for_task("run a command")
        assert tool == "execute_code"

    def test_get_best_tool_for_task_fallback_not_better(self):
        router = ToolRouter()
        # Both have low success rate
        router.performance["terminal"].total_calls = 10
        router.performance["terminal"].successful_calls = 1
        router.performance["execute_code"].total_calls = 10
        router.performance["execute_code"].successful_calls = 1

        tool = router.get_best_tool_for_task("run a command")
        assert tool == "terminal"  # defaults to primary

    @pytest.mark.asyncio
    async def test_get_tool_embedding_no_embedder(self):
        router = ToolRouter()
        result = await router._get_tool_embedding("terminal")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_tool_embedding_no_cache(self):
        mock_embedder = MagicMock()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1, 0.2, 0.3]]
        mock_embedder.embed = AsyncMock(return_value=mock_result)
        router = ToolRouter(embedder_client=mock_embedder)
        vec = await router._get_tool_embedding("terminal")
        assert vec == [0.1, 0.2, 0.3]
        # Should be cached
        assert "terminal" in router._tool_embedding_cache

    @pytest.mark.asyncio
    async def test_get_tool_embedding_cached(self):
        mock_embedder = MagicMock()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1, 0.2, 0.3]]
        mock_embedder.embed = AsyncMock(return_value=mock_result)
        router = ToolRouter(embedder_client=mock_embedder)
        # First call
        await router._get_tool_embedding("terminal")
        # Second call should use cache
        vec = await router._get_tool_embedding("terminal")
        assert vec == [0.1, 0.2, 0.3]
        mock_embedder.embed.assert_called_once()  # Only called once

    @pytest.mark.asyncio
    async def test_get_tool_embedding_embedder_error(self):
        mock_embedder = MagicMock()
        mock_embedder.embed = AsyncMock(side_effect=Exception("Embedding failed"))
        router = ToolRouter(embedder_client=mock_embedder)
        result = await router._get_tool_embedding("terminal")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_tool_embedding_unknown_tool(self):
        mock_embedder = MagicMock()
        router = ToolRouter(embedder_client=mock_embedder)
        result = await router._get_tool_embedding("nonexistent")
        assert result is None
        mock_embedder.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_semantic_route_tool_no_embedder(self):
        router = ToolRouter()
        route = await router.semantic_route_tool("run a command")
        assert route.primary_tool == "terminal"  # Falls back to heuristic

    @pytest.mark.asyncio
    async def test_semantic_route_tool_embedder_no_embeddings(self):
        mock_embedder = MagicMock()
        mock_result = MagicMock()
        mock_result.embeddings = []
        mock_embedder.embed = AsyncMock(return_value=mock_result)
        router = ToolRouter(embedder_client=mock_embedder)
        route = await router.semantic_route_tool("run a command")
        assert route.primary_tool == "terminal"  # Falls back to heuristic

    @pytest.mark.asyncio
    async def test_semantic_route_tool_with_embeddings(self):
        mock_embedder = MagicMock()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.9, 0.1, 0.1]]  # High similarity to terminal
        mock_embedder.embed = AsyncMock(return_value=mock_result)
        router = ToolRouter(embedder_client=mock_embedder)
        route = await router.semantic_route_tool("run a command")
        assert route.primary_tool == "terminal"
        assert "Embedding similarity" in route.reason

    def test_execute_with_recovery_custom_max_retries(self):
        router = ToolRouter()
        call_count = [0]
        def flaky(tool_name, args):
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("Transient")
            return {"success": True}
        router._execute_tool = flaky

        result = router.execute_with_recovery("read_file", {}, max_retries=5)
        assert result["success"] is True
        assert call_count[0] == 2

    def test_execute_with_recovery_uses_capability_max_retries(self):
        router = ToolRouter()
        call_count = [0]
        def always_fails(tool_name, args):
            call_count[0] += 1
            raise RuntimeError("Error")
        router._execute_tool = always_fails

        # read_file has max_retries=3
        result = router.execute_with_recovery("read_file", {})
        assert result["success"] is False
        assert call_count[0] == 3

    def test_execute_with_recovery_no_max_retries_param(self):
        router = ToolRouter()
        call_count = [0]
        def always_fails(tool_name, args):
            call_count[0] += 1
            raise RuntimeError("Error")
        router._execute_tool = always_fails

        # delegate_task has max_retries=2
        result = router.execute_with_recovery("delegate_task", {})
        assert result["success"] is False
        assert call_count[0] == 2
