"""Unit tests for tektos.runtime.approval_registry."""

from __future__ import annotations

import asyncio

import pytest

from tektos.runtime.approval_registry import (
    ApprovalRegistry,
    PendingApproval,
    get_approval_registry,
    reset_approval_registry,
)


@pytest.fixture(autouse=True)
def _reset_default() -> None:
    reset_approval_registry()
    yield
    reset_approval_registry()


def test_register_returns_pending_approval() -> None:
    registry = ApprovalRegistry()
    pending = registry.register("s1", "t1", "shell")
    assert isinstance(pending, PendingApproval)
    assert pending.session_id == "s1"
    assert pending.tool_id == "t1"
    assert pending.tool_name == "shell"
    assert pending.approved is False
    assert pending.resolved is False


def test_get_returns_registered_pending() -> None:
    registry = ApprovalRegistry()
    registered = registry.register("s1", "t1", "shell")
    assert registry.get("s1", "t1") is registered
    assert registry.get("s1", "missing") is None
    assert registry.get("missing", "t1") is None


def test_approve_and_reject_mark_and_return_true_first_time() -> None:
    registry = ApprovalRegistry()
    registry.register("s1", "t1", "shell")
    assert registry.approve("s1", "t1") is True
    assert registry.approve("s1", "t1") is False  # second time is a no-op

    registry.register("s1", "t2", "shell")
    assert registry.reject("s1", "t2") is True
    assert registry.reject("s1", "t2") is False


def test_approve_unknown_returns_false() -> None:
    registry = ApprovalRegistry()
    assert registry.approve("s1", "missing") is False
    assert registry.reject("s1", "missing") is False


@pytest.mark.asyncio
async def test_wait_for_decision_returns_true_on_approve() -> None:
    registry = ApprovalRegistry()
    registry.register("s1", "t1", "shell")

    async def resolver() -> None:
        await asyncio.sleep(0.01)
        registry.approve("s1", "t1")

    resolver_task = asyncio.create_task(resolver())
    approved = await registry.wait_for_decision("s1", "t1", timeout=1.0)
    await resolver_task
    assert approved is True


@pytest.mark.asyncio
async def test_wait_for_decision_returns_false_on_reject() -> None:
    registry = ApprovalRegistry()
    registry.register("s1", "t1", "shell")

    async def resolver() -> None:
        await asyncio.sleep(0.01)
        registry.reject("s1", "t1")

    resolver_task = asyncio.create_task(resolver())
    approved = await registry.wait_for_decision("s1", "t1", timeout=1.0)
    await resolver_task
    assert approved is False


@pytest.mark.asyncio
async def test_wait_for_decision_timeout_returns_false_and_marks_resolved() -> None:
    registry = ApprovalRegistry()
    pending = registry.register("s1", "t1", "shell")

    approved = await registry.wait_for_decision("s1", "t1", timeout=0.05)
    assert approved is False
    assert pending.resolved is True
    # A late approve is a no-op.
    assert registry.approve("s1", "t1") is False


@pytest.mark.asyncio
async def test_wait_for_decision_unknown_returns_false() -> None:
    registry = ApprovalRegistry()
    approved = await registry.wait_for_decision("s1", "missing", timeout=0.05)
    assert approved is False


def test_list_pending_excludes_resolved() -> None:
    registry = ApprovalRegistry()
    registry.register("s1", "t1", "shell")
    registry.register("s1", "t2", "shell")
    registry.approve("s1", "t1")

    pending = registry.list_pending("s1")
    assert {p.tool_id for p in pending} == {"t2"}


def test_discard_removes_entry() -> None:
    registry = ApprovalRegistry()
    registry.register("s1", "t1", "shell")
    registry.discard("s1", "t1")
    assert registry.get("s1", "t1") is None


def test_clear_session_wakes_and_removes_all() -> None:
    registry = ApprovalRegistry()
    p1 = registry.register("s1", "t1", "shell")
    p2 = registry.register("s1", "t2", "shell")
    registry.register("s2", "t3", "shell")

    registry.clear_session("s1")
    assert p1.resolved is True and p1.approved is False
    assert p2.resolved is True and p2.approved is False
    assert registry.get("s1", "t1") is None
    assert registry.get("s2", "t3") is not None


def test_default_registry_is_singleton() -> None:
    reset_approval_registry()
    r1 = get_approval_registry()
    r2 = get_approval_registry()
    assert r1 is r2

    reset_approval_registry()
    r3 = get_approval_registry()
    assert r3 is not r1
