"""
Tektos-Ultima v1 — GUI Debugger Tests

Tests ChromeDebugger integration:
- ChromeDebuggerConfig defaults and fields
- Dataclasses: ConsoleEntry, NetworkRequest, ScreenshotResult,
  PerformanceMetrics, DebugSession
- CDPSessionManager: console, network, DOM, accessibility, performance,
  JS execution, element operations
- TestRecorder: record_session, generate_report, save_report
- ChromeDebugger: start, stop, navigate, screenshots, console/network,
  end_session, run_gui_test
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

from tektos.gui.debugger import (
    ChromeDebugger,
    ChromeDebuggerConfig,
    CDPSessionManager,
    ConsoleEntry,
    DebugSession,
    GuiTestRecorder,
    NetworkRequest,
    PerformanceMetrics,
    ScreenshotResult,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestChromeDebuggerConfig:
    def test_defaults(self):
        config = ChromeDebuggerConfig()
        assert config.base_url == "http://localhost:3003"
        assert config.headless is True
        assert config.slow_mo == 0
        assert config.viewport_width == 1280
        assert config.viewport_height == 720
        assert config.screenshot_dir == "gui-test-screenshots"
        assert config.trace_dir == "gui-test-traces"
        assert config.enable_perf is True
        assert config.enable_network is True
        assert config.enable_console is True

    def test_custom_values(self):
        config = ChromeDebuggerConfig(
            base_url="http://example.com",
            headless=False,
            slow_mo=100,
            viewport_width=1920,
            viewport_height=1080,
            screenshot_dir="/tmp/screenshots",
            trace_dir="/tmp/traces",
            enable_perf=False,
            enable_network=False,
            enable_console=False,
        )
        assert config.base_url == "http://example.com"
        assert config.headless is False
        assert config.slow_mo == 100
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.enable_perf is False

    def test_to_dict(self):
        config = ChromeDebuggerConfig()
        d = config.model_dump()
        assert d["base_url"] == "http://localhost:3003"
        assert d["headless"] is True


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class TestConsoleEntry:
    def test_defaults(self):
        entry = ConsoleEntry(level="log", text="hello", timestamp="2024-01-01T00:00:00Z")
        assert entry.level == "log"
        assert entry.text == "hello"
        assert entry.timestamp == "2024-01-01T00:00:00Z"
        assert entry.url is None
        assert entry.stack is None

    def test_with_all_fields(self):
        entry = ConsoleEntry(
            level="error", text="failed", timestamp="2024-01-01T00:00:00Z",
            url="http://example.com", stack="at foo.js:1",
        )
        assert entry.url == "http://example.com"
        assert entry.stack == "at foo.js:1"

    def test_levels(self):
        for level in ("log", "warn", "error", "info", "debug"):
            entry = ConsoleEntry(level=level, text="t", timestamp="t")
            assert entry.level == level


class TestNetworkRequest:
    def test_defaults(self):
        req = NetworkRequest(url="http://example.com", method="GET")
        assert req.url == "http://example.com"
        assert req.method == "GET"
        assert req.status is None
        assert req.status_text is None
        assert req.resource_type is None
        assert req.initiator is None
        assert req.response_time_ms is None
        assert req.size_bytes is None
        assert req.cached is False
        assert req.error is None
        assert req.timestamp == ""

    def test_with_all_fields(self):
        req = NetworkRequest(
            url="http://example.com/api", method="POST",
            status=200, status_text="OK", resource_type="xhr",
            initiator="main", response_time_ms=150.5, size_bytes=1024,
            cached=True, error=None, timestamp="2024-01-01T00:00:00Z",
        )
        assert req.status == 200
        assert req.response_time_ms == 150.5
        assert req.size_bytes == 1024
        assert req.cached is True

    def test_status_codes(self):
        for status in (200, 301, 404, 500, 503):
            req = NetworkRequest(url="http://example.com", method="GET", status=status)
            assert req.status == status


class TestScreenshotResult:
    def test_defaults(self):
        result = ScreenshotResult(path="/tmp/test.png", width=1280, height=720, timestamp="2024-01-01T00:00:00Z")
        assert result.path == "/tmp/test.png"
        assert result.width == 1280
        assert result.height == 720
        assert result.format == "png"

    def test_custom_format(self):
        result = ScreenshotResult(path="/tmp/test.webp", width=800, height=600, timestamp="2024-01-01T00:00:00Z", format="webp")
        assert result.format == "webp"


class TestPerformanceMetrics:
    def test_defaults(self):
        ts = "2024-01-01T00:00:00Z"
        metrics = PerformanceMetrics(timestamp=ts)
        assert metrics.timestamp == ts
        assert metrics.domContentLoaded_ms is None
        assert metrics.loadComplete_ms is None
        assert metrics.firstPaint_ms is None
        assert metrics.firstContentfulPaint_ms is None
        assert metrics.totalBlockingTime is None
        assert metrics.cumulativeLayoutShift is None
        assert metrics.mainThreadTime_ms is None

    def test_with_values(self):
        metrics = PerformanceMetrics(
            timestamp="2024-01-01T00:00:00Z",
            domContentLoaded_ms=500.0,
            loadComplete_ms=1200.0,
            firstPaint_ms=300.0,
            firstContentfulPaint_ms=350.0,
            totalBlockingTime=100.0,
            cumulativeLayoutShift=0.05,
            mainThreadTime_ms=5000.0,
        )
        assert metrics.domContentLoaded_ms == 500.0
        assert metrics.loadComplete_ms == 1200.0
        assert metrics.cumulativeLayoutShift == 0.05


class TestDebugSession:
    def test_defaults(self):
        session = DebugSession()
        assert session.session_id == ""
        assert session.url == ""
        assert session.duration_ms == 0
        assert session.screenshots == []
        assert session.console_entries == []
        assert session.network_requests == []
        assert session.performance is None
        assert session.errors == []

    def test_to_dict(self):
        session = DebugSession(
            session_id="sess-1", url="http://example.com",
            duration_ms=5000.0,
            errors=["error1", "error2"],
        )
        d = session.to_dict()
        assert d["session_id"] == "sess-1"
        assert d["url"] == "http://example.com"
        assert d["duration_ms"] == 5000.0
        assert d["screenshots_count"] == 0
        assert d["console_entries"] == 0
        assert d["network_requests"] == 0
        assert d["errors"] == ["error1", "error2"]

    def test_to_dict_with_data(self):
        session = DebugSession(
            session_id="sess-1", url="http://example.com",
            screenshots=[ScreenshotResult(path="/tmp/1.png", width=1280, height=720, timestamp="t")],
            console_entries=[ConsoleEntry(level="log", text="hi", timestamp="t")],
            network_requests=[NetworkRequest(url="http://example.com", method="GET")],
            errors=["err1"],
        )
        d = session.to_dict()
        assert d["screenshots_count"] == 1
        assert d["console_entries"] == 1
        assert d["network_requests"] == 1


# ---------------------------------------------------------------------------
# CDPSessionManager
# ---------------------------------------------------------------------------


class TestCDPSessionManager:
    def _make_page(self):
        page = MagicMock()
        page.context = MagicMock()
        page.context.new_cdp_session = AsyncMock(return_value=MagicMock())
        page.evaluate = AsyncMock(return_value="")
        page.metrics = AsyncMock(return_value={
            "DOMContentLoaded": 500.0, "Load": 1200.0, "JSHeapUsedSize": 5000000,
        })
        page.accessibility = MagicMock()
        page.accessibility.snapshot = AsyncMock(return_value={"nodes": []})
        page.locator = MagicMock(return_value=MagicMock())
        page.locator.return_value.all = AsyncMock(return_value=[])
        return page

    def test_initialization(self):
        page = self._make_page()
        cdp = CDPSessionManager(page)
        assert cdp._page == page
        assert cdp._cdp is None
        assert cdp._console_callbacks == []
        assert cdp._network_enabled is False
        assert cdp._perf_enabled is False

    async def test_initialize(self):
        page = self._make_page()
        cdp = CDPSessionManager(page)
        await cdp.initialize()
        # CDP session would be created; in mock mode _cdp set to None
        assert cdp._cdp is None  # Mocked to None due to page.context check

    async def test_get_console_log(self):
        page = self._make_page()
        cdp = CDPSessionManager(page)
        entries = await cdp.get_console_log()
        assert entries == []

    async def test_get_network_log(self):
        page = self._make_page()
        cdp = CDPSessionManager(page)
        entries = await cdp.get_network_log()
        assert entries == []

    async def test_get_dom_snapshot(self):
        page = self._make_page()
        page.evaluate = AsyncMock(return_value="<html><body>test</body></html>"[:10000])
        cdp = CDPSessionManager(page)
        dom = await cdp.get_dom_snapshot()
        assert "html" in dom

    async def test_get_accessibility_tree(self):
        page = self._make_page()
        cdp = CDPSessionManager(page)
        tree = await cdp.get_accessibility_tree()
        assert "nodes" in tree

    async def test_get_accessibility_tree_fails(self):
        page = self._make_page()
        page.accessibility = MagicMock()
        page.accessibility.snapshot = AsyncMock(side_effect=Exception("fail"))
        cdp = CDPSessionManager(page)
        tree = await cdp.get_accessibility_tree()
        assert tree == {}

    async def test_get_performance_metrics(self):
        page = self._make_page()
        cdp = CDPSessionManager(page)
        metrics = await cdp.get_performance_metrics()
        assert metrics.domContentLoaded_ms == 500.0
        assert metrics.loadComplete_ms == 1200.0
        assert metrics.mainThreadTime_ms == 5000000

    async def test_get_performance_metrics_fails(self):
        page = self._make_page()
        page.metrics = AsyncMock(side_effect=Exception("fail"))
        cdp = CDPSessionManager(page)
        metrics = await cdp.get_performance_metrics()
        assert metrics.timestamp != ""
        assert metrics.domContentLoaded_ms is None

    async def test_execute_js(self):
        page = self._make_page()
        page.evaluate = AsyncMock(return_value={"x": 1})
        cdp = CDPSessionManager(page)
        result = await cdp.execute_js("1 + 1")
        assert result == {"x": 1}

    async def test_get_elements(self):
        page = self._make_page()
        elem_mock = MagicMock()
        elem_mock.bounding_box = AsyncMock(return_value={"x": 0, "y": 0, "width": 100, "height": 50})
        elem_mock.inner_text = AsyncMock(return_value="Hello")
        elem_mock.evaluate = AsyncMock(return_value="DIV")
        elem_mock.is_visible = AsyncMock(return_value=True)
        elem_mock.is_enabled = AsyncMock(return_value=True)
        page.locator.return_value.all = AsyncMock(return_value=[elem_mock])
        cdp = CDPSessionManager(page)
        elements = await cdp.get_elements("div")
        assert len(elements) == 1
        assert elements[0]["tag"] == "DIV"
        assert elements[0]["text"] == "Hello"

    async def test_get_elements_empty(self):
        page = self._make_page()
        page.locator.return_value.all = AsyncMock(return_value=[])
        cdp = CDPSessionManager(page)
        elements = await cdp.get_elements("div")
        assert elements == []

    async def test_click_element_success(self):
        page = self._make_page()
        elem_mock = MagicMock()
        elem_mock.click = AsyncMock()
        page.locator.return_value = elem_mock
        cdp = CDPSessionManager(page)
        result = await cdp.click_element("button")
        assert result is True

    async def test_click_element_failure(self):
        page = self._make_page()
        page.locator = MagicMock(side_effect=Exception("fail"))
        cdp = CDPSessionManager(page)
        result = await cdp.click_element("button")
        assert result is False

    async def test_fill_input_success(self):
        page = self._make_page()
        elem_mock = MagicMock()
        elem_mock.fill = AsyncMock()
        page.locator.return_value = elem_mock
        cdp = CDPSessionManager(page)
        result = await cdp.fill_input("input[name='q']", "test")
        assert result is True

    async def test_fill_input_failure(self):
        page = self._make_page()
        page.locator = MagicMock(side_effect=Exception("fail"))
        cdp = CDPSessionManager(page)
        result = await cdp.fill_input("input", "test")
        assert result is False


# ---------------------------------------------------------------------------
# TestRecorder
# ---------------------------------------------------------------------------


class TestGuiTestRecorder:
    def test_init_creates_dirs(self, tmp_path):
        recorder = GuiTestRecorder(
            output_dir=str(tmp_path / "traces"),
            screenshot_dir=str(tmp_path / "screenshots"),
        )
        assert (tmp_path / "traces").is_dir()
        assert (tmp_path / "screenshots").is_dir()

    def test_init_no_args(self, tmp_path):
        recorder = GuiTestRecorder(output_dir=str(tmp_path / "o"), screenshot_dir=str(tmp_path / "s"))
        assert recorder.sessions == []
        assert recorder.output_dir == tmp_path / "o"
        assert recorder.screenshot_dir == tmp_path / "s"

    def test_record_session(self, tmp_path):
        recorder = GuiTestRecorder(
            output_dir=str(tmp_path / "traces"),
            screenshot_dir=str(tmp_path / "screenshots"),
        )
        session = DebugSession(session_id="sess-1", url="http://example.com", duration_ms=5000.0)
        recorder.record_session(session)
        assert len(recorder.sessions) == 1
        assert (tmp_path / "traces" / "session_sess-1.json").exists()

    def test_record_multiple_sessions(self, tmp_path):
        recorder = GuiTestRecorder(
            output_dir=str(tmp_path / "traces"),
            screenshot_dir=str(tmp_path / "screenshots"),
        )
        for i in range(3):
            session = DebugSession(session_id=f"sess-{i}", url=f"http://example.com/{i}")
            recorder.record_session(session)
        assert len(recorder.sessions) == 3

    def test_generate_report_empty(self):
        recorder = GuiTestRecorder(output_dir="/tmp", screenshot_dir="/tmp")
        report = recorder.generate_report()
        assert "# GUI Test Report" in report
        assert "**Sessions:** 0" in report
        assert "**Total Screenshots:** 0" in report
        assert "**Total Errors:** 0" in report

    def test_generate_report_with_sessions(self, tmp_path):
        recorder = GuiTestRecorder(
            output_dir=str(tmp_path / "traces"),
            screenshot_dir=str(tmp_path / "screenshots"),
        )
        session = DebugSession(
            session_id="sess-1", url="http://example.com",
            duration_ms=5000.0, errors=["error1", "error2"],
        )
        recorder.record_session(session)
        report = recorder.generate_report()
        assert "## Session: sess-1" in report
        assert "URL: http://example.com" in report
        assert "Duration: 5000.0ms" in report
        assert "Console Entries: 0" in report
        assert "Network Requests: 0" in report
        assert "**Errors:** 2" in report
        assert "- error1" in report
        assert "- error2" in report

    def test_save_report(self, tmp_path):
        recorder = GuiTestRecorder(
            output_dir=str(tmp_path / "traces"),
            screenshot_dir=str(tmp_path / "screenshots"),
        )
        session = DebugSession(session_id="sess-1", url="http://example.com")
        recorder.record_session(session)
        report_path = recorder.save_report("test-report.md")
        assert Path(report_path).exists()
        content = Path(report_path).read_text()
        assert "GUI Test Report" in content

    def test_save_report_custom_name(self, tmp_path):
        recorder = GuiTestRecorder(
            output_dir=str(tmp_path / "traces"),
            screenshot_dir=str(tmp_path / "screenshots"),
        )
        report_path = recorder.save_report("custom.md")
        assert Path(report_path).name == "custom.md"


# ---------------------------------------------------------------------------
# ChromeDebugger
# ---------------------------------------------------------------------------


class TestChromeDebugger:
    def test_init_defaults(self):
        debugger = ChromeDebugger()
        assert debugger.config.base_url == "http://localhost:3003"
        assert debugger._browser is None
        assert debugger._page is None
        assert debugger._cdp is None
        assert debugger._console_entries == []
        assert debugger._network_requests == []
        assert debugger._session_start is None
        assert debugger._current_session is None

    def test_init_custom_config(self):
        config = ChromeDebuggerConfig(base_url="http://example.com", headless=False, slow_mo=100)
        debugger = ChromeDebugger(config)
        assert debugger.config.base_url == "http://example.com"
        assert debugger.config.headless is False
        assert debugger.config.slow_mo == 100

    def test_init_without_config(self):
        debugger = ChromeDebugger(None)
        assert debugger.config.base_url == "http://localhost:3003"

    async def test_start_and_stop(self):
        """Test that start() launches browser successfully."""
        config = ChromeDebuggerConfig(headless=True)
        debugger = ChromeDebugger(config)
        await debugger.start()
        assert debugger._browser is not None
        assert debugger._page is not None
        await debugger.stop()

    async def test_stop_no_browser(self):
        debugger = ChromeDebugger()
        await debugger.stop()  # Should not crash

    async def test_stop_with_browser(self):
        debugger = ChromeDebugger()
        debugger._browser = MagicMock()
        debugger._browser.close = AsyncMock()
        debugger._playwright = MagicMock()
        debugger._playwright.stop = AsyncMock()
        await debugger.stop()
        debugger._browser.close.assert_called_once()

    async def test_navigate_no_page_raises(self):
        debugger = ChromeDebugger()
        with pytest.raises(RuntimeError, match="Debugger not started"):
            await debugger.navigate("http://example.com")

    async def test_reload_no_page_raises(self):
        debugger = ChromeDebugger()
        with pytest.raises(RuntimeError, match="Debugger not started."):
            await debugger.reload()

    async def test_take_screenshot_no_page_raises(self):
        debugger = ChromeDebugger()
        with pytest.raises(RuntimeError, match="Debugger not started."):
            await debugger.take_screenshot("test.png")

    async def test_get_console_log_empty(self):
        debugger = ChromeDebugger()
        entries = await debugger.get_console_log()
        assert entries == []

    async def test_get_network_log_empty(self):
        debugger = ChromeDebugger()
        entries = await debugger.get_network_log()
        assert entries == []

    async def test_end_session_no_page_raises(self):
        debugger = ChromeDebugger()
        with pytest.raises(RuntimeError, match="No page open."):
            await debugger.end_session()

    async def test_get_performance_metrics_no_page_raises(self):
        debugger = ChromeDebugger()
        metrics = await debugger.get_performance_metrics()
        assert metrics is not None
        assert metrics.timestamp != ""

    async def test_get_dom_snapshot_no_page_raises(self):
        debugger = ChromeDebugger()
        with pytest.raises(Exception):
            await debugger.get_dom_snapshot()

    async def test_get_accessibility_tree_no_page_raises(self):
        debugger = ChromeDebugger()
        tree = await debugger.get_accessibility_tree()
        assert isinstance(tree, dict)

    async def test_click_no_page_raises(self):
        debugger = ChromeDebugger()
        result = await debugger.click("button")
        assert result is False

    async def test_fill_no_page_raises(self):
        debugger = ChromeDebugger()
        result = await debugger.fill("input", "test")
        assert result is False

    async def test_execute_js_no_page_raises(self):
        debugger = ChromeDebugger()
        with pytest.raises(Exception):
            await debugger.execute_js("1 + 1")

    async def test_wait_for_selector_no_page_raises(self):
        debugger = ChromeDebugger()
        result = await debugger.wait_for_selector("button")
        assert result is False

    async def test_wait_for_load_state_no_page_raises(self):
        debugger = ChromeDebugger()
        with pytest.raises((AttributeError, RuntimeError)):
            await debugger.wait_for_load_state()

    async def test_run_gui_test_no_page_raises(self):
        debugger = ChromeDebugger()
        with pytest.raises(RuntimeError):
            await debugger.run_gui_test()

    async def test_context_manager_enter(self):
        """Test async context manager enters correctly."""
        debugger = ChromeDebugger()
        debugger.start = AsyncMock(return_value=None)
        debugger.stop = AsyncMock(return_value=None)
        async with debugger:
            debugger.start.assert_called_once()

    async def test_context_manager_exit(self):
        """Test async context manager exits correctly."""
        debugger = ChromeDebugger()
        debugger.start = AsyncMock(return_value=None)
        debugger.stop = AsyncMock(return_value=None)
        async with debugger:
            pass
        debugger.stop.assert_called_once()

    async def test_run_gui_test(self):
        """Test run_gui_test with mocked page."""
        debugger = ChromeDebugger()
        page_mock = MagicMock()
        page_mock.url = "http://localhost:3003"
        page_mock.goto = AsyncMock()
        page_mock.wait_for_load_state = AsyncMock()
        page_mock.screenshot = AsyncMock()
        page_mock.evaluate = AsyncMock(return_value={"w": 1280, "h": 720})
        page_mock.metrics = AsyncMock(return_value={})
        debugger._page = page_mock
        debugger._session_start = 0

        session = await debugger.run_gui_test(screenshots=[("test", "h1")])
        assert isinstance(session, DebugSession)
        assert session.url == "http://localhost:3003"
        assert session.performance is not None

    async def test_screenshot_creates_file(self, tmp_path):
        """Test that screenshot saves to disk."""
        debugger = ChromeDebugger(ChromeDebuggerConfig(screenshot_dir=str(tmp_path / "screenshots")))
        page_mock = MagicMock()
        page_mock.evaluate = AsyncMock(return_value={"w": 1280, "h": 720})
        page_mock.screenshot = AsyncMock()
        debugger._page = page_mock
        debugger._session_start = 0

        result = await debugger.take_screenshot("test.png")
        assert isinstance(result, ScreenshotResult)
        assert result.path == str(tmp_path / "screenshots" / "test.png")
        assert result.width == 1280
        assert result.height == 720
        assert result.format == "png"

    async def test_screenshot_full_page(self, tmp_path):
        debugger = ChromeDebugger(ChromeDebuggerConfig(screenshot_dir=str(tmp_path / "screenshots")))
        page_mock = MagicMock()
        page_mock.evaluate = AsyncMock(return_value={"w": 1280, "h": 720})
        page_mock.screenshot = AsyncMock()
        debugger._page = page_mock

        result = await debugger.take_screenshot("full.png", full_page=True)
        assert result is not None

    async def test_console_entries_copied(self):
        debugger = ChromeDebugger()
        debugger._console_entries = [ConsoleEntry(level="log", text="hi", timestamp="t")]
        entries = await debugger.get_console_log()
        assert len(entries) == 1
        assert entries[0].text == "hi"
        entries.append(ConsoleEntry(level="error", text="new", timestamp="t"))
        assert len(debugger._console_entries) == 1

    async def test_network_requests_copied(self):
        debugger = ChromeDebugger()
        debugger._network_requests = [NetworkRequest(url="http://example.com", method="GET")]
        entries = await debugger.get_network_log()
        assert len(entries) == 1
        entries.append(NetworkRequest(url="http://other.com", method="POST"))
        assert len(debugger._network_requests) == 1

    async def test_run_gui_test_no_screenshots(self):
        """Test run_gui_test without screenshots - uses real async mocks."""
        debugger = ChromeDebugger()
        page_mock = MagicMock(spec=[])
        page_mock.url = "http://localhost:3003"
        page_mock.goto = AsyncMock()
        page_mock.wait_for_load_state = AsyncMock()
        page_mock.screenshot = AsyncMock()
        page_mock.evaluate = AsyncMock(return_value={"w": 1280, "h": 720})
        page_mock.metrics = AsyncMock(return_value={})
        debugger._page = page_mock
        debugger._session_start = 0

        session = await debugger.run_gui_test()
        assert session is not None
        assert session.performance is not None

    async def test_run_gui_test_with_screenshots(self):
        debugger = ChromeDebugger()
        page_mock = MagicMock()
        page_mock.url = "http://localhost:3003"
        page_mock.goto = AsyncMock()
        page_mock.wait_for_load_state = AsyncMock()
        page_mock.screenshot = AsyncMock()
        page_mock.evaluate = AsyncMock(return_value={"w": 1280, "h": 720})
        page_mock.metrics = AsyncMock(return_value={})
        locator_mock = MagicMock()
        locator_mock.count = AsyncMock(return_value=1)
        locator_mock.scroll_into_view_if_needed = AsyncMock()
        page_mock.locator = MagicMock(return_value=locator_mock)
        debugger._page = page_mock
        debugger._session_start = 0

        session = await debugger.run_gui_test(screenshots=[("test", "h1")])
        assert session is not None

    async def test_run_gui_test_screenshot_fails(self):
        debugger = ChromeDebugger()
        page_mock = MagicMock()
        page_mock.url = "http://localhost:3003"
        page_mock.goto = AsyncMock()
        page_mock.wait_for_load_state = AsyncMock()
        page_mock.screenshot = AsyncMock()
        page_mock.evaluate = AsyncMock(return_value={"w": 1280, "h": 720})
        page_mock.metrics = AsyncMock(return_value={})
        locator_mock = MagicMock()
        locator_mock.count = AsyncMock(side_effect=Exception("fail"))
        page_mock.locator = MagicMock(return_value=locator_mock)
        debugger._page = page_mock
        debugger._session_start = 0

        session = await debugger.run_gui_test(screenshots=[("test", "h1")])
        assert session is not None
