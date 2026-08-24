"""Dynamic llama.cpp settings — per-request parameters that can be changed without reloading.

These settings are ordered by importance (most to least):
1. temperature — controls randomness (0.0-2.0)
2. stop — stop sequences
3. seed — reproducibility
4. enable-thinking — enable reasoning mode
5. reasoning-effort — reasoning depth (low/medium/high)
6. n-predict — max tokens to generate
7. top-p — nucleus sampling threshold
8. top-k — top-k sampling
9. min-p — minimum probability threshold
10. repeat-penalty — penalize repetition
11. n-draft — speculative decoding draft tokens
12. logit-bias — token probability bias
13. grammar/JSON schema — structured output
14. presence-penalty — penalize token presence
15. frequency-penalty — penalize token frequency
16. cache-prompt — prompt caching
17. chat-template — chat template
18. p-split — split threshold for speculative decoding

This module provides:
- DynamicSettings: manages all settings with defaults and validation
- SettingsOptimizer: adjusts settings based on inference metrics and task type
- SettingsContext: per-request settings context for the SDK
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


class TaskType(Enum):
    """Task types that influence settings optimization."""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    PLANNING = "planning"
    DEBUGGING = "debugging"
    SIMPLE_QUERY = "simple_query"
    CREATIVE_WRITING = "creative_writing"
    DATA_ANALYSIS = "data_analysis"
    REASONING = "reasoning"


class ReasoningEffort(Enum):
    """Reasoning effort levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class DynamicSettings:
    """Manages all dynamic llama.cpp settings.
    
    These settings can be changed per-request without reloading the model.
    """
    
    # Core settings
    temperature: float = 0.7
    stop: list[str] = field(default_factory=list)
    seed: int = -1  # -1 = random
    enable_thinking: bool = False
    reasoning_effort: ReasoningEffort = ReasoningEffort.MEDIUM
    n_predict: int = 4096
    
    # Sampling settings
    top_p: float = 0.95
    top_k: int = 40
    min_p: float = 0.05
    
    # Repetition control
    repeat_penalty: float = 1.1
    
    # Speculative decoding
    n_draft: int = 0
    
    # Token bias
    logit_bias: dict[str, float] = field(default_factory=dict)
    
    # Structured output
    grammar: str | None = None
    json_schema: dict[str, Any] | None = None
    
    # Penalty settings
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    
    # Caching
    cache_prompt: bool = True
    
    # Chat template
    chat_template: str | None = None
    
    # Speculative split
    p_split: float = 0.1
    
    # Computed settings
    _last_updated: float = field(default_factory=time.time)
    _update_count: int = 0
    
    def to_payload(self) -> dict[str, Any]:
        """Convert to llama.cpp /chat/completions payload parameters."""
        payload: dict[str, Any] = {}
        
        if self.temperature != 0.7:
            payload["temperature"] = self.temperature
        if self.stop:
            payload["stop"] = self.stop
        if self.seed != -1:
            payload["seed"] = self.seed
        if self.enable_thinking:
            payload["enable_thinking"] = self.enable_thinking
        if self.reasoning_effort != ReasoningEffort.MEDIUM:
            payload["reasoning_effort"] = self.reasoning_effort.value
        if self.n_predict != 4096:
            payload["n_predict"] = self.n_predict
        if self.top_p != 0.95:
            payload["top_p"] = self.top_p
        if self.top_k != 40:
            payload["top_k"] = self.top_k
        if self.min_p != 0.05:
            payload["min_p"] = self.min_p
        if self.repeat_penalty != 1.1:
            payload["repeat_penalty"] = self.repeat_penalty
        if self.n_draft > 0:
            payload["n_draft"] = self.n_draft
        if self.logit_bias:
            payload["logit_bias"] = self.logit_bias
        if self.grammar:
            payload["grammar"] = self.grammar
        if self.json_schema:
            payload["json_schema"] = self.json_schema
        if self.presence_penalty != 0.0:
            payload["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty != 0.0:
            payload["frequency_penalty"] = self.frequency_penalty
        if self.cache_prompt:
            payload["cache_prompt"] = self.cache_prompt
        if self.chat_template:
            payload["chat_template"] = self.chat_template
        if self.p_split != 0.1:
            payload["p_split"] = self.p_split
        
        return payload
    
    def update(self, **kwargs: Any) -> None:
        """Update settings with new values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self._last_updated = time.time()
        self._update_count += 1
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self.temperature = 0.7
        self.stop = []
        self.seed = -1
        self.enable_thinking = False
        self.reasoning_effort = ReasoningEffort.MEDIUM
        self.n_predict = 4096
        self.top_p = 0.95
        self.top_k = 40
        self.min_p = 0.05
        self.repeat_penalty = 1.1
        self.n_draft = 0
        self.logit_bias = {}
        self.grammar = None
        self.json_schema = None
        self.presence_penalty = 0.0
        self.frequency_penalty = 0.0
        self.cache_prompt = True
        self.chat_template = None
        self.p_split = 0.1
        self._last_updated = time.time()
        self._update_count += 1
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "temperature": self.temperature,
            "n_predict": self.n_predict,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "enable_thinking": self.enable_thinking,
            "reasoning_effort": self.reasoning_effort.value,
            "update_count": self._update_count,
        }


@dataclass
class SettingsOptimizer:
    """Optimizes dynamic settings based on task type and inference metrics.
    
    Uses inference metrics (throughput, cache hit rates, VRAM) to adjust
    settings for optimal performance and quality.
    """
    
    settings: DynamicSettings = field(default_factory=DynamicSettings)
    _task_history: list[dict[str, Any]] = field(default_factory=list)
    _metric_history: list[dict[str, Any]] = field(default_factory=list)
    
    def optimize_for_task(self, task_type: TaskType, prompt: str) -> DynamicSettings:
        """Optimize settings for a specific task type.
        
        Args:
            task_type: The type of task being performed.
            prompt: The user's prompt.
        
        Returns:
            Optimized DynamicSettings.
        """
        optimized = DynamicSettings()
        
        # Task-specific settings
        if task_type == TaskType.CODE_GENERATION:
            optimized.temperature = 0.3  # Lower for code
            optimized.top_p = 0.9
            optimized.top_k = 20
            optimized.n_predict = 8192  # Longer generations
            optimized.repeat_penalty = 1.2
            optimized.cache_prompt = True
        
        elif task_type == TaskType.CODE_REVIEW:
            optimized.temperature = 0.1  # Very deterministic
            optimized.top_p = 0.8
            optimized.top_k = 10
            optimized.n_predict = 2048
            optimized.repeat_penalty = 1.3
        
        elif task_type == TaskType.PLANNING:
            optimized.temperature = 0.5
            optimized.top_p = 0.95
            optimized.top_k = 30
            optimized.n_predict = 16384  # Long planning
            optimized.enable_thinking = True
            optimized.reasoning_effort = ReasoningEffort.HIGH
        
        elif task_type == TaskType.DEBUGGING:
            optimized.temperature = 0.2
            optimized.top_p = 0.85
            optimized.top_k = 15
            optimized.n_predict = 4096
            optimized.enable_thinking = True
            optimized.reasoning_effort = ReasoningEffort.HIGH
        
        elif task_type == TaskType.SIMPLE_QUERY:
            optimized.temperature = 0.1
            optimized.top_p = 0.9
            optimized.top_k = 20
            optimized.n_predict = 1024  # Short responses
            optimized.cache_prompt = True
        
        elif task_type == TaskType.CREATIVE_WRITING:
            optimized.temperature = 0.9
            optimized.top_p = 0.98
            optimized.top_k = 50
            optimized.n_predict = 8192
            optimized.repeat_penalty = 1.0
        
        elif task_type == TaskType.DATA_ANALYSIS:
            optimized.temperature = 0.2
            optimized.top_p = 0.85
            optimized.top_k = 15
            optimized.n_predict = 4096
            optimized.json_schema = {"type": "object", "properties": {"analysis": {"type": "string"}}}
        
        elif task_type == TaskType.REASONING:
            optimized.temperature = 0.3
            optimized.top_p = 0.9
            optimized.top_k = 20
            optimized.n_predict = 16384
            optimized.enable_thinking = True
            optimized.reasoning_effort = ReasoningEffort.HIGH
        
        # Apply metric-based optimizations
        self._apply_metric_optimizations(optimized)
        
        # Record this optimization
        self._task_history.append({
            "task_type": task_type.value,
            "settings": optimized.to_memory_entry(),
            "timestamp": time.time(),
        })
        
        return optimized
    
    def _apply_metric_optimizations(self, settings: DynamicSettings) -> None:
        """Apply optimizations based on collected inference metrics."""
        if not self._metric_history:
            return
        
        # Get recent metrics (last 10)
        recent = self._metric_history[-10:]
        avg_cache_hit = sum(m.get("cache_hit_rate", 0) for m in recent) / len(recent)
        avg_throughput = sum(m.get("throughput", 0) for m in recent) / len(recent)
        
        # If cache hit rate is low, increase n_predict to encourage caching
        if avg_cache_hit < 0.5:
            settings.n_predict = min(int(settings.n_predict * 1.2), 32768)
        
        # If throughput is low, reduce n_predict to avoid long generations
        if avg_throughput < 50:
            settings.n_predict = min(settings.n_predict, 2048)
        
        # If VRAM is high, reduce n_predict to avoid OOM
        for m in recent:
            if m.get("gpu_vram_utilization", 0) > 0.9:
                settings.n_predict = min(settings.n_predict, 4096)
                break
    
    def record_metric(self, metric: dict[str, Any]) -> None:
        """Record inference metric for future optimization."""
        self._metric_history.append(metric)
        # Keep only last 100 metrics
        if len(self._metric_history) > 100:
            self._metric_history = self._metric_history[-100:]
    
    def get_recommendations(self) -> list[str]:
        """Get optimization recommendations based on history."""
        recommendations: list[str] = []
        
        if not self._task_history:
            return recommendations
        
        # Analyze task history
        task_counts: dict[str, int] = {}
        for entry in self._task_history:
            task_type = entry["task_type"]
            task_counts[task_type] = task_counts.get(task_type, 0) + 1
        
        # If planning tasks are frequent, recommend higher n_predict
        if task_counts.get("planning", 0) > 5:
            recommendations.append("Increase n_predict for planning tasks")
        
        # If code generation tasks are frequent, recommend lower temperature
        if task_counts.get("code_generation", 0) > 10:
            recommendations.append("Consider lowering temperature for code generation")
        
        return recommendations
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "task_history_count": len(self._task_history),
            "metric_history_count": len(self._metric_history),
            "recommendations": self.get_recommendations(),
        }


# ── Convenience Functions ───────────────────────────────────────────────────

_optimizer: SettingsOptimizer | None = None


def get_optimizer() -> SettingsOptimizer:
    """Get or create the settings optimizer."""
    global _optimizer
    if _optimizer is None:
        _optimizer = SettingsOptimizer()
    return _optimizer


def detect_task_type(prompt: str) -> TaskType:
    """Detect task type from prompt.
    
    Args:
        prompt: The user's prompt.
    
    Returns:
        Detected TaskType.
    """
    prompt_lower = prompt.lower()
    
    if any(kw in prompt_lower for kw in ["plan", "design", "architect", "strategy"]):
        return TaskType.PLANNING
    elif any(kw in prompt_lower for kw in ["debug", "fix", "error", "bug"]):
        return TaskType.DEBUGGING
    elif any(kw in prompt_lower for kw in ["review", "audit", "check"]):
        return TaskType.CODE_REVIEW
    elif any(kw in prompt_lower for kw in ["write code", "implement", "create", "build"]):
        return TaskType.CODE_GENERATION
    elif any(kw in prompt_lower for kw in ["analyze", "data", "statistics"]):
        return TaskType.DATA_ANALYSIS
    elif any(kw in prompt_lower for kw in ["reason", "think", "explain"]):
        return TaskType.REASONING
    elif any(kw in prompt_lower for kw in ["creative", "story", "poem", "write"]):
        return TaskType.CREATIVE_WRITING
    else:
        return TaskType.SIMPLE_QUERY
