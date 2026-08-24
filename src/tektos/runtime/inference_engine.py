"""Inference Engine Monitor — llama.cpp instance discovery, metrics collection, and optimization.

Tektos is aware of its own inference infrastructure:
- Primary LLM: Qwen3.6-35B-A3B on GPU (port 8090)
- Secondary LLM: Granite4.1-8B on CPU (port 8092)
- Embedder: Qwen3-Embedding-0.6B on CPU (port 8091)

This module:
1. Discovers all llama.cpp instances via health checks
2. Collects Prometheus-style metrics from /metrics endpoint
3. Tracks performance characteristics (throughput, latency, cache hit rates)
4. Provides optimization recommendations for dynamic settings
5. Integrates with the self-improvement loop via reflection/synthesis

Metrics collected:
- Prompt tokens processed (total, cached, uncached)
- Generation tokens processed
- Prompt/generation throughput (tokens/sec)
- KV cache utilization (n_tokens_max vs configured max)
- Speculative decoding stats
- Average latency per token
- Memory usage (GPU VRAM, CPU RAM)
- System metrics (GPU utilization, temperature, system RAM)

Optimization targets:
- KV cache size (n_ctx) — adjust based on observed max sequence length
- Batch size — adjust based on throughput vs latency tradeoff
- GPU offload layers — adjust based on VRAM utilization
- Temperature/top_p — adjust based on task complexity
- LLM routing — optimize based on task type and model strengths
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Any

import httpx

log = logging.getLogger(__name__)


# ── Inference Engine Configuration ──────────────────────────────────────────

@dataclass
class LlamaCppInstance:
    """Configuration for a single llama.cpp instance."""
    port: int
    model_name: str
    model_path: str
    parameter_size: str
    quantization: str
    format: str
    capabilities: list[str]
    is_gpu: bool
    is_embedding: bool
    base_url: str = ""

    def __post_init__(self):
        self.base_url = f"http://127.0.0.1:{self.port}/v1"


# Repo size categories (for context window optimization)
class RepoSize(Enum):
    """Repository size categories that influence context window and token limits."""
    VERY_SMALL = "very_small", "<10,000 LOC"
    SMALL = "small", "10,000-100,000 LOC"
    MEDIUM = "medium", "100,000-250,000 LOC"
    LARGE = "large", "250,000-2,000,000 LOC"
    VERY_LARGE = "very_large", "2,000,000-10,000,000 LOC"
    ENTERPRISE = "enterprise", "10,000,000+ LOC"

# Current repo size
CURRENT_REPO_SIZE = RepoSize.MEDIUM
CURRENT_REPO_LOC = 145011

# Context window recommendations by repo size
REPO_SIZE_CONTEXT_RECOMMENDATIONS = {
    RepoSize.VERY_SMALL: {"max_tokens": 32768, "context_window": 16384, "memory_tiers": 2},
    RepoSize.SMALL: {"max_tokens": 65536, "context_window": 32768, "memory_tiers": 3},
    RepoSize.MEDIUM: {"max_tokens": 131072, "context_window": 65536, "memory_tiers": 4},
    RepoSize.LARGE: {"max_tokens": 262144, "context_window": 131072, "memory_tiers": 4},
    RepoSize.VERY_LARGE: {"max_tokens": 524288, "context_window": 262144, "memory_tiers": 4},
    RepoSize.ENTERPRISE: {"max_tokens": 1048576, "context_window": 524288, "memory_tiers": 4},
}

# Repo size categories (for context window optimization)
class RepoSize(Enum):
    """Repository size categories that influence context window and token limits."""
    VERY_SMALL = "very_small", "<10,000 LOC"
    SMALL = "small", "10,000-100,000 LOC"
    MEDIUM = "medium", "100,000-250,000 LOC"
    LARGE = "large", "250,000-2,000,000 LOC"
    VERY_LARGE = "very_large", "2,000,000-10,000,000 LOC"
    ENTERPRISE = "enterprise", "10,000,000+ LOC"

# Current repo size
CURRENT_REPO_SIZE = RepoSize.MEDIUM
CURRENT_REPO_LOC = 144986

# Context window recommendations by repo size
REPO_SIZE_CONTEXT_RECOMMENDATIONS = {
    RepoSize.VERY_SMALL: {"max_tokens": 32768, "context_window": 16384, "memory_tiers": 2},
    RepoSize.SMALL: {"max_tokens": 65536, "context_window": 32768, "memory_tiers": 3},
    RepoSize.MEDIUM: {"max_tokens": 131072, "context_window": 65536, "memory_tiers": 4},
    RepoSize.LARGE: {"max_tokens": 262144, "context_window": 131072, "memory_tiers": 4},
    RepoSize.VERY_LARGE: {"max_tokens": 524288, "context_window": 262144, "memory_tiers": 4},
    RepoSize.ENTERPRISE: {"max_tokens": 1048576, "context_window": 524288, "memory_tiers": 4},
}

# Repo size categories (for context window optimization)
class RepoSize(Enum):
    """Repository size categories that influence context window and token limits."""
    VERY_SMALL = "very_small", "<10,000 LOC"
    SMALL = "small", "10,000-100,000 LOC"
    MEDIUM = "medium", "100,000-250,000 LOC"
    LARGE = "large", "250,000-2,000,000 LOC"
    VERY_LARGE = "very_large", "2,000,000-10,000,000 LOC"
    ENTERPRISE = "enterprise", "10,000,000+ LOC"

# Current repo size
CURRENT_REPO_SIZE = RepoSize.MEDIUM
CURRENT_REPO_LOC = 144986

# Context window recommendations by repo size
REPO_SIZE_CONTEXT_RECOMMENDATIONS = {
    RepoSize.VERY_SMALL: {"max_tokens": 32768, "context_window": 16384, "memory_tiers": 2},
    RepoSize.SMALL: {"max_tokens": 65536, "context_window": 32768, "memory_tiers": 3},
    RepoSize.MEDIUM: {"max_tokens": 131072, "context_window": 65536, "memory_tiers": 4},
    RepoSize.LARGE: {"max_tokens": 262144, "context_window": 131072, "memory_tiers": 4},
    RepoSize.VERY_LARGE: {"max_tokens": 524288, "context_window": 262144, "memory_tiers": 4},
    RepoSize.ENTERPRISE: {"max_tokens": 1048576, "context_window": 524288, "memory_tiers": 4},
}

# Known llama.cpp instances
KNOWN_INSTANCES: dict[str, LlamaCppInstance] = {
    "primary_gpu": LlamaCppInstance(
        port=8090,
        model_name="Qwen3.6-35B-A3B-Q5_K_M",
        model_path="/home/rmholston/dev/openhands-ext-v1/models/qwen3_6-35b-a3b-bartowski-q5_k_m-gguf/Qwen_Qwen3.6-35B-A3B-Q5_K_M.gguf",
        parameter_size="35B",
        quantization="Q5_K_M",
        format="gguf",
        capabilities=["completion", "multimodal"],
        is_gpu=True,
        is_embedding=False,
    ),
    "secondary_cpu": LlamaCppInstance(
        port=8092,
        model_name="Granite4.1-8B-UD",
        model_path="",
        parameter_size="8B",
        quantization="Q4_K_M",
        format="gguf",
        capabilities=["completion"],
        is_gpu=False,
        is_embedding=False,
    ),
    "embedder_cpu": LlamaCppInstance(
        port=8091,
        model_name="Qwen3-Embedding-0.6B",
        model_path="",
        parameter_size="0.6B",
        quantization="Q4_K_M",
        format="gguf",
        capabilities=["embedding"],
        is_gpu=False,
        is_embedding=True,
    ),
}


# ── Metrics Data Model ──────────────────────────────────────────────────────

@dataclass
class LlamaCppMetrics:
    """Metrics from a single llama.cpp instance."""
    timestamp: str = ""
    
    # Token counters
    prompt_tokens_total: float = 0.0
    prompt_tokens_cached_total: float = 0.0
    tokens_predicted_total: float = 0.0
    n_decode_total: float = 0.0
    
    # Time counters
    prompt_seconds_total: float = 0.0
    tokens_predicted_seconds_total: float = 0.0
    
    # Sequence length
    n_tokens_max: float = 0.0
    
    # Speculative decoding
    spec_decode_num_draft_tokens_total: float = 0.0
    spec_decode_num_accepted_tokens_total: float = 0.0
    spec_decode_num_drafts_total: float = 0.0
    
    # Throughput gauges
    prompt_tokens_seconds: float = 0.0  # tokens/sec
    predicted_tokens_seconds: float = 0.0  # tokens/sec
    
    # KV cache
    kv_cache_usage: float = 0.0  # 0.0 to 1.0
    n_ctx_used: float = 0.0
    n_ctx_total: float = 0.0
    
    # System metrics (collected separately)
    gpu_memory_used_mb: float = 0.0
    gpu_memory_total_mb: float = 0.0
    gpu_utilization: float = 0.0
    gpu_temperature: float = 0.0
    system_ram_used_gb: float = 0.0
    system_ram_total_gb: float = 0.0
    
    # Computed metrics
    cache_hit_rate: float = 0.0
    avg_prompt_latency_ms: float = 0.0
    avg_generation_latency_ms: float = 0.0
    total_tokens_processed: float = 0.0
    
    def update_from_prometheus(self, metrics_text: str) -> None:
        """Parse Prometheus-style metrics text."""
        for line in metrics_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Parse metric name and value
            match = re.match(r'^(\S+)(?:\{[^}]*\})?\s+([\d.eE+-]+)$', line)
            if not match:
                continue
            
            name = match.group(1)
            value = float(match.group(2))
            
            if name == 'llamacpp:prompt_tokens_total':
                self.prompt_tokens_total = value
            elif name == 'llamacpp:prompt_tokens_cached_total':
                self.prompt_tokens_cached_total = value
            elif name == 'llamacpp:tokens_predicted_total':
                self.tokens_predicted_total = value
            elif name == 'llamacpp:n_decode_total':
                self.n_decode_total = value
            elif name == 'llamacpp:prompt_seconds_total':
                self.prompt_seconds_total = value
            elif name == 'llamacpp:tokens_predicted_seconds_total':
                self.tokens_predicted_seconds_total = value
            elif name == 'llamacpp:n_tokens_max':
                self.n_tokens_max = value
            elif name == 'llamacpp:spec_decode_num_draft_tokens_total':
                self.spec_decode_num_draft_tokens_total = value
            elif name == 'llamacpp:spec_decode_num_accepted_tokens_total':
                self.spec_decode_num_accepted_tokens_total = value
            elif name == 'llamacpp:spec_decode_num_drafts_total':
                self.spec_decode_num_drafts_total = value
            elif name == 'llamacpp:prompt_tokens_seconds':
                self.prompt_tokens_seconds = value
            elif name == 'llamacpp:predicted_tokens_seconds':
                self.predicted_tokens_seconds = value
            elif name == 'llamacpp:kv_cache_usage':
                self.kv_cache_usage = value
            elif name == 'llamacpp:n_ctx_used':
                self.n_ctx_used = value
            elif name == 'llamacpp:n_ctx_total':
                self.n_ctx_total = value
        
        # Compute derived metrics
        self._compute_derived()
    
    def _compute_derived(self) -> None:
        """Compute derived metrics from raw values."""
        # Cache hit rate
        if self.prompt_tokens_total > 0:
            uncached = self.prompt_tokens_total - self.prompt_tokens_cached_total
            if uncached < 0:
                uncached = 0
            self.cache_hit_rate = 1.0 - (uncached / self.prompt_tokens_total)
        
        # Average latencies
        if self.prompt_seconds_total > 0 and self.prompt_tokens_total > 0:
            self.avg_prompt_latency_ms = (self.prompt_seconds_total / self.prompt_tokens_total) * 1000
        if self.tokens_predicted_seconds_total > 0 and self.tokens_predicted_total > 0:
            self.avg_generation_latency_ms = (self.tokens_predicted_seconds_total / self.tokens_predicted_total) * 1000
        
        # Total tokens
        self.total_tokens_processed = self.prompt_tokens_total + self.tokens_predicted_total


@dataclass
class OptimizationRecommendation:
    """Recommendation for optimizing llama.cpp settings."""
    category: str  # kv_cache, batch_size, gpu_offload, routing, temperature
    metric: str
    current_value: float
    recommended_value: float
    reason: str
    priority: str  # high, medium, low
    confidence: float  # 0.0 to 1.0
    
    def to_markdown(self) -> str:
        return f"- **{self.category}**: {self.metric} → {self.recommended_value} (confidence: {self.confidence:.0%}) — {self.reason}"


@dataclass
class InferenceEngineState:
    """Complete state of the inference engine."""
    timestamp: str = ""
    instances: dict[str, LlamaCppMetrics] = field(default_factory=dict)
    recommendations: list[OptimizationRecommendation] = field(default_factory=list)
    health_status: dict[str, str] = field(default_factory=dict)
    total_tokens_processed: float = 0.0
    avg_cache_hit_rate: float = 0.0
    system_metrics: dict[str, Any] = field(default_factory=dict)


# ── Inference Engine Monitor ────────────────────────────────────────────────

class InferenceEngineMonitor:
    """Monitor and optimize llama.cpp inference instances.
    
    Discovers instances, collects metrics, and provides optimization
    recommendations based on observed performance characteristics.
    """
    
    def __init__(self, instances: dict[str, LlamaCppInstance] | None = None):
        """Initialize the monitor.
        
        Args:
            instances: Known llama.cpp instances. Defaults to KNOWN_INSTANCES.
        """
        self.instances = instances or KNOWN_INSTANCES
        self._state = InferenceEngineState()
        self._client: httpx.AsyncClient | None = None
    
    async def start(self) -> None:
        """Create HTTP client for health checks."""
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(5.0))
    
    async def stop(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def discover_instances(self) -> dict[str, LlamaCppInstance]:
        """Discover active llama.cpp instances via health checks.
        
        Returns:
            Dict of instance_id -> LlamaCppInstance for active instances.
        """
        active = {}
        
        for instance_id, instance in self.instances.items():
            try:
                assert self._client is not None
                resp = await self._client.get(f"http://127.0.0.1:{instance.port}/health")
                if resp.status_code == 200 and resp.json().get("status") == "ok":
                    active[instance_id] = instance
                    log.info(f"[InferenceEngine] Active: {instance_id} (port {instance.port})")
                else:
                    log.warning(f"[InferenceEngine] {instance_id} unhealthy: {resp.status_code}")
            except Exception as exc:
                log.warning(f"[InferenceEngine] {instance_id} not responding: {exc}")
        
        self._state.health_status = {
            iid: "healthy" if iid in active else "unhealthy"
            for iid in self.instances
        }
        
        return active
    
    async def collect_metrics(self, instance_id: str) -> LlamaCppMetrics | None:
        """Collect metrics from a single llama.cpp instance.
        
        Args:
            instance_id: The instance identifier (e.g., 'primary_gpu').
        
        Returns:
            LlamaCppMetrics if successful, None otherwise.
        """
        instance = self.instances.get(instance_id)
        if not instance:
            return None
        
        metrics = LlamaCppMetrics(timestamp=datetime.now(timezone.utc).isoformat())
        
        try:
            # Fetch Prometheus metrics
            resp = await self._client.get(f"http://127.0.0.1:{instance.port}/metrics")
            if resp.status_code == 200:
                metrics.update_from_prometheus(resp.text)
                log.debug(f"[InferenceEngine] Collected metrics from {instance_id}")
            else:
                log.warning(f"[InferenceEngine] Failed to fetch metrics from {instance_id}: {resp.status_code}")
                return None
        except Exception as exc:
            log.warning(f"[InferenceEngine] Error collecting metrics from {instance_id}: {exc}")
            return None
        
        # Collect system metrics (GPU/CPU/RAM)
        self._collect_system_metrics(metrics, instance)
        
        return metrics
    
    def _collect_system_metrics(self, metrics: LlamaCppMetrics, instance: LlamaCppInstance) -> None:
        """Collect system-level metrics (GPU, CPU, RAM)."""
        import subprocess
        
        # GPU metrics (NVIDIA)
        if instance.is_gpu:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(',')
                if len(parts) >= 4:
                    metrics.gpu_memory_used_mb = float(parts[0].strip())
                    metrics.gpu_memory_total_mb = float(parts[1].strip())
                    metrics.gpu_utilization = float(parts[2].strip())
                    metrics.gpu_temperature = float(parts[3].strip())
        
        # System RAM
        result = subprocess.run(['free', '-gb'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Mem:'):
                    parts = line.split()
                    if len(parts) >= 3:
                        metrics.system_ram_total_gb = float(parts[1])
                        metrics.system_ram_used_gb = float(parts[2])
    
    async def collect_all_metrics(self) -> InferenceEngineState:
        """Collect metrics from all active instances.
        
        Returns:
            Complete InferenceEngineState with all metrics.
        """
        active_instances = await self.discover_instances()
        
        for instance_id in active_instances:
            metrics = await self.collect_metrics(instance_id)
            if metrics:
                self._state.instances[instance_id] = metrics
        
        # Compute aggregate metrics
        if self._state.instances:
            self._state.total_tokens_processed = sum(
                m.total_tokens_processed for m in self._state.instances.values()
            )
            self._state.avg_cache_hit_rate = (
                sum(m.cache_hit_rate for m in self._state.instances.values()) /
                len(self._state.instances)
            )
        
        # Generate optimization recommendations
        self._state.recommendations = self._generate_recommendations()
        
        return self._state
    
    def _generate_recommendations(self) -> list[OptimizationRecommendation]:
        """Generate optimization recommendations based on collected metrics.
        
        Returns:
            List of OptimizationRecommendation instances.
        """
        recommendations: list[OptimizationRecommendation] = []
        
        for instance_id, metrics in self._state.instances.items():
            instance = self.instances[instance_id]
            
            # KV Cache optimization
            if metrics.n_tokens_max > 0:
                # Recommend n_ctx = max_observed * 1.2 (20% headroom)
                recommended_ctx = metrics.n_tokens_max * 1.2
                recommendations.append(OptimizationRecommendation(
                    category="kv_cache",
                    metric="n_ctx",
                    current_value=metrics.n_tokens_max,
                    recommended_value=recommended_ctx,
                    reason=f"Max observed sequence length: {metrics.n_tokens_max:.0f}. Add 20% headroom.",
                    priority="high" if metrics.n_tokens_max > 32000 else "medium",
                    confidence=0.9,
                ))
            
            # Cache hit rate optimization
            if metrics.cache_hit_rate < 0.5:
                recommendations.append(OptimizationRecommendation(
                    category="kv_cache",
                    metric="cache_hit_rate",
                    current_value=metrics.cache_hit_rate,
                    recommended_value=0.8,
                    reason=f"Low cache hit rate ({metrics.cache_hit_rate:.0%}). Consider increasing n_ctx or using prompt caching.",
                    priority="high",
                    confidence=0.85,
                ))
            
            # GPU VRAM optimization
            if instance.is_gpu and metrics.gpu_memory_total_mb > 0:
                vram_utilization = metrics.gpu_memory_used_mb / metrics.gpu_memory_total_mb
                if vram_utilization > 0.9:
                    recommendations.append(OptimizationRecommendation(
                        category="gpu_offload",
                        metric="gpu_vram_utilization",
                        current_value=vram_utilization,
                        recommended_value=0.85,
                        reason=f"VRAM utilization at {vram_utilization:.0%}. Risk of OOM. Consider reducing n_ctx or using quantization.",
                        priority="high",
                        confidence=0.95,
                    ))
                elif vram_utilization < 0.5:
                    recommendations.append(OptimizationRecommendation(
                        category="gpu_offload",
                        metric="gpu_vram_utilization",
                        current_value=vram_utilization,
                        recommended_value=0.8,
                        reason=f"VRAM underutilized at {vram_utilization:.0%}. Can increase n_ctx or use larger model.",
                        priority="medium",
                        confidence=0.8,
                    ))
            
            # Throughput optimization
            if metrics.predicted_tokens_seconds > 0:
                recommendations.append(OptimizationRecommendation(
                    category="batch_size",
                    metric="tokens_per_second",
                    current_value=metrics.predicted_tokens_seconds,
                    recommended_value=metrics.predicted_tokens_seconds * 1.2,
                    reason=f"Current throughput: {metrics.predicted_tokens_seconds:.0f} tokens/sec. Try increasing batch size.",
                    priority="medium",
                    confidence=0.7,
                ))
            
            # Routing optimization
            if instance_id == "primary_gpu" and metrics.prompt_tokens_seconds > 0:
                recommendations.append(OptimizationRecommendation(
                    category="routing",
                    metric="prompt_throughput",
                    current_value=metrics.prompt_tokens_seconds,
                    recommended_value=metrics.prompt_tokens_seconds * 1.1,
                    reason=f"Primary LLM prompt throughput: {metrics.prompt_tokens_seconds:.0f} tokens/sec. Optimize prompt formatting.",
                    priority="low",
                    confidence=0.6,
                ))
        
        # Cross-instance recommendations
        if "primary_gpu" in self._state.instances and "secondary_cpu" in self._state.instances:
            primary = self._state.instances["primary_gpu"]
            secondary = self._state.instances["secondary_cpu"]
            
            # If primary is overloaded, recommend more routing to secondary
            if primary.prompt_tokens_seconds > 5000 and secondary.predicted_tokens_seconds < 100:
                recommendations.append(OptimizationRecommendation(
                    category="routing",
                    metric="task_distribution",
                    current_value=1.0,
                    recommended_value=0.7,
                    reason="Primary GPU overloaded. Route 30% of simple tasks to secondary CPU LLM.",
                    priority="high",
                    confidence=0.85,
                ))
        
        return recommendations
    
    def get_state_summary(self) -> str:
        """Get a human-readable summary of the inference engine state.
        
        Returns:
            Markdown-formatted summary.
        """
        lines = ["# Inference Engine State", ""]
        
        # Health status
        lines.append("## Health Status")
        for instance_id, status in self._state.health_status.items():
            icon = "✓" if status == "healthy" else "✗"
            lines.append(f"- {icon} **{instance_id}**: {status}")
        lines.append("")
        
        # Metrics per instance
        for instance_id, metrics in self._state.instances.items():
            instance = self.instances[instance_id]
            lines.append(f"## {instance_id} ({instance.model_name})")
            lines.append(f"- **Model**: {instance.model_name}")
            lines.append(f"- **Total tokens**: {metrics.total_tokens_processed:,.0f}")
            lines.append(f"- **Cache hit rate**: {metrics.cache_hit_rate:.0%}")
            lines.append(f"- **Prompt throughput**: {metrics.prompt_tokens_seconds:.0f} tokens/sec")
            lines.append(f"- **Generation throughput**: {metrics.predicted_tokens_seconds:.0f} tokens/sec")
            lines.append(f"- **Max sequence length**: {metrics.n_tokens_max:.0f}")
            
            if instance.is_gpu:
                lines.append(f"- **GPU VRAM**: {metrics.gpu_memory_used_mb:.0f}/{metrics.gpu_memory_total_mb:.0f} MB ({metrics.gpu_memory_used_mb/max(metrics.gpu_memory_total_mb,1):.0%})")
                lines.append(f"- **GPU Temp**: {metrics.gpu_temperature:.0f}°C")
                lines.append(f"- **GPU Util**: {metrics.gpu_utilization:.0f}%")
            
            lines.append("")
        
        # Recommendations
        if self._state.recommendations:
            lines.append("## Optimization Recommendations")
            for rec in sorted(self._state.recommendations, key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.priority, 3)):
                lines.append(rec.to_markdown())
            lines.append("")
        
        return "\n".join(lines)
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert state to a memory entry for the self-improvement loop.
        
        Returns:
            Dict suitable for storing in MemorySystem.
        """
        return {
            "timestamp": self._state.timestamp,
            "total_tokens_processed": self._state.total_tokens_processed,
            "avg_cache_hit_rate": self._state.avg_cache_hit_rate,
            "health_status": self._state.health_status,
            "recommendations_count": len(self._state.recommendations),
            "high_priority_recommendations": sum(
                1 for r in self._state.recommendations if r.priority == "high"
            ),
        }


# ── Convenience Functions ───────────────────────────────────────────────────

_monitor: InferenceEngineMonitor | None = None


def get_monitor(instances: dict[str, LlamaCppInstance] | None = None) -> InferenceEngineMonitor:
    """Get or create the inference engine monitor."""
    global _monitor
    if _monitor is None:
        _monitor = InferenceEngineMonitor(instances)
    return _monitor


async def collect_inference_metrics() -> InferenceEngineState:
    """Collect metrics from all inference instances.
    
    Returns:
        Complete InferenceEngineState.
    """
    monitor = get_monitor()
    await monitor.start()
    try:
        return await monitor.collect_all_metrics()
    finally:
        await monitor.stop()
