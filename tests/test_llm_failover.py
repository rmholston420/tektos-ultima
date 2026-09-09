"""Tests for FailoverLLMClient — primary/fallback routing behavior.

Uses respx to stub httpx transport so the tests are deterministic and don't
require a running llama-server. Verifies:

    1. Healthy primary — requests go to primary; ``is_on_fallback`` stays False.
    2. Primary ConnectError — request fails over; subsequent requests bypass
       primary until the cooldown expires.
    3. Primary 5xx — request fails over.
    4. Primary 4xx — does NOT fail over (client error, would fail the same
       on the fallback).
    5. Fallback failure — the fallback exception propagates and chains the
       primary exception via ``__cause__``.
    6. Cooldown expires — next call retries the primary.
    7. Disabled failover — behaves like a plain httpx client pointed at
       the primary.
    8. Model rewrite — POST bodies see the model alias of whichever endpoint
       actually gets called.
"""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from tektos.runtime.llm_client import FailoverLLMClient, build_llm_client

PRIMARY = "http://primary.test/v1"
FALLBACK = "http://fallback.test/v1"


def make_client(**overrides) -> FailoverLLMClient:
    defaults = dict(
        primary_url=PRIMARY,
        primary_model="primary-model",
        fallback_url=FALLBACK,
        fallback_model="fallback-model",
        enabled=True,
        cooldown_seconds=30.0,
    )
    defaults.update(overrides)
    return FailoverLLMClient(**defaults)


# ── Happy path ──────────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_healthy_primary_serves_requests():
    respx.get(f"{PRIMARY}/models").mock(return_value=httpx.Response(200, json={"data": []}))

    client = make_client()
    resp = await client.get("/models")

    assert resp.status_code == 200
    assert client.is_on_fallback is False
    assert client.base_url == PRIMARY
    assert client.model == "primary-model"
    assert client.failover_count == 0

    await client.aclose()


# ── Failover on transient error ─────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_connect_error_triggers_failover():
    respx.get(f"{PRIMARY}/models").mock(side_effect=httpx.ConnectError("refused"))
    respx.get(f"{FALLBACK}/models").mock(return_value=httpx.Response(200, json={"data": []}))

    client = make_client()
    resp = await client.get("/models")

    assert resp.status_code == 200
    assert client.is_on_fallback is True
    assert client.base_url == FALLBACK
    assert client.model == "fallback-model"
    assert client.failover_count == 1

    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_5xx_triggers_failover():
    respx.get(f"{PRIMARY}/models").mock(return_value=httpx.Response(503, text="down"))
    respx.get(f"{FALLBACK}/models").mock(return_value=httpx.Response(200, json={"data": []}))

    client = make_client()
    resp = await client.get("/models")

    assert resp.status_code == 200
    assert client.is_on_fallback is True
    assert client.failover_count == 1

    await client.aclose()


# ── 4xx does NOT fail over ──────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_4xx_does_not_trigger_failover():
    respx.get(f"{PRIMARY}/models").mock(return_value=httpx.Response(401, text="unauthorized"))
    # Fallback should never be called — assert by NOT registering its route.

    client = make_client()
    resp = await client.get("/models")

    # 4xx is returned as-is (no raise, no failover)
    assert resp.status_code == 401
    assert client.is_on_fallback is False
    assert client.failover_count == 0

    await client.aclose()


# ── Cooldown behavior ───────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_during_cooldown_bypasses_primary():
    primary_route = respx.get(f"{PRIMARY}/models").mock(side_effect=httpx.ConnectError("down"))
    fallback_route = respx.get(f"{FALLBACK}/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    client = make_client(cooldown_seconds=30.0)

    # First call fails over
    await client.get("/models")
    assert primary_route.call_count == 1
    assert fallback_route.call_count == 1

    # Second call goes straight to fallback, primary is not retried
    await client.get("/models")
    assert primary_route.call_count == 1  # unchanged
    assert fallback_route.call_count == 2

    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_primary_retried_after_cooldown():
    primary_route = respx.get(f"{PRIMARY}/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    # Fallback shouldn't need to answer after primary recovers, but define it
    # anyway so we can assert it wasn't called on the second attempt.
    fallback_route = respx.get(f"{FALLBACK}/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    client = make_client(cooldown_seconds=30.0)
    # Force the client into cooldown as if primary just failed
    client._primary_down_until = time.monotonic() + 30
    client._active_is_fallback = True

    # During cooldown → fallback
    await client.get("/models")
    assert fallback_route.call_count == 1
    assert primary_route.call_count == 0

    # Advance past cooldown by rewriting the clock threshold
    client._primary_down_until = time.monotonic() - 1

    # Now primary should be retried and succeed → active flips back
    await client.get("/models")
    assert primary_route.call_count == 1
    assert client.is_on_fallback is False
    assert client.recovery_count == 1

    await client.aclose()


# ── Fallback failure chains primary exception ───────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_fallback_failure_chains_primary_exception():
    respx.get(f"{PRIMARY}/models").mock(side_effect=httpx.ConnectError("primary down"))
    respx.get(f"{FALLBACK}/models").mock(side_effect=httpx.ConnectError("fallback down"))

    client = make_client()
    with pytest.raises(httpx.ConnectError) as excinfo:
        await client.get("/models")

    # The raised exception is from the fallback attempt; primary chained via __cause__
    assert "fallback down" in str(excinfo.value)
    assert excinfo.value.__cause__ is not None
    assert "primary down" in str(excinfo.value.__cause__)

    await client.aclose()


# ── Failover disabled ───────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_disabled_failover_behaves_like_plain_client():
    respx.get(f"{PRIMARY}/models").mock(side_effect=httpx.ConnectError("down"))
    # No fallback route registered — if it were called, respx would raise.

    client = make_client(enabled=False)
    assert client.failover_enabled is False

    with pytest.raises(httpx.ConnectError):
        await client.get("/models")

    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_no_fallback_url_disables_failover():
    respx.get(f"{PRIMARY}/models").mock(side_effect=httpx.ConnectError("down"))

    client = make_client(fallback_url=None, fallback_model=None)
    assert client.failover_enabled is False

    with pytest.raises(httpx.ConnectError):
        await client.get("/models")

    await client.aclose()


# ── Model field rewrite ─────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_post_body_model_field_rewritten_on_fallback():
    captured: dict[str, object] = {}

    def _capture_primary(request):
        return httpx.Response(503, text="down")

    def _capture_fallback(request):
        import json as _json

        body = _json.loads(request.content)
        captured["fallback_model"] = body.get("model")
        return httpx.Response(200, json={"choices": []})

    respx.post(f"{PRIMARY}/chat/completions").mock(side_effect=_capture_primary)
    respx.post(f"{FALLBACK}/chat/completions").mock(side_effect=_capture_fallback)

    client = make_client()
    resp = await client.post(
        "/chat/completions",
        json={"model": "primary-model", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert resp.status_code == 200
    # Body sent to the fallback endpoint must name the fallback model,
    # not the primary model that the caller originally passed.
    assert captured["fallback_model"] == "fallback-model"

    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_post_body_model_field_preserved_on_primary():
    captured: dict[str, object] = {}

    def _capture(request):
        import json as _json

        body = _json.loads(request.content)
        captured["model"] = body.get("model")
        return httpx.Response(200, json={"choices": []})

    respx.post(f"{PRIMARY}/chat/completions").mock(side_effect=_capture)

    client = make_client()
    await client.post(
        "/chat/completions",
        json={"model": "primary-model", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert captured["model"] == "primary-model"

    await client.aclose()


# ── build_llm_client factory ────────────────────────────────────────────────

def test_build_llm_client_from_config():
    from tektos.config import LLMConfig

    cfg = LLMConfig()
    client = build_llm_client(cfg)

    assert client.base_url == cfg.base_url
    assert client.model == cfg.model
    assert client.failover_enabled is True
