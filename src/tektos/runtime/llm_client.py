"""OpenAI-compatible LLM client with primary/fallback failover.

Wraps two ``httpx.AsyncClient`` instances — one for the primary endpoint and
one for the fallback — behind an interface that mirrors the subset of
``httpx.AsyncClient`` used by :class:`tektos.runtime.sdk.RuntimeSDK`:

    - ``async get(path, **kwargs)`` — used for ``/models`` health probes
    - ``async post(path, **kwargs)`` — used for ``/chat/completions`` etc.
    - ``async aclose()``            — teardown
    - ``base_url`` and ``model`` properties reporting the *currently active*
      endpoint, so callers building request payloads see the right model name.

Failover semantics:

    1. Requests are first attempted against the primary endpoint.
    2. If the primary raises a connect/read/timeout error, or returns a 5xx
       status, the client marks the primary "down" for ``cooldown_seconds``
       and immediately retries the same request against the fallback.
    3. While the primary is down, requests go straight to the fallback
       without re-probing the primary. After ``cooldown_seconds`` elapses,
       the next request re-tries the primary first.
    4. If the fallback also fails, the exception from the fallback is
       raised. The primary's exception is chained via ``__cause__``.

The wrapper also rewrites the OpenAI-style ``model`` field in JSON bodies
so downstream servers see the right model alias for whichever endpoint is
actually being called.

Failover can be disabled by constructing with ``fallback_url=None`` or
``enabled=False`` — the wrapper then behaves like a plain
``httpx.AsyncClient`` pointed at the primary.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)


# Exceptions that we treat as "primary is down, try fallback".
# httpx.HTTPStatusError is handled separately (only 5xx trigger failover).
_TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
)


class FailoverLLMClient:
    """Primary/fallback wrapper around two ``httpx.AsyncClient`` instances.

    Presents the small surface :class:`RuntimeSDK` actually uses, so it can
    drop-in replace ``self._client`` without touching the request-issuing
    code paths.
    """

    def __init__(
        self,
        primary_url: str,
        primary_model: str,
        *,
        fallback_url: str | None = None,
        fallback_model: str | None = None,
        enabled: bool = True,
        cooldown_seconds: float = 30.0,
        timeout: httpx.Timeout | None = None,
        limits: httpx.Limits | None = None,
    ) -> None:
        self._primary_url = primary_url.rstrip("/")
        self._primary_model = primary_model
        self._fallback_url = fallback_url.rstrip("/") if fallback_url else None
        self._fallback_model = fallback_model
        self._enabled = bool(enabled and fallback_url and fallback_model)
        self._cooldown_seconds = float(cooldown_seconds)

        timeout = timeout or httpx.Timeout(30.0, read=300.0)
        limits = limits or httpx.Limits(max_connections=10, max_keepalive_connections=5)

        self._primary = httpx.AsyncClient(
            base_url=self._primary_url, timeout=timeout, limits=limits
        )
        self._fallback: httpx.AsyncClient | None = None
        if self._enabled and self._fallback_url is not None:
            self._fallback = httpx.AsyncClient(
                base_url=self._fallback_url, timeout=timeout, limits=limits
            )

        # State
        self._primary_down_until: float = 0.0  # monotonic timestamp; 0 = healthy
        self._active_is_fallback: bool = False  # updated after each successful call
        self._failover_count: int = 0
        self._recovery_count: int = 0

    # ── Public surface used by RuntimeSDK ────────────────────────────────

    @property
    def base_url(self) -> str:
        """URL of whichever endpoint served the most recent successful request."""
        if self._active_is_fallback and self._fallback_url is not None:
            return self._fallback_url
        return self._primary_url

    @property
    def model(self) -> str:
        """Model alias of whichever endpoint served the most recent successful request."""
        if self._active_is_fallback and self._fallback_model is not None:
            return self._fallback_model
        return self._primary_model

    @property
    def failover_enabled(self) -> bool:
        return self._enabled

    @property
    def is_on_fallback(self) -> bool:
        return self._active_is_fallback

    @property
    def failover_count(self) -> int:
        return self._failover_count

    @property
    def recovery_count(self) -> int:
        return self._recovery_count

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        # Rewrite ``json.model`` so the request names the model alias of
        # whichever endpoint we actually end up sending to. We can't know
        # which endpoint that is until we try, so we rewrite twice if the
        # primary attempt fails.
        return await self._request("POST", path, **kwargs)

    def stream(self, method: str, path: str, **kwargs: Any) -> "_FailoverStream":
        """Return an async context manager that streams a request through the
        primary→fallback logic. Use for endpoints where the caller wants to
        consume the response body incrementally (``aiter_lines()``,
        ``aiter_bytes()``, etc.) instead of buffering the whole body.

        The returned object mirrors ``httpx.AsyncClient.stream``: it must be
        used with ``async with client.stream(...) as resp: ...``. Failover
        happens on entry; once a streaming response is yielded, the caller
        owns it and further failover is not possible.
        """
        return _FailoverStream(self, method, path, kwargs)

    async def aclose(self) -> None:
        await self._primary.aclose()
        if self._fallback is not None:
            await self._fallback.aclose()

    # ── Internal ─────────────────────────────────────────────────────────

    def _primary_is_cooling(self) -> bool:
        return time.monotonic() < self._primary_down_until

    def _mark_primary_down(self) -> None:
        was_up = not self._active_is_fallback
        self._primary_down_until = time.monotonic() + self._cooldown_seconds
        self._active_is_fallback = True
        if was_up:
            self._failover_count += 1
            log.warning(
                "LLM primary failover: routing to fallback %s (model=%s) "
                "for %.0fs — reason will be logged by caller",
                self._fallback_url,
                self._fallback_model,
                self._cooldown_seconds,
            )

    def _mark_primary_recovered(self) -> None:
        was_down = self._active_is_fallback
        self._primary_down_until = 0.0
        self._active_is_fallback = False
        if was_down:
            self._recovery_count += 1
            log.info(
                "LLM primary recovered: routing to %s (model=%s)",
                self._primary_url,
                self._primary_model,
            )

    def _rewrite_model_field(self, kwargs: dict[str, Any], model: str) -> None:
        body = kwargs.get("json")
        if isinstance(body, dict) and "model" in body:
            # Make a shallow copy so we don't mutate the caller's dict
            new_body = dict(body)
            new_body["model"] = model
            kwargs["json"] = new_body

    async def _try(
        self,
        client: httpx.AsyncClient,
        model: str,
        method: str,
        path: str,
        kwargs: dict[str, Any],
    ) -> httpx.Response:
        # Copy kwargs so successive attempts don't stomp each other's json body
        call_kwargs = dict(kwargs)
        self._rewrite_model_field(call_kwargs, model)
        resp = await client.request(method, path, **call_kwargs)
        # 5xx should trigger failover; 4xx should NOT (it's a client error,
        # would fail identically on the fallback).
        if resp.status_code >= 500:
            resp.raise_for_status()
        return resp

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        # Fast path: failover disabled — behave like a plain AsyncClient
        # pointed at the primary.
        if not self._enabled or self._fallback is None:
            log.info(
                "LLM %s %s -> primary (failover disabled): %s",
                method, path, self._primary_url,
            )
            return await self._primary.request(method, path, **kwargs)

        # If the primary is in cooldown, go straight to the fallback.
        if self._primary_is_cooling():
            log.info(
                "LLM %s %s -> fallback (primary cooling): %s",
                method, path, self._fallback_url,
            )
            try:
                resp = await self._try(self._fallback, self._fallback_model or "", method, path, kwargs)
                self._active_is_fallback = True
                return resp
            except _TRANSIENT_EXCEPTIONS + (httpx.HTTPStatusError,):
                raise

        # Normal path: try primary first.
        log.info(
            "LLM %s %s -> primary attempt: %s",
            method, path, self._primary_url,
        )
        primary_exc: BaseException | None = None
        try:
            resp = await self._try(self._primary, self._primary_model, method, path, kwargs)
            log.info(
                "LLM %s %s -> primary OK: status=%d",
                method, path, resp.status_code,
            )
            self._mark_primary_recovered()
            return resp
        except _TRANSIENT_EXCEPTIONS as exc:
            primary_exc = exc
            log.warning(
                "LLM primary %s failed with %s: %s — attempting fallback",
                self._primary_url,
                type(exc).__name__,
                exc,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                # Client error — do NOT fail over.
                log.info(
                    "LLM primary returned %d (client error) — passthrough, no failover",
                    exc.response.status_code,
                )
                raise
            primary_exc = exc
            log.warning(
                "LLM primary %s returned %d — attempting fallback",
                self._primary_url,
                exc.response.status_code,
            )

        # Primary failed — mark down and try fallback.
        self._mark_primary_down()
        log.info(
            "LLM %s %s -> fallback attempt: %s (model=%s)",
            method, path, self._fallback_url, self._fallback_model,
        )
        try:
            resp = await self._try(self._fallback, self._fallback_model or "", method, path, kwargs)
            log.info(
                "LLM %s %s -> fallback OK: status=%d",
                method, path, resp.status_code,
            )
            self._active_is_fallback = True
            return resp
        except Exception as fallback_exc:
            log.error(
                "LLM fallback %s also failed with %s: %s",
                self._fallback_url,
                type(fallback_exc).__name__,
                fallback_exc,
            )
            # Chain the primary exception so callers see both.
            raise fallback_exc from primary_exc


class _FailoverStream:
    """Async context manager that opens a streaming request through the
    :class:`FailoverLLMClient` primary→fallback logic.

    Failover is tried once on entry (``__aenter__``). Once the response is
    yielded, the caller owns it — mid-stream failover is not supported
    because the caller may already have consumed partial output.
    """

    def __init__(
        self,
        client: FailoverLLMClient,
        method: str,
        path: str,
        kwargs: dict[str, Any],
    ) -> None:
        self._client = client
        self._method = method
        self._path = path
        self._kwargs = kwargs
        # These are populated by __aenter__ and torn down by __aexit__.
        self._httpx_stream_cm: Any = None
        self._resp: httpx.Response | None = None

    async def __aenter__(self) -> httpx.Response:
        c = self._client
        method, path, kwargs = self._method, self._path, self._kwargs

        # Fast path: failover disabled — stream straight from primary.
        if not c._enabled or c._fallback is None:
            log.info(
                "LLM %s %s -> primary stream (failover disabled): %s",
                method, path, c._primary_url,
            )
            call_kwargs = dict(kwargs)
            c._rewrite_model_field(call_kwargs, c._primary_model)
            self._httpx_stream_cm = c._primary.stream(method, path, **call_kwargs)
            self._resp = await self._httpx_stream_cm.__aenter__()
            return self._resp

        # If primary is cooling, go straight to fallback stream.
        if c._primary_is_cooling():
            log.info(
                "LLM %s %s -> fallback stream (primary cooling): %s (model=%s)",
                method, path, c._fallback_url, c._fallback_model,
            )
            call_kwargs = dict(kwargs)
            c._rewrite_model_field(call_kwargs, c._fallback_model or "")
            try:
                self._httpx_stream_cm = c._fallback.stream(method, path, **call_kwargs)
                self._resp = await self._httpx_stream_cm.__aenter__()
                c._active_is_fallback = True
                log.info(
                    "LLM %s %s -> fallback stream OK: status=%d",
                    method, path, self._resp.status_code,
                )
                return self._resp
            except Exception as exc:
                log.error(
                    "LLM fallback stream %s failed with %s: %s",
                    c._fallback_url, type(exc).__name__, exc,
                )
                raise

        # Try primary first.
        primary_exc: Exception | None = None
        log.info(
            "LLM %s %s -> primary stream attempt: %s",
            method, path, c._primary_url,
        )
        try:
            call_kwargs = dict(kwargs)
            c._rewrite_model_field(call_kwargs, c._primary_model)
            self._httpx_stream_cm = c._primary.stream(method, path, **call_kwargs)
            self._resp = await self._httpx_stream_cm.__aenter__()
            # Treat 5xx as failover-worthy; 4xx passes through.
            if self._resp.status_code >= 500:
                status = self._resp.status_code
                # Close the primary stream cleanly before falling over.
                await self._httpx_stream_cm.__aexit__(None, None, None)
                self._httpx_stream_cm = None
                self._resp = None
                primary_exc = httpx.HTTPStatusError(
                    f"primary returned {status}", request=None, response=None  # type: ignore[arg-type]
                )
                log.warning(
                    "LLM primary stream %s returned %d — attempting fallback",
                    c._primary_url, status,
                )
            else:
                log.info(
                    "LLM %s %s -> primary stream OK: status=%d",
                    method, path, self._resp.status_code,
                )
                c._mark_primary_recovered()
                return self._resp
        except _TRANSIENT_EXCEPTIONS as exc:
            primary_exc = exc
            log.warning(
                "LLM primary stream %s failed with %s: %s — attempting fallback",
                c._primary_url, type(exc).__name__, exc,
            )
            # If __aenter__ succeeded partially, tear it down.
            if self._httpx_stream_cm is not None:
                try:
                    await self._httpx_stream_cm.__aexit__(type(exc), exc, exc.__traceback__)
                except Exception:
                    log.debug("primary stream teardown after failure raised", exc_info=True)
                self._httpx_stream_cm = None
            self._resp = None

        # Primary failed — mark down and stream from fallback.
        c._mark_primary_down()
        log.info(
            "LLM %s %s -> fallback stream attempt: %s (model=%s)",
            method, path, c._fallback_url, c._fallback_model,
        )
        try:
            call_kwargs = dict(kwargs)
            c._rewrite_model_field(call_kwargs, c._fallback_model or "")
            self._httpx_stream_cm = c._fallback.stream(method, path, **call_kwargs)
            self._resp = await self._httpx_stream_cm.__aenter__()
            log.info(
                "LLM %s %s -> fallback stream OK: status=%d",
                method, path, self._resp.status_code,
            )
            c._active_is_fallback = True
            return self._resp
        except Exception as fallback_exc:
            log.error(
                "LLM fallback stream %s also failed with %s: %s",
                c._fallback_url, type(fallback_exc).__name__, fallback_exc,
            )
            raise fallback_exc from primary_exc

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._httpx_stream_cm is not None:
            try:
                await self._httpx_stream_cm.__aexit__(exc_type, exc, tb)
            finally:
                self._httpx_stream_cm = None
                self._resp = None


def build_llm_client(cfg: Any) -> FailoverLLMClient:
    """Build a :class:`FailoverLLMClient` from a :class:`tektos.config.LLMConfig`.

    Accepts the config object rather than raw fields so callers don't have to
    unpack it themselves. ``cfg`` is typed as ``Any`` to avoid a circular
    import between ``config`` and ``runtime.llm_client``.
    """
    return FailoverLLMClient(
        primary_url=cfg.base_url,
        primary_model=cfg.model,
        fallback_url=cfg.fallback_url,
        fallback_model=cfg.fallback_model,
        enabled=cfg.failover_enabled,
        cooldown_seconds=cfg.failover_cooldown_seconds,
        timeout=httpx.Timeout(30.0, read=cfg.timeout),
    )
