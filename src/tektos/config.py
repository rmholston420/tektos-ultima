"""Tektos-Ultima v1 — Configuration.

All external-facing URLs and settings are configurable via environment variables
with sensible localhost defaults.

Endpoint layout (see ``docs/knowledge/06-tektos-architecture-reference.md``):

    Port 8090 — primary coder     — Qwen3.8-27B  (GPU, RTX 5090)
    Port 8091 — embedder          — Qwen3-Embedding-0.6B (CPU)
    Port 8092 — fallback coder    — Granite 4.1 8B (CPU)
    Port 8094 — vision            — Qwen3-VL-4B (CPU)
"""

import os

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration for the primary LLM inference backend + optional fallback."""

    base_url: str = Field(
        default="http://127.0.0.1:8090/v1",
        description="Primary LLM API base URL (TEKTOS_LLM_BASE_URL env var)",
    )
    model: str = Field(
        default="qwen3.8-27b-code",
        description="Primary LLM model alias (TEKTOS_LLM_MODEL env var)",
    )
    timeout: float = Field(default=300.0, description="Request timeout in seconds")

    # Failover — optional. If fallback_url is set and fallback is enabled,
    # runtime.llm_client.FailoverLLMClient will route requests to the fallback
    # endpoint whenever the primary is unavailable.
    fallback_url: str | None = Field(
        default="http://127.0.0.1:8092/v1",
        description="Fallback LLM API base URL (TEKTOS_LLM_FALLBACK_URL env var)",
    )
    fallback_model: str | None = Field(
        default="granite4.1-8b-instruct",
        description="Fallback LLM model alias (TEKTOS_LLM_FALLBACK_MODEL env var)",
    )
    failover_enabled: bool = Field(
        default=True,
        description="Enable automatic failover to fallback endpoint on primary failure "
        "(TEKTOS_LLM_FAILOVER_ENABLED env var)",
    )
    failover_cooldown_seconds: float = Field(
        default=30.0,
        description="Seconds to keep serving from fallback before re-probing primary "
        "(TEKTOS_LLM_FAILOVER_COOLDOWN_SECONDS env var)",
    )


class EmbedderConfig(BaseModel):
    """Configuration for the embedding backend."""

    base_url: str = Field(
        default="http://127.0.0.1:8091/v1",
        description="Embedder API base URL (TEKTOS_EMBEDDER_BASE_URL env var)",
    )
    model: str = Field(
        default="qwen3-embedding-0.6b",
        description="Embedder model alias (TEKTOS_EMBEDDER_MODEL env var)",
    )
    timeout: float = Field(default=30.0, description="Request timeout in seconds")


class HindsightConfig(BaseModel):
    """Configuration for the Hindsight memory daemon."""

    base_url: str = Field(
        default="http://127.0.0.1:9000",
        description="Hindsight API base URL (TEKTOS_HINDSIGHT_URL env var)",
    )
    timeout: float = Field(default=30.0, description="Request timeout in seconds")


class SearXNGConfig(BaseModel):
    """Configuration for the SearXNG search backend."""

    base_url: str = Field(
        default="http://localhost:8888/search",
        description="SearXNG JSON API URL (TEKTOS_SEARXNG_URL env var)",
    )
    retry_backoff_base: float = Field(default=1.0, description="Base backoff seconds for retries")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class VisionConfig(BaseModel):
    """Configuration for the vision analysis backend."""

    base_url: str = Field(
        default="http://127.0.0.1:8094/v1",
        description="Vision analysis base URL (TEKTOS_VISION_URL env var)",
    )
    model: str = Field(
        default="qwen3-vl-4b",
        description="Vision model alias (TEKTOS_VISION_MODEL env var)",
    )
    timeout: float = Field(default=300.0, description="Request timeout in seconds")


class APIKeyConfig(BaseModel):
    """Configuration for API key authentication."""

    enabled: bool = Field(
        default=False, description="Enable API key auth (TEKTOS_API_KEY_ENABLED env var)"
    )
    api_key: str | None = Field(
        default=None, description="API key for authentication (TEKTOS_API_KEY env var)"
    )


class TektosConfig(BaseModel):
    """Master configuration for Tektos-Ultima v1."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig)
    hindsight: HindsightConfig = Field(default_factory=HindsightConfig)
    searxng: SearXNGConfig = Field(default_factory=SearXNGConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    api_key: APIKeyConfig = Field(default_factory=APIKeyConfig)

    @classmethod
    def from_env(cls) -> "TektosConfig":
        """Load config from environment variables with defaults."""
        # LLM (primary)
        llm_url = os.getenv("TEKTOS_LLM_BASE_URL", "http://127.0.0.1:8090/v1")
        llm_model = os.getenv("TEKTOS_LLM_MODEL", "qwen3.8-27b-code")
        # LLM (fallback)
        llm_fallback_url = os.getenv("TEKTOS_LLM_FALLBACK_URL", "http://127.0.0.1:8092/v1")
        llm_fallback_model = os.getenv("TEKTOS_LLM_FALLBACK_MODEL", "granite4.1-8b-instruct")
        failover_enabled = os.getenv("TEKTOS_LLM_FAILOVER_ENABLED", "true").lower() == "true"
        failover_cooldown = float(os.getenv("TEKTOS_LLM_FAILOVER_COOLDOWN_SECONDS", "30"))
        # Embedder
        embedder_url = os.getenv("TEKTOS_EMBEDDER_BASE_URL", "http://127.0.0.1:8091/v1")
        embedder_model = os.getenv("TEKTOS_EMBEDDER_MODEL", "qwen3-embedding-0.6b")
        # Other services
        hindsight_url = os.getenv("TEKTOS_HINDSIGHT_URL", "http://127.0.0.1:9000")
        searxng_url = os.getenv("TEKTOS_SEARXNG_URL", "http://localhost:8888/search")
        vision_url = os.getenv("TEKTOS_VISION_URL", "http://127.0.0.1:8094/v1")
        vision_model = os.getenv("TEKTOS_VISION_MODEL", "qwen3-vl-4b")
        api_key_enabled = os.getenv("TEKTOS_API_KEY_ENABLED", "false").lower() == "true"
        api_key = os.getenv("TEKTOS_API_KEY")

        return cls(
            llm=LLMConfig(
                base_url=llm_url,
                model=llm_model,
                fallback_url=llm_fallback_url,
                fallback_model=llm_fallback_model,
                failover_enabled=failover_enabled,
                failover_cooldown_seconds=failover_cooldown,
            ),
            embedder=EmbedderConfig(base_url=embedder_url, model=embedder_model),
            hindsight=HindsightConfig(base_url=hindsight_url),
            searxng=SearXNGConfig(base_url=searxng_url),
            vision=VisionConfig(base_url=vision_url, model=vision_model),
            api_key=APIKeyConfig(enabled=api_key_enabled, api_key=api_key),
        )
