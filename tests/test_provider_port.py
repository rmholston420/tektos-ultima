"""Tests for tektos.ports.provider_port.

Covers:
- Base ProviderPort Protocol structural typing.
- Kind-specific Protocols (SearchProviderPort, SandboxProviderPort, ...).
- SandboxProvider concrete class satisfies SandboxProviderPort at runtime.
"""

from __future__ import annotations

from typing import Any

import pytest

from tektos.ports import (
    ProviderPort,
    SandboxProviderPort,
    SearchProviderPort,
    VisionProviderPort,
)
from tektos.providers.sandbox_provider import SandboxProvider


class _FakeSearch:
    name = "fake-search"
    kind = "search"
    version = "0.0.1"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def health(self) -> bool:
        return True

    async def search(
        self, query: str, *, limit: int = 10, **options: Any
    ) -> list[dict[str, Any]]:
        return [{"url": "http://x", "title": "t", "snippet": query}][:limit]


class _FakeVision:
    name = "fake-vision"
    kind = "vision"
    version = "0.0.1"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def health(self) -> bool:
        return True

    async def analyze(
        self, image: bytes | str, prompt: str, **options: Any
    ) -> dict[str, Any]:
        return {"answer": prompt}


class TestProviderPortStructural:
    def test_fake_search_satisfies_base_port(self) -> None:
        assert isinstance(_FakeSearch(), ProviderPort)

    def test_fake_search_satisfies_search_port(self) -> None:
        assert isinstance(_FakeSearch(), SearchProviderPort)

    def test_fake_vision_satisfies_vision_port(self) -> None:
        assert isinstance(_FakeVision(), VisionProviderPort)

    def test_fake_vision_does_not_pretend_to_be_search(self) -> None:
        # Missing `search()` \u2014 must fail SearchProviderPort even though
        # it satisfies the base ProviderPort.
        assert isinstance(_FakeVision(), ProviderPort)
        assert not isinstance(_FakeVision(), SearchProviderPort)


class TestSandboxProviderImplementsPort:
    def test_sandbox_provider_is_provider_port(self, tmp_path) -> None:
        sp = SandboxProvider(fs_root=tmp_path)
        assert isinstance(sp, ProviderPort)

    def test_sandbox_provider_is_sandbox_port(self, tmp_path) -> None:
        sp = SandboxProvider(fs_root=tmp_path)
        assert isinstance(sp, SandboxProviderPort)

    def test_sandbox_provider_exposes_metadata(self, tmp_path) -> None:
        sp = SandboxProvider(fs_root=tmp_path)
        assert sp.name == "local-sandbox"
        assert sp.kind == "sandbox"
        assert sp.version

    @pytest.mark.asyncio
    async def test_sandbox_provider_health_is_true(self, tmp_path) -> None:
        sp = SandboxProvider(fs_root=tmp_path)
        assert await sp.health() is True

    @pytest.mark.asyncio
    async def test_sandbox_provider_start_stop_are_noops(self, tmp_path) -> None:
        sp = SandboxProvider(fs_root=tmp_path)
        # Just assert they don't raise.
        await sp.start()
        await sp.stop()
