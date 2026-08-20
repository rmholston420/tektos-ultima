"""Tektos-Ultima v1 — Configuration.

All external-facing URLs and settings are configurable via environment variables
with sensible localhost defaults.
"""

import os
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration for the LLM inference backend."""
    base_url: str = Field(
        default="http://127.0.0.1:8090/v1",
        description="LLM API base URL (TEKTOS_LLM_BASE_URL env var)"
    )
    timeout: float = Field(default=300.0, description="Request timeout in seconds")


class HindsightConfig(BaseModel):
    """Configuration for the Hindsight memory daemon."""
    base_url: str = Field(
        default="http://127.0.0.1:9177",
        description="Hindsight API base URL (TEKTOS_HINDSIGHT_URL env var)"
    )
    timeout: float = Field(default=30.0, description="Request timeout in seconds")


class SearXNGConfig(BaseModel):
    """Configuration for the SearXNG search backend."""
    base_url: str = Field(
        default="http://localhost:8888/search",
        description="SearXNG JSON API URL (TEKTOS_SEARXNG_URL env var)"
    )
    retry_backoff_base: float = Field(default=1.0, description="Base backoff seconds for retries")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class VisionConfig(BaseModel):
    """Configuration for the vision analysis backend."""
    base_url: str = Field(
        default="http://127.0.0.1:8083",
        description="Vision analysis base URL (TEKTOS_VISION_URL env var)"
    )
    timeout: float = Field(default=300.0, description="Request timeout in seconds")


class APIKeyConfig(BaseModel):
    """Configuration for API key authentication."""
    enabled: bool = Field(default=False, description="Enable API key auth (TEKTOS_API_KEY_ENABLED env var)")
    api_key: str | None = Field(default=None, description="API key for authentication (TEKTOS_API_KEY env var)")


class TektosConfig(BaseModel):
    """Master configuration for Tektos-Ultima v1."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    hindsight: HindsightConfig = Field(default_factory=HindsightConfig)
    searxng: SearXNGConfig = Field(default_factory=SearXNGConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    api_key: APIKeyConfig = Field(default_factory=APIKeyConfig)

    @classmethod
    def from_env(cls) -> "TektosConfig":
        """Load config from environment variables with defaults."""
        llm_url = os.getenv("TEKTOS_LLM_BASE_URL", "http://127.0.0.1:8090/v1")
        hindsight_url = os.getenv("TEKTOS_HINDSIGHT_URL", "http://127.0.0.1:9177")
        searxng_url = os.getenv("TEKTOS_SEARXNG_URL", "http://localhost:8888/search")
        vision_url = os.getenv("TEKTOS_VISION_URL", "http://127.0.0.1:8083")
        api_key_enabled = os.getenv("TEKTOS_API_KEY_ENABLED", "false").lower() == "true"
        api_key = os.getenv("TEKTOS_API_KEY")

        return cls(
            llm=LLMConfig(base_url=llm_url),
            hindsight=HindsightConfig(base_url=hindsight_url),
            searxng=SearXNGConfig(base_url=searxng_url),
            vision=VisionConfig(base_url=vision_url),
            api_key=APIKeyConfig(enabled=api_key_enabled, api_key=api_key),
        )
