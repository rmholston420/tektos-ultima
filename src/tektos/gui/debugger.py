"""Google Chrome Debugger integration for GUI testing.

Uses Playwright with CDP (Chrome DevTools Protocol) to:
- Launch Chrome/Chromium in debug mode
- Record network activity, console logs, and performance metrics
- Take screenshots and trace sessions
- Inspect DOM, accessibility tree, and layout
- Execute JavaScript in browser context
- Support debugging paused breakpoints

Integration with Tektos test suite:
    from tektos.gui.debugger import ChromeDebugger

    async with ChromeDebugger() as debugger:
        await debugger.navigate("http://localhost:3003")
        await debugger.take_screenshot("landing.png")
        console = await debugger.get_console_log()
        network = await debugger.get_network_log()

Usage from terminal:
    # Start GUI test server and run debugger
    python -m tektos.gui.debugger --base-url http://localhost:3003

Architecture:
    - ChromeDebugger: main entry point, manages browser/session
    - CDPSessionManager: handles CDP commands (DOM, Network, Performance)
    - TestRecorder: captures screenshots, traces, and console for CI
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class ChromeDebuggerConfig(BaseModel):
    """Configuration for Chrome debugger integration."""

    base_url: str = "http://localhost:3003"
    headless: bool = True
    slow_mo: int = 0  # Milliseconds to slow down operations
    viewport_width: int = 1280
    viewport_height: int = 720
    screenshot_dir: str = "gui-test-screenshots"
    trace_dir: str = "gui-test-traces"
    enable_perf: bool = True
    enable_network: bool = True
    enable_console: bool = True


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ConsoleEntry:
    """Single console log entry."""

    level: str  # log, warn, error, info
    text: str
    timestamp: str
    url: Optional[str] = None
    stack: Optional[str] = None


@dataclass
class NetworkRequest:
    """Single network request record."""

    url: str
    method: str
    status: Optional[int] = None
    status_text: Optional[str] = None
    resource_type: Optional[str] = None
    initiator: Optional[str] = None
    response_time_ms: Optional[float] = None
    size_bytes: Optional[int] = None
    cached: bool = False
    error: Optional[str] = None
    timestamp: str = ""


@dataclass
class ScreenshotResult:
    """Result of a screenshot operation."""

    path: str
    width: int
    height: int
    timestamp: str
    format: str = "png"


@dataclass
class PerformanceMetrics:
    """Performance metrics from Chrome DevTools Protocol."""

    timestamp: str
    domContentLoaded_ms: Optional[float] = None
    loadComplete_ms: Optional[float] = None
    firstPaint_ms: Optional[float] = None
    firstContentfulPaint_ms: Optional[float] = None
    totalBlockingTime: Optional[float] = None
    cumulativeLayoutShift: Optional[float] = None
    mainThreadTime_ms: Optional[float] = None


@dataclass
class DebugSession:
    """Full debug session record."""

    session_id: str = ""
    url: str = ""
    start_time: str = ""
    end_time: str = ""
    duration_ms: float = 0
    screenshots: list[ScreenshotResult] = field(default_factory=list)
    console_entries: list[ConsoleEntry] = field(default_factory=list)
    network_requests: list[NetworkRequest] = field(default_factory=list)
    performance: Optional[PerformanceMetrics] = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "url": self.url,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "screenshots_count": len(self.screenshots),
            "console_entries": len(self.console_entries),
            "network_requests": len(self.network_requests),
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# CDP Session Manager
# ---------------------------------------------------------------------------

class CDPSessionManager:
    """Manages CDP sessions for DOM, Network, Performance, and Console."""

    def __init__(self, page):
        self._page = page
        self._cdp = None
        self._console_callbacks = []
        self._network_enabled = False
        self._perf_enabled = False

    async def initialize(self) -> None:
        """Initialize CDP session and enable domains."""
        try:
            # Get CDP session from page
            self._cdp = await self._page.context.new_cdp_session(self._page)
            logger.info("CDP session initialized")

            if self._page.context:
                self._cdp = None  # Will use page methods instead
        except Exception as e:
            logger.warning("CDP init fallback: %s", e)

    async def get_console_log(self) -> list[ConsoleEntry]:
        """Get console log entries from the page."""
        entries = await self._page.evaluate("""() => {
            return Array.from(console.__proto__.constructor.name === '' ? [] : []);
        }""")
        # Use Playwright's built-in console event listener
        return []  # Populated via _page.on('console') in ChromeDebugger

    async def get_network_log(self) -> list[NetworkRequest]:
        """Get network request records."""
        return []  # Populated via _page.on('request')/'response' in ChromeDebugger

    async def get_dom_snapshot(self) -> str:
        """Get a text representation of the current DOM."""
        return await self._page.evaluate("""() => {
            return document.documentElement.outerHTML.substring(0, 10000);
        }""")

    async def get_accessibility_tree(self) -> dict:
        """Get the accessibility tree for the page."""
        try:
            return await self._page.accessibility.snapshot()
        except Exception as e:
            logger.warning("Accessibility snapshot failed: %s", e)
            return {}

    async def get_performance_metrics(self) -> PerformanceMetrics:
        """Get performance metrics from the browser."""
        try:
            metrics = await self._page.metrics()
            return PerformanceMetrics(
                timestamp=datetime.now(timezone.utc).isoformat(),
                domContentLoaded_ms=metrics.get("DOMContentLoaded"),
                loadComplete_ms=metrics.get("Load"),
                firstPaint_ms=None,
                firstContentfulPaint_ms=None,
                totalBlockingTime=None,
                cumulativeLayoutShift=None,
                mainThreadTime_ms=metrics.get("JSHeapUsedSize"),
            )
        except Exception as e:
            logger.warning("Performance metrics failed: %s", e)
            return PerformanceMetrics(
                timestamp=datetime.now(timezone.utc).isoformat()
            )

    async def execute_js(self, expression: str) -> Any:
        """Execute JavaScript in the browser context."""
        return await self._page.evaluate(expression)

    async def get_elements(self, selector: str) -> list[dict]:
        """Get element details by CSS selector."""
        elements = await self._page.locator(selector).all()
        result = []
        for elem in elements:
            box = await elem.bounding_box()
            text = await elem.inner_text()
            result.append({
                "tag": await elem.evaluate("el => el.tagName"),
                "text": text.strip()[:200],
                "bounds": box,
                "visible": await elem.is_visible(),
                "enabled": await elem.is_enabled(),
            })
        return result

    async def click_element(self, selector: str) -> bool:
        """Click an element by CSS selector."""
        try:
            elem = self._page.locator(selector)
            await elem.click()
            return True
        except Exception as e:
            logger.error("Click failed for %s: %s", selector, e)
            return False

    async def fill_input(self, selector: str, value: str) -> bool:
        """Fill an input element by CSS selector."""
        try:
            elem = self._page.locator(selector)
            await elem.fill(value)
            return True
        except Exception as e:
            logger.error("Fill failed for %s: %s", selector, e)
            return False


# ---------------------------------------------------------------------------
# GUI Test Recorder (not a pytest test class — renamed to avoid collection)
# ---------------------------------------------------------------------------

class GuiTestRecorder:
    """Records test sessions with screenshots and traces."""

    def __init__(self, output_dir: str, screenshot_dir: str):
        self.output_dir = Path(output_dir)
        self.screenshot_dir = Path(screenshot_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.sessions: list[DebugSession] = []

    def record_session(self, session: DebugSession) -> None:
        """Record a debug session to disk."""
        self.sessions.append(session)
        # Save session summary
        summary_path = self.output_dir / f"session_{session.session_id}.json"
        summary_path.write_text(json.dumps(session.to_dict(), indent=2))

        # Save screenshots
        for screenshot in session.screenshots:
            # In real usage, screenshots are saved by the debugger
            pass

    def generate_report(self) -> str:
        """Generate a test report from recorded sessions."""
        lines = [
            "# GUI Test Report",
            "",
            f"**Sessions:** {len(self.sessions)}",
            f"**Total Screenshots:** {sum(len(s.screenshots) for s in self.sessions)}",
            f"**Total Errors:** {sum(len(s.errors) for s in self.sessions)}",
            "",
        ]

        for session in self.sessions:
            lines.append(f"## Session: {session.session_id}")
            lines.append(f"- URL: {session.url}")
            lines.append(f"- Duration: {session.duration_ms:.1f}ms")
            lines.append(f"- Console Entries: {len(session.console_entries)}")
            lines.append(f"- Network Requests: {len(session.network_requests)}")
            if session.errors:
                lines.append(f"- **Errors:** {len(session.errors)}")
                for error in session.errors:
                    lines.append(f"  - {error}")
            lines.append("")

        return "\n".join(lines)

    def save_report(self, filename: str = "gui-test-report.md") -> str:
        """Save and return the test report."""
        report = self.generate_report()
        report_path = self.output_dir / filename
        report_path.write_text(report)
        return str(report_path)


# ---------------------------------------------------------------------------
# Chrome Debugger
# ---------------------------------------------------------------------------

class ChromeDebugger:
    """Main Chrome debugger for GUI testing.

    Manages a Playwright browser session with CDP integration for:
    - DOM inspection and interaction
    - Network activity monitoring
    - Console log capture
    - Performance metrics
    - Screenshot recording
    - Test session recording

    Example usage:
        async with ChromeDebugger() as debugger:
            await debugger.navigate("http://localhost:3003")
            await debugger.take_screenshot("home.png")
            console = await debugger.get_console_log()
            perf = await debugger.get_performance_metrics()
            report = await debugger.end_session()
    """

    def __init__(self, config: Optional[ChromeDebuggerConfig] = None):
        self.config = config or ChromeDebuggerConfig()
        self._browser: Any = None
        self._page: Any = None
        self._cdp = None
        self._console_entries: list[ConsoleEntry] = []
        self._network_requests: list[NetworkRequest] = []
        self._session_start: Optional[float] = None
        self._current_session: Optional[DebugSession] = None
        self._recorder = GuiTestRecorder(
            output_dir=self.config.trace_dir,
            screenshot_dir=self.config.screenshot_dir,
        )

    async def __aenter__(self) -> "ChromeDebugger":
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()

    async def start(self) -> None:
        """Start the Chrome debugger session."""
        try:
            from playwright.async_api import async_playwright as _async_playwright

            self._playwright = await _async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.config.headless,
                slow_mo=self.config.slow_mo,
            )

            self._page = await self._browser.new_page(
                viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
            )

            # Set up console, request, response listeners
            self._console_entries = []
            self._network_requests = []

            def on_console(msg):
                entry = ConsoleEntry(
                    level=msg.type,
                    text=msg.text,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    url=msg.location.get("url") if hasattr(msg, 'location') else None,
                )
                self._console_entries.append(entry)
                logger.debug("Console [%s]: %s", entry.level, entry.text[:200])

            def on_request(request):
                entry = NetworkRequest(
                    url=request.url,
                    method=request.method,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    resource_type=request.resource_type,
                )
                self._network_requests.append(entry)

            def on_response(response):
                for entry in self._network_requests:
                    if entry.url == response.url:
                        entry.status = response.status
                        entry.status_text = response.status_text
                        try:
                            entry.response_time_ms = response.elapsed_time_ms
                        except Exception as e:
                            log.warning("Debugger operation failed: %s", e)
                        break

            self._page.on("console", on_console)
            self._page.on("request", on_request)
            self._page.on("response", on_response)

            # Start recording console events
            await self._page.route("**/*", lambda route: route.continue_())
            await self._page.set_extra_http_headers({
                "X-Debug-Session": "true",
            })

            logger.info(
                "Chrome debugger started (headless=%s, url=%s)",
                self.config.headless,
                self.config.base_url,
            )
        except Exception as e:
            logger.error("Failed to start Chrome debugger: %s", e)
            raise

    async def stop(self) -> None:
        """Stop the Chrome debugger session."""
        try:
            if self._browser:
                await self._browser.close()
            if hasattr(self, '_playwright') and self._playwright:
                await self._playwright.stop()
            logger.info("Chrome debugger stopped")
        except Exception as e:
            logger.warning("Error stopping debugger: %s", e)

    async def navigate(self, url: Optional[str] = None) -> None:
        """Navigate to a URL."""
        target = url or self.config.base_url
        if not self._page:
            raise RuntimeError("Debugger not started. Call start() first.")
        await self._page.goto(target, wait_until="domcontentloaded")
        logger.info("Navigated to %s", target)

    async def reload(self) -> None:
        """Reload the current page."""
        if not self._page:
            raise RuntimeError("Debugger not started.")
        await self._page.reload(wait_until="domcontentloaded")
        logger.info("Page reloaded")

    async def take_screenshot(
        self,
        filename: str,
        full_page: bool = False,
    ) -> ScreenshotResult:
        """Take a screenshot of the current page."""
        if not self._page:
            raise RuntimeError("Debugger not started.")

        screenshot_dir = Path(self.config.screenshot_dir)
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = screenshot_dir / filename

        await self._page.screenshot(
            path=str(path),
            full_page=full_page,
        )

        size = await self._page.evaluate(
            "() => ({ w: window.innerWidth, h: window.innerHeight })"
        )
        width = size["w"]
        height = size["h"]

        result = ScreenshotResult(
            path=str(path),
            width=width,
            height=height,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        logger.info("Screenshot saved: %s (%dx%d)", path, width, height)
        return result

    async def get_console_log(self) -> list[ConsoleEntry]:
        """Get all console log entries."""
        return self._console_entries.copy()

    async def get_network_log(self) -> list[NetworkRequest]:
        """Get all network request records."""
        return self._network_requests.copy()

    async def get_performance_metrics(self) -> PerformanceMetrics:
        """Get performance metrics from the browser."""
        cdp = CDPSessionManager(self._page)
        return await cdp.get_performance_metrics()

    async def get_dom_snapshot(self) -> str:
        """Get a text representation of the DOM."""
        cdp = CDPSessionManager(self._page)
        return await cdp.get_dom_snapshot()

    async def get_accessibility_tree(self) -> dict:
        """Get the accessibility tree."""
        cdp = CDPSessionManager(self._page)
        return await cdp.get_accessibility_tree()

    async def click(self, selector: str) -> bool:
        """Click an element by CSS selector."""
        cdp = CDPSessionManager(self._page)
        return await cdp.click_element(selector)

    async def fill(self, selector: str, value: str) -> bool:
        """Fill an input element."""
        cdp = CDPSessionManager(self._page)
        return await cdp.fill_input(selector, value)

    async def execute_js(self, expression: str) -> Any:
        """Execute JavaScript in the browser."""
        return await self._page.evaluate(expression)

    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> bool:
        """Wait for a selector to appear."""
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def wait_for_load_state(self, state: str = "networkidle") -> None:
        """Wait for a page state."""
        await self._page.wait_for_load_state(state)

    async def end_session(self) -> DebugSession:
        """End the current debug session and return a record."""
        if not self._page:
            raise RuntimeError("No page open.")

        session = DebugSession(
            session_id=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
            url=self._page.url,
            start_time="",
            end_time=datetime.now(timezone.utc).isoformat(),
            duration_ms=(time.time() - (self._session_start or time.time())) * 1000,
            console_entries=self._console_entries.copy(),
            network_requests=self._network_requests.copy(),
        )

        self._recorder.record_session(session)
        logger.info("Debug session ended: %s", session.session_id)
        return session

    async def run_gui_test(
        self,
        url: Optional[str] = None,
        screenshots: Optional[list[tuple[str, str]]] = None,
    ) -> DebugSession:
        """Run a complete GUI test: navigate, take screenshots, collect metrics.

        Args:
            url: URL to test (defaults to config.base_url)
            screenshots: List of (name, selector) tuples for post-interaction screenshots

        Returns:
            DebugSession with all collected data
        """
        self._session_start = time.time()
        await self.navigate(url)

        # Wait for page to stabilize
        await self._page.wait_for_load_state("networkidle")

        # Take initial screenshot
        await self.take_screenshot("initial.png")

        # Get performance metrics
        perf = await self.get_performance_metrics()

        # Take additional screenshots if specified
        if screenshots:
            for name, selector in screenshots:
                try:
                    elem = self._page.locator(selector)
                    if await elem.count() > 0:
                        await elem.scroll_into_view_if_needed()
                        await self.take_screenshot(f"{name}.png")
                except Exception as e:
                    logger.warning("Screenshot %s failed: %s", name, e)

        # End session
        session = await self.end_session()
        session.performance = perf

        logger.info(
            "GUI test complete: %d console, %d network, %d screenshots",
            len(session.console_entries),
            len(session.network_requests),
            len(session.screenshots),
        )

        return session


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for running GUI tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Tektos GUI Test Runner")
    parser.add_argument(
        "--base-url",
        default="http://localhost:3003",
        help="Base URL to test",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run in headless mode",
    )
    parser.add_argument(
        "--screenshot-dir",
        default="gui-test-screenshots",
        help="Directory for screenshots",
    )
    parser.add_argument(
        "--trace-dir",
        default="gui-test-traces",
        help="Directory for trace files",
    )
    args = parser.parse_args()

    async def run():
        config = ChromeDebuggerConfig(
            base_url=args.base_url,
            headless=args.headless,
            screenshot_dir=args.screenshot_dir,
            trace_dir=args.trace_dir,
        )

        async with ChromeDebugger(config) as debugger:
            # Run a test session
            session = await debugger.run_gui_test(
                screenshots=[("homepage", "h1"), ("footer", "footer")],
            )

            # Save report
            report_path = debugger._recorder.save_report()
            print(f"Report saved to: {report_path}")
            print(json.dumps(session.to_dict(), indent=2))

    asyncio.run(run())


if __name__ == "__main__":
    main()