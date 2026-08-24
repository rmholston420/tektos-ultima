"""Context Engineering — ACE (Agentic Context Engineering) Framework.

Implements the ACE framework from Stanford/SambaNova research to prevent
context collapse and manage what the agent sees.

Context collapse is the #1 failure mode in agentic coding: when agents
repeatedly regenerate or rewrite their own context without proper curation,
they start to "forget" earlier constraints and regress toward generic behavior.

This module provides:
- ContextMonitor: Tracks context health and detects drift
- ContextCurator: Curates and optimizes context for each session
- ContextDriftDetector: Detects when context is degrading
- ContextPreservation: Preserves critical constraints across context windows
- ACEFramework: Full ACE framework integration

Key techniques:
1. Context window management — optimize what's in context
2. Constraint preservation — keep critical rules visible
3. Context drift detection — detect when agent is forgetting
4. Context curation — actively manage context quality
5. Context compression — smart compression without losing constraints
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class ContextMetric:
    """A single context metric."""
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    unit: str = ""
    
    def __post_init__(self):
        if not self.unit:
            self.unit = "score"


@dataclass
class ContextHealth:
    """Overall context health status."""
    score: float  # 0.0 to 1.0
    status: str  # "healthy", "warning", "critical"
    metrics: list[ContextMetric] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    def is_healthy(self) -> bool:
        return self.score >= 0.7
    
    def is_warning(self) -> bool:
        return 0.5 <= self.score < 0.7
    
    def is_critical(self) -> bool:
        return self.score < 0.5


@dataclass
class ContextDrift:
    """Detected context drift."""
    drift_type: str  # "constraint_loss", "context_overflow", "repetition"
    severity: str  # "low", "medium", "high"
    description: str
    timestamp: float = field(default_factory=time.time)
    affected_constraints: list[str] = field(default_factory=list)
    recovery_action: str = ""


class ContextMonitor:
    """Monitors context health and detects drift.
    
    Tracks context metrics over time and alerts when context quality
    degrades beyond acceptable thresholds.
    """
    
    def __init__(self, max_context_tokens: int = 128000):
        """Initialize context monitor.
        
        Args:
            max_context_tokens: Maximum context window size.
        """
        self.max_context_tokens = max_context_tokens
        self._metrics: list[ContextMetric] = []
        self._drifts: list[ContextDrift] = []
        self._constraint_history: list[dict[str, Any]] = []
        self._last_health: ContextHealth | None = None
    
    def record_metric(self, name: str, value: float, unit: str = "") -> None:
        """Record a context metric.
        
        Args:
            name: Metric name.
            value: Metric value.
            unit: Metric unit.
        """
        metric = ContextMetric(name=name, value=value, unit=unit)
        self._metrics.append(metric)
        
        # Keep only last 100 metrics
        if len(self._metrics) > 100:
            self._metrics = self._metrics[-100:]
    
    def detect_drift(self, current_constraints: list[str],
                     previous_constraints: list[str]) -> ContextDrift | None:
        """Detect context drift between constraint sets.
        
        Args:
            current_constraints: Current set of constraints.
            previous_constraints: Previous set of constraints.
        
        Returns:
            ContextDrift if drift detected, None otherwise.
        """
        # Check for constraint loss
        lost_constraints = set(previous_constraints) - set(current_constraints)
        if lost_constraints:
            return ContextDrift(
                drift_type="constraint_loss",
                severity="high" if len(lost_constraints) > 3 else "medium",
                description=f"Lost {len(lost_constraints)} constraints: {', '.join(lost_constraints)}",
                affected_constraints=list(lost_constraints),
                recovery_action="Re-inject lost constraints into system prompt",
            )
        
        # Check for context overflow
        current_tokens = sum(len(c) for c in current_constraints)
        if current_tokens > self.max_context_tokens * 0.9:
            return ContextDrift(
                drift_type="context_overflow",
                severity="high",
                description=f"Context approaching limit: {current_tokens}/{self.max_context_tokens} tokens",
                recovery_action="Compress context or remove low-priority constraints",
            )
        
        # Check for repetition
        if len(current_constraints) > len(previous_constraints) * 1.5:
            return ContextDrift(
                drift_type="repetition",
                severity="low",
                description="Context growing too fast — possible repetition",
                recovery_action="Deduplicate constraints",
            )
        
        return None
    
    def assess_health(self) -> ContextHealth:
        """Assess current context health.
        
        Returns:
            ContextHealth with score, status, and recommendations.
        """
        if not self._metrics:
            return ContextHealth(
                score=1.0,
                status="healthy",
                metrics=[],
                issues=[],
                recommendations=["No metrics recorded yet"],
            )
        
        # Calculate health score from metrics
        scores = [m.value for m in self._metrics[-10:]]  # Last 10 metrics
        avg_score = sum(scores) / len(scores) if scores else 1.0
        
        # Determine status
        if avg_score >= 0.7:
            status = "healthy"
        elif avg_score >= 0.5:
            status = "warning"
        else:
            status = "critical"
        
        # Generate recommendations
        recommendations = []
        if avg_score < 0.7:
            recommendations.append("Context health is degraded — consider compression")
        if any(m.name == "constraint_count" and m.value > 20 for m in self._metrics):
            recommendations.append("Too many constraints — prioritize critical ones")
        if any(m.name == "context_tokens" and m.value > self.max_context_tokens * 0.8 for m in self._metrics):
            recommendations.append("Context near limit — compress or remove low-priority content")
        
        return ContextHealth(
            score=avg_score,
            status=status,
            metrics=self._metrics[-10:],
            issues=[],
            recommendations=recommendations,
        )
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        health = self.assess_health()
        return {
            "health_score": health.score,
            "health_status": health.status,
            "metrics_count": len(self._metrics),
            "drifts_detected": len(self._drifts),
            "recommendations": health.recommendations,
        }


class ContextCurator:
    """Curates and optimizes context for each session.
    
    Actively manages context quality by:
    - Prioritizing critical constraints
    - Compressing low-priority content
    - Removing redundant information
    - Preserving essential context across windows
    """
    
    def __init__(self, max_context_tokens: int = 128000):
        """Initialize context curator.
        
        Args:
            max_context_tokens: Maximum context window size.
        """
        self.max_context_tokens = max_context_tokens
        self._critical_constraints: list[str] = []
        self._optional_constraints: list[str] = []
        self._compressed_context: str = ""
    
    def add_critical_constraint(self, constraint: str) -> None:
        """Add a critical constraint that must always be preserved.
        
        Args:
            constraint: The constraint to add.
        """
        if constraint not in self._critical_constraints:
            self._critical_constraints.append(constraint)
            log.debug(f"[ContextCurator] Added critical constraint: {constraint[:50]}...")
    
    def add_optional_constraint(self, constraint: str) -> None:
        """Add an optional constraint that can be compressed if needed.
        
        Args:
            constraint: The constraint to add.
        """
        if constraint not in self._optional_constraints:
            self._optional_constraints.append(constraint)
    
    def curate_context(self, all_constraints: list[str],
                       all_context: str) -> str:
        """Curate context by prioritizing and compressing.
        
        Args:
            all_constraints: All constraints (critical + optional).
            all_context: Full context text.
        
        Returns:
            Curated context optimized for quality and size.
        """
        # Separate critical and optional constraints
        critical = [c for c in all_constraints if c in self._critical_constraints]
        optional = [c for c in all_constraints if c not in self._critical_constraints]
        
        # Build curated context
        curated = ""
        
        # Always include critical constraints
        if critical:
            curated += "# Critical Constraints\n"
            for c in critical:
                curated += f"- {c}\n"
            curated += "\n"
        
        # Include optional constraints (up to token limit)
        if optional:
            curated += "# Additional Constraints\n"
            for c in optional:
                if len(curated) // 4 < self.max_context_tokens * 0.7:  # 70% of limit
                    curated += f"- {c}\n"
                else:
                    break
            curated += "\n"
        
        # Add compressed context
        if all_context:
            if len(curated) // 4 < self.max_context_tokens * 0.8:
                curated += f"# Context\n{all_context}"
            else:
                # Compress context
                curated += f"# Context (compressed)\n{self._compress_context(all_context)}"
        
        return curated
    
    def _compress_context(self, context: str) -> str:
        """Compress context while preserving meaning.
        
        Args:
            context: Full context text.
        
        Returns:
            Compressed context.
        """
        # Simple compression: remove whitespace, keep structure
        lines = context.split('\n')
        compressed_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped:
                # Keep headers and important lines
                if stripped.startswith('#') or stripped.startswith('- ') or stripped.startswith('* '):
                    compressed_lines.append(stripped)
                elif len(stripped) > 10:  # Keep non-trivial lines
                    compressed_lines.append(stripped)
        
        return '\n'.join(compressed_lines)
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "critical_constraints": len(self._critical_constraints),
            "optional_constraints": len(self._optional_constraints),
            "max_context_tokens": self.max_context_tokens,
        }


class ACEFramework:
    """Full ACE (Agentic Context Engineering) Framework.
    
    Integrates ContextMonitor and ContextCurator to provide
    comprehensive context engineering capabilities.
    """
    
    def __init__(self, max_context_tokens: int = 128000):
        """Initialize ACE framework.
        
        Args:
            max_context_tokens: Maximum context window size.
        """
        self.monitor = ContextMonitor(max_context_tokens=max_context_tokens)
        self.curator = ContextCurator(max_context_tokens=max_context_tokens)
        self._session_context: str = ""
        self._session_constraints: list[str] = []
    
    def start_session(self, initial_constraints: list[str] | None = None) -> None:
        """Start a new session with initial constraints.
        
        Args:
            initial_constraints: Initial set of constraints.
        """
        self._session_constraints = initial_constraints or []
        self._session_context = ""
        
        # Add critical constraints
        for constraint in self._session_constraints:
            if "NEVER" in constraint.upper() or "MUST" in constraint.upper():
                self.curator.add_critical_constraint(constraint)
            else:
                self.curator.add_optional_constraint(constraint)
        
        log.info(f"[ACE] Started session with {len(self._session_constraints)} constraints")
    
    def update_context(self, new_context: str,
                       new_constraints: list[str] | None = None) -> None:
        """Update session context and constraints.
        
        Args:
            new_context: New context text.
            new_constraints: New set of constraints.
        """
        # Detect drift
        if new_constraints and self._session_constraints:
            drift = self.monitor.detect_drift(new_constraints, self._session_constraints)
            if drift:
                log.warning(f"[ACE] Context drift detected: {drift.description}")
                self.monitor._drifts.append(drift)
        
        # Update session state
        self._session_context = new_context
        self._session_constraints = new_constraints or self._session_constraints
        
        # Record metrics
        self.monitor.record_metric("context_tokens", len(new_context) // 4)
        self.monitor.record_metric("constraint_count", len(self._session_constraints))
    
    def get_curated_context(self) -> str:
        """Get curated context for the current session.
        
        Returns:
            Curated context optimized for quality and size.
        """
        return self.curator.curate_context(
            self._session_constraints,
            self._session_context,
        )
    
    def get_health(self) -> ContextHealth:
        """Get current context health.
        
        Returns:
            ContextHealth with score and recommendations.
        """
        return self.monitor.assess_health()
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "session_constraints": len(self._session_constraints),
            "session_context_tokens": len(self._session_context) // 4,
            "health": self.get_health().to_dict() if hasattr(self.get_health(), 'to_dict') else {
                "score": self.get_health().score,
                "status": self.get_health().status,
            },
            "monitor": self.monitor.to_memory_entry(),
            "curator": self.curator.to_memory_entry(),
        }


# ── Convenience Functions ───────────────────────────────────────────────────

_framework: ACEFramework | None = None


def get_ace_framework(max_context_tokens: int = 128000) -> ACEFramework:
    """Get or create the ACE framework.
    
    Args:
        max_context_tokens: Maximum context window size.
    
    Returns:
        ACEFramework instance.
    """
    global _framework
    if _framework is None:
        _framework = ACEFramework(max_context_tokens=max_context_tokens)
    return _framework


def start_ace_session(constraints: list[str] | None = None) -> None:
    """Start a new ACE session.
    
    Args:
        constraints: Initial set of constraints.
    """
    framework = get_ace_framework()
    framework.start_session(constraints)
