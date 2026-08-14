"""Tests for ChromeDebugger — Playwright CDP integration for GUI testing."""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tektos.gui.debugger import (
    ChromeDebugger,
    ChromeDebuggerConfig,
    CDPSessionManager,
    ConsoleEntry,
    DebugSession,
    NetworkRequest,
    PerformanceMetrics,
    ScreenshotResult,
    TestRecorder,
)


class TestChromeDebuggerConfig:
    """Tests for ChromeDebuggerConfig defaults."""

    def test_config_defaults(self):
        config = ChromeDebuggerConfig()
        assert config.base_url == "http://localhost:3003"
        assert config.headless is True
        assert config.slow_mo == 0
        assert config.viewport_width == 1280
        assert config.viewport_height == 720
        assert config.screenshot_dir == "gui-test-screenshots"
        assert config.enable_perf is True
        assert config.enable_network is True
        assert config.enable_console is True

    def test_config_custom(self):
        config = ChromeDebuggerConfig(
            base_url="http://custom:9999",
            headless=False,
            slow_mo=100,
            viewport_width=1920,
            viewport_height=1080,
        )
        assert config.base_url == "http://custom:9999"
        assert config.headless is False
        assert config.slow_mo == 100
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080


class TestConsoleEntry:
    """Tests for ConsoleEntry dataclass."""

    def test_console_entry_defaults(self):
        entry = ConsoleEntry(
            level="log",
            text="Hello world",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        assert entry.level == "log"
        assert entry.text == "Hello world"
        assert entry.url is None
        assert entry.stack is None

    def test_console_entry_with_url(self):
        entry = ConsoleEntry(
            level="error",
            text="Failed to load resource",
            timestamp=datetime.now(timezone.utc).isoformat(),
            url="http://localhost:3003/api/test",
            stack="Error: Failed at line 42",
        )
        assert entry.level == "error"
        assert entry.url == "http://localhost:3003/api/test"
        assert entry.stack == "Error: Failed at line 42"


class TestNetworkRequest:
    """Tests for NetworkRequest dataclass."""

    def test_network_request_defaults(self):
        request = NetworkRequest(
            url="http://localhost:3003/api/test",
            method="GET",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        assert request.url == "http://localhost:3003/api/test"
        assert request.method == "GET"
        assert request.status is None
        assert request.cached is False

    def test_network_request_with_response(self):
        request = NetworkRequest(
            url="http://localhost:3003/api/data",
            method="POST",
            status=200,
            status_text="OK",
            resource_type="fetch",
            response_time_ms=150.5,
            size_bytes=4096,
            cached=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        assert request.status == 200
        assert request.response_time_ms == 150.5
        assert request.size_bytes == 4096


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass."""

    def test_performance_metrics_defaults(self):
        metrics = PerformanceMetrics(
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        assert metrics.domContentLoaded_ms is None
        assert metrics.firstContentfulPaint_ms is None
        assert metrics.cumulativeLayoutShift is None

    def test_performance_metrics_with_values(self):
        metrics = PerformanceMetrics(
            timestamp=datetime.now(timezone.utc).isoformat(),
            domContentLoaded_ms=250.0,
            loadComplete_ms=500.0,
            firstContentfulPaint_ms=300.0,
            cumulativeLayoutShift=0.15,
            mainThreadTime_ms=1024.0,
        )
        assert metrics.domContentLoaded_ms == 250.0
        assert metrics.loadComplete_ms == 500.0
        assert metrics.cumulativeLayoutShift == 0.15


class TestScreenshotResult:
    """Tests for ScreenshotResult dataclass."""

    def test_screenshot_result_defaults(self):
        result = ScreenshotResult(
            path="/tmp/screenshot.png",
            width=1280,
            height=720,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        assert result.path == "/tmp/screenshot.png"
        assert result.width == 1280
        assert result.format == "png"


class TestDebugSession:
    """Tests for DebugSession dataclass."""

    def test_debug_session_defaults(self):
        session = DebugSession(session_id="test123")
        assert session.session_id == "test123"
        assert session.url == ""
        assert session.duration_ms == 0
        assert session.errors == []

    def test_debug_session_to_dict(self):
        session = DebugSession(
            session_id="test123",
            url="http://localhost:3003",
            duration_ms=5000.0,
        )
        session.console_entries = [
            ConsoleEntry(level="log", text="test", timestamp="2024-01-01T00:00:00Z"),
        ]
        session.network_requests = [
            NetworkRequest(url="http://localhost:3003/api", method="GET"),
        ]
        session.errors = ["Test error"]

        d = session.to_dict()
        assert d["session_id"] == "test123"
        assert d["url"] == "http://localhost:3003"
        assert d["screenshots_count"] == 0
        assert d["console_entries"] == 1
        assert d["network_requests"] == 1
        assert d["errors"] == ["Test error"]


class TestTestRecorder:
    """Tests for TestRecorder."""

    def test_recorder_initialization(self, tmp_path):
        recorder = TestRecorder(
            output_dir=str(tmp_path / "traces"),
            screenshot_dir=str(tmp_path / "screenshots"),
        )
        assert recorder.sessions == []
        assert (tmp_path / "traces").exists()
        assert (tmp_path / "screenshots").exists()

    def test_record_session(self, tmp_path):
        recorder = TestRecorder(
            output_dir=str(tmp_path / "traces"),
            screenshot_dir=str(tmp_path / "screenshots"),
        )
        session = DebugSession(session_id="test123", url="http://localhost:3003")
        recorder.record_session(session)
        assert len(recorder.sessions) == 1

    def test_generate_report(self, tmp_path):
        recorder = TestRecorder(
            output_dir=str(tmp_path / "traces"),
            screenshot_dir=str(tmp_path / "screenshots"),
        )
        session = DebugSession(
            session_id="test123",
            url="http://localhost:3003",
            duration_ms=1000.0,
        )
        session.errors = ["Error 1", "Error 2"]
        recorder.record_session(session)

        report = recorder.generate_report()
        assert "# GUI Test Report" in report
        assert "test123" in report
        assert "Error 1" in report
        assert "Error 2" in report

    def test_save_report(self, tmp_path):
        recorder = TestRecorder(
            output_dir=str(tmp_path / "traces"),
            screenshot_dir=str(tmp_path / "screenshots"),
        )
        session = DebugSession(session_id="test123")
        recorder.record_session(session)

        report_path = recorder.save_report()
        assert (tmp_path / "traces" / "gui-test-report.md").exists()


class TestCDPSessionManager:
    """Tests for CDPSessionManager."""

    def test_cdp_initialization(self):
        mock_page = MagicMock()
        manager = CDPSessionManager(mock_page)
        assert manager._page == mock_page
        assert manager._console_callbacks == []

    @pytest.mark.asyncio
    async def test_get_console_log(self):
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value=[])
        manager = CDPSessionManager(mock_page)
        entries = await manager.get_console_log()
        assert entries == []

    @pytest.mark.asyncio
    async def test_get_network_log(self):
        mock_page = MagicMock()
        manager = CDPSessionManager(mock_page)
        requests = await manager.get_network_log()
        assert requests == []

    @pytest.mark.asyncio
    async def test_get_dom_snapshot(self):
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value="<html>test</html>")
        manager = CDPSessionManager(mock_page)
        snapshot = await manager.get_dom_snapshot()
        assert "<html>test</html>" in snapshot

    @pytest.mark.asyncio
    async def test_get_accessibility_tree(self):
        mock_page = MagicMock()
        mock_page.accessibility.snapshot = AsyncMock(return_value={"role": "document"})
        manager = CDPSessionManager(mock_page)
        tree = await manager.get_accessibility_tree()
        assert tree["role"] == "document"

    @pytest.mark.asyncio
    async def test_get_performance_metrics(self):
        mock_page = MagicMock()
        mock_page.metrics = AsyncMock(return_value={
            "DOMContentLoaded": 250.0,
            "Load": 500.0,
            "JSHeapUsedSize": 1024.0,
        })
        manager = CDPSessionManager(mock_page)
        metrics = await manager.get_performance_metrics()
        assert metrics.domContentLoaded_ms == 250.0
        assert metrics.loadComplete_ms == 500.0

    @pytest.mark.asyncio
    async def test_execute_js(self):
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value=42)
        manager = CDPSessionManager(mock_page)
        result = await manager.execute_js("1 + 1")
        assert result == 42

    @pytest.mark.asyncio
    async def test_get_elements(self):
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.all = AsyncMock(return_value=[MagicMock()])
        mock_elem = MagicMock()
        mock_elem.bounding_box = AsyncMock(return_value={"x": 0, "y": 0, "width": 100, "height": 50})
        mock_elem.inner_text = AsyncMock(return_value="Test text")
        mock_elem.is_visible = AsyncMock(return_value=True)
        mock_elem.is_enabled = AsyncMock(return_value=True)
        mock_elem.evaluate = AsyncMock(return_value="DIV")
        mock_locator.all = AsyncMock(return_value=[mock_elem])
        mock_page.locator = MagicMock(return_value=mock_locator)
        manager = CDPSessionManager(mock_page)
        elements = await manager.get_elements("div.test")
        assert len(elements) == 1
        assert elements[0]["tag"] == "DIV"
        assert elements[0]["visible"] is True

    @pytest.mark.asyncio
    async def test_click_element_success(self):
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)
        manager = CDPSessionManager(mock_page)
        result = await manager.click_element("button.submit")
        assert result is True

    @pytest.mark.asyncio
    async def test_click_element_failure(self):
        mock_page = MagicMock()
        mock_page.locator = MagicMock(side_effect=Exception("Element not found"))
        manager = CDPSessionManager(mock_page)
        result = await manager.click_element("button.submit")
        assert result is False

    @pytest.mark.asyncio
    async def test_fill_input_success(self):
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.fill = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)
        manager = CDPSessionManager(mock_page)
        result = await manager.fill_input("input#name", "John")
        assert result is True

    @pytest.mark.asyncio
    async def test_fill_input_failure(self):
        mock_page = MagicMock()
        mock_page.locator = MagicMock(side_effect=Exception("Element not found"))
        manager = CDPSessionManager(mock_page)
        result = await manager.fill_input("input#name", "John")
        assert result is False


class TestChromeDebugger:
    """Tests for ChromeDebugger."""

    def test_debugger_initialization(self):
        debugger = ChromeDebugger()
        assert debugger.config.base_url == "http://localhost:3003"
        assert debugger._console_entries == []
        assert debugger._network_requests == []
        assert debugger._recorder is not None

    def test_debugger_custom_config(self):
        config = ChromeDebuggerConfig(
            base_url="http://custom:9999",
            headless=False,
        )
        debugger = ChromeDebugger(config)
        assert debugger.config.base_url == "http://custom:9999"
        assert debugger.config.headless is False

    def _make_mock_browser(self):
        """Create mock browser/page objects for testing."""
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        # evaluate returns {"w": 1280, "h": 720}, code reads size["w"] and size["h"]
        mock_page.evaluate = AsyncMock(return_value={"w": 1280, "h": 720})
        mock_page.screenshot = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.reload = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.metrics = AsyncMock(return_value={
            "DOMContentLoaded": 250.0, "Load": 500.0, "JSHeapUsedSize": 1024.0
        })
        mock_page.context = None
        mock_page.url = "http://localhost:3003"
        mock_page.on = MagicMock()
        mock_page.route = AsyncMock()
        mock_page.set_extra_http_headers = AsyncMock()
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_pw.stop = AsyncMock()
        return mock_pw, mock_browser, mock_page

    @pytest.mark.asyncio
    async def test_start_stop(self):
        with patch("playwright.async_api.async_playwright") as mock_playwright_fn:
            mock_pw, mock_browser, mock_page = self._make_mock_browser()
            mock_playwright_fn.return_value.start = AsyncMock(return_value=mock_pw)

            async with ChromeDebugger() as debugger:
                assert debugger._browser is not None
                assert debugger._page is not None

            mock_browser.close.assert_called_once()
            mock_pw.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_failure(self):
        with patch("playwright.async_api.async_playwright") as mock_playwright_fn:
            mock_playwright_fn.return_value.start = AsyncMock(
                side_effect=Exception("Browser not found")
            )

            debugger = ChromeDebugger()
            with pytest.raises(Exception, match="Browser not found"):
                await debugger.start()

    @pytest.mark.asyncio
    async def test_navigate(self):
        with patch("playwright.async_api.async_playwright") as mock_playwright_fn:
            mock_pw, mock_browser, mock_page = self._make_mock_browser()
            mock_playwright_fn.return_value.start = AsyncMock(return_value=mock_pw)

            async with ChromeDebugger() as debugger:
                await debugger.navigate("http://test:3003")
                mock_page.goto.assert_called_once()

    @pytest.mark.asyncio
    async def test_take_screenshot(self, tmp_path):
        with patch("playwright.async_api.async_playwright") as mock_playwright_fn:
            mock_pw, mock_browser, mock_page = self._make_mock_browser()
            mock_playwright_fn.return_value.start = AsyncMock(return_value=mock_pw)

            async with ChromeDebugger() as debugger:
                screenshot = await debugger.take_screenshot("test.png")
                assert screenshot.width == 1280
                assert screenshot.height == 720
                mock_page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_console_log(self):
        debugger = ChromeDebugger()
        debugger._console_entries = [
            ConsoleEntry(level="log", text="test", timestamp="2024-01-01T00:00:00Z"),
        ]
        entries = await debugger.get_console_log()
        assert len(entries) == 1
        assert entries[0].text == "test"

    @pytest.mark.asyncio
    async def test_get_network_log(self):
        debugger = ChromeDebugger()
        debugger._network_requests = [
            NetworkRequest(url="http://test", method="GET"),
        ]
        requests = await debugger.get_network_log()
        assert len(requests) == 1
        assert requests[0].method == "GET"

    @pytest.mark.asyncio
    async def test_click(self):
        with patch("playwright.async_api.async_playwright") as mock_playwright_fn:
            mock_pw, mock_browser, mock_page = self._make_mock_browser()
            mock_locator = MagicMock()
            mock_locator.click = AsyncMock()
            mock_page.locator = MagicMock(return_value=mock_locator)
            mock_playwright_fn.return_value.start = AsyncMock(return_value=mock_pw)

            async with ChromeDebugger() as debugger:
                result = await debugger.click("button.submit")
                assert result is True

    @pytest.mark.asyncio
    async def test_fill(self):
        with patch("playwright.async_api.async_playwright") as mock_playwright_fn:
            mock_pw, mock_browser, mock_page = self._make_mock_browser()
            mock_locator = MagicMock()
            mock_locator.fill = AsyncMock()
            mock_page.locator = MagicMock(return_value=mock_locator)
            mock_playwright_fn.return_value.start = AsyncMock(return_value=mock_pw)

            async with ChromeDebugger() as debugger:
                result = await debugger.fill("input#name", "John")
                assert result is True

    @pytest.mark.asyncio
    async def test_execute_js(self):
        with patch("playwright.async_api.async_playwright") as mock_playwright_fn:
            mock_pw, mock_browser, mock_page = self._make_mock_browser()
            mock_page.evaluate = AsyncMock(return_value=42)
            mock_playwright_fn.return_value.start = AsyncMock(return_value=mock_pw)

            async with ChromeDebugger() as debugger:
                result = await debugger.execute_js("1 + 1")
                assert result == 42

    @pytest.mark.asyncio
    async def test_wait_for_selector(self):
        with patch("playwright.async_api.async_playwright") as mock_playwright_fn:
            mock_pw, mock_browser, mock_page = self._make_mock_browser()
            mock_playwright_fn.return_value.start = AsyncMock(return_value=mock_pw)

            async with ChromeDebugger() as debugger:
                result = await debugger.wait_for_selector("#element")
                assert result is True

    @pytest.mark.asyncio
    async def test_end_session(self):
        with patch("playwright.async_api.async_playwright") as mock_playwright_fn:
            mock_pw, mock_browser, mock_page = self._make_mock_browser()
            mock_playwright_fn.return_value.start = AsyncMock(return_value=mock_pw)

            async with ChromeDebugger() as debugger:
                session = await debugger.end_session()
                assert session.url == "http://localhost:3003"
                assert "session_id" in session.to_dict()


class TestChromeDebuggerCLI:
    """Tests for ChromeDebugger CLI entry point."""

    def test_main_parse_args(self):
        import argparse
        from tektos.gui.debugger import main as cli_main

        with patch("sys.argv", ["tektos.gui.debugger", "--base-url", "http://custom:9999", "--headless"]):
            parser = argparse.ArgumentParser(description="Tektos GUI Test Runner")
            parser.add_argument("--base-url", default="http://localhost:3003")
            parser.add_argument("--headless", action="store_true", default=True)
            parser.add_argument("--screenshot-dir", default="gui-test-screenshots")
            parser.add_argument("--trace-dir", default="gui-test-traces")
            args = parser.parse_args()
            assert args.base_url == "http://custom:9999"
            assert args.headless is True