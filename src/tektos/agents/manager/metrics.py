"""Prime Mover Metrics — the 8 critical variables the Manager tracks.

The Manager does NOT track everything. It tracks only the prime mover
variables — the critical health metrics and failure states that indicate
system health.

Ashby's Law of Requisite Variety: A system must have enough internal
variety to match the variety of its environment. If the environment is
more complex than the system, the system will fail.

The 8 Prime Mover Variables:
1. Error Rate — percentage of operations that fail
2. Token Efficiency — tokens used per successful task
3. Tool Success Ratio — successful tool calls / total tool calls
4. Context Compression Ratio — original tokens / compressed tokens
5. Skill Creation Rate — new skills created per cycle
6. Archetype Frequency — most common repeated patterns
7. Spiral Radius — distance from center (S5 identity)
8. Latency — time from prompt to response

The animal that got eaten teaches more than the ones that got away.
Failure data > success data. Track what goes wrong, not what goes right.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class MetricSample(BaseModel):
    """A single metric sample."""

    id: str = Field(default_factory=lambda: f"metric-{uuid.uuid4().hex[:8]}")
    name: str
    value: float
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    who: str = Field(default="S3 Manager", description="W5H1M: Who collected this")
    what: str = Field(default="", description="W5H1M: What was measured")
    where: str = Field(default="backend metrics store", description="W5H1M: Where collected")
    when: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="W5H1M: When collected")
    why: str = Field(default="prime mover variable tracking", description="W5H1M: Why tracking this")
    how: str = Field(default="automatic collection", description="W5H1M: How collected")
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricThreshold(BaseModel):
    """A threshold for a metric that triggers alerts."""

    name: str
    warning: float = Field(..., description="Warning threshold")
    critical: float = Field(..., description="Critical threshold")
    direction: str = Field(default="lower_is_better", description="lower_is_better or higher_is_better")
    who: str = Field(default="S3 Manager", description="W5H1M: Who set this threshold")
    what: str = Field(default="", description="W5H1M: What threshold")
    where: str = Field(default="manager config", description="W5H1M: Where configured")
    when: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="W5H1M: When set")
    why: str = Field(default="system health monitoring", description="W5H1M: Why this threshold")
    how: str = Field(default="config-driven", description="W5H1M: How threshold works")


class PrimeMoverMetrics:
    """Collects and tracks the 8 prime mover variables.

    Tracks only what matters. No noise. No success logging.
    Focus on failure states and critical health variables.

    Attributes:
        samples: All metric samples collected.
        thresholds: Configured thresholds for each metric.
        spiral_radius: Current distance from center (S5 identity).
    """

    # The 8 prime mover variables
    METRICS = [
        "error_rate",
        "token_efficiency",
        "tool_success_ratio",
        "context_compression_ratio",
        "skill_creation_rate",
        "archetype_frequency",
        "spiral_radius",
        "latency",
    ]

    def __init__(self) -> None:
        self.samples: list[MetricSample] = []
        self.thresholds: dict[str, MetricThreshold] = {
            "error_rate": MetricThreshold(
                name="error_rate",
                warning=0.05,
                critical=0.10,
                direction="lower_is_better",
                what="error_rate threshold",
                where="manager config",
                why="system health monitoring",
                how="config-driven",
            ),
            "token_efficiency": MetricThreshold(
                name="token_efficiency",
                warning=1.5,
                critical=2.0,
                direction="higher_is_better",
                what="token_efficiency threshold",
                where="manager config",
                why="system health monitoring",
                how="config-driven",
            ),
            "tool_success_ratio": MetricThreshold(
                name="tool_success_ratio",
                warning=0.80,
                critical=0.60,
                direction="higher_is_better",
                what="tool_success_ratio threshold",
                where="manager config",
                why="system health monitoring",
                how="config-driven",
            ),
            "context_compression_ratio": MetricThreshold(
                name="context_compression_ratio",
                warning=1.5,
                critical=2.0,
                direction="higher_is_better",
                what="context_compression_ratio threshold",
                where="manager config",
                why="system health monitoring",
                how="config-driven",
            ),
            "skill_creation_rate": MetricThreshold(
                name="skill_creation_rate",
                warning=0.5,
                critical=0.1,
                direction="higher_is_better",
                what="skill_creation_rate threshold",
                where="manager config",
                why="system health monitoring",
                how="config-driven",
            ),
            "archetype_frequency": MetricThreshold(
                name="archetype_frequency",
                warning=5,
                critical=10,
                direction="lower_is_better",
                what="archetype_frequency threshold",
                where="manager config",
                why="system health monitoring",
                how="config-driven",
            ),
            "spiral_radius": MetricThreshold(
                name="spiral_radius",
                warning=0.5,
                critical=0.8,
                direction="lower_is_better",
                what="spiral_radius threshold",
                where="manager config",
                why="system health monitoring",
                how="config-driven",
            ),
            "latency": MetricThreshold(
                name="latency",
                warning=10.0,
                critical=30.0,
                direction="lower_is_better",
                what="latency threshold",
                where="manager config",
                why="system health monitoring",
                how="config-driven",
            ),
        }
        self.spiral_radius: float = 1.0

    def record(self, name: str, value: float, **kwargs: Any) -> MetricSample:
        """Record a metric sample.

        Args:
            name: The metric name (one of the 8 prime mover variables).
            value: The metric value.
            **kwargs: Additional metadata.

        Returns:
            The recorded MetricSample.
        """
        sample = MetricSample(
            name=name,
            value=value,
            **kwargs,
        )
        self.samples.append(sample)
        return sample

    def get_latest(self, name: str) -> MetricSample | None:
        """Get the most recent sample for a metric."""
        for sample in reversed(self.samples):
            if sample.name == name:
                return sample
        return None

    def get_average(self, name: str, last_n: int = 10) -> float | None:
        """Get the average value for a metric over the last N samples."""
        values = [
            s.value
            for s in reversed(self.samples)
            if s.name == name
        ][:last_n]
        return sum(values) / len(values) if values else None

    def check_threshold(self, name: str) -> str | None:
        """Check if a metric has crossed a threshold.

        Returns:
            'warning' if warning threshold crossed,
            'critical' if critical threshold crossed,
            None if within limits.
        """
        threshold = self.thresholds.get(name)
        if not threshold:
            return None

        latest = self.get_latest(name)
        if not latest:
            return None

        value = latest.value

        if threshold.direction == "lower_is_better":
            # For "lower is better" (error_rate, latency, etc.):
            # Higher values are BAD → critical if >= critical, warning if >= warning
            if value >= threshold.critical:
                return "critical"
            if value >= threshold.warning:
                return "warning"
        else:  # higher_is_better
            # For "higher is better" (token_efficiency, tool_success_ratio, etc.):
            # Lower values are BAD → critical if <= critical, warning if <= warning
            if value <= threshold.critical:
                return "critical"
            if value <= threshold.warning:
                return "warning"

        return None

    def update_spiral_radius(self, new_radius: float) -> None:
        """Update the spiral radius (distance from center/S5 identity).

        If the radius is increasing, the system is spiraling out
        (expansion without convergence) — this is a warning sign.

        Args:
            new_radius: The new spiral radius (0 = perfect center, 1 = outer ring).
        """
        self.spiral_radius = new_radius

    def get_health_report(self) -> dict[str, Any]:
        """Generate a health report of all prime mover variables."""
        report: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "spiral_radius": self.spiral_radius,
            "metrics": {},
        }

        for metric_name in self.METRICS:
            latest = self.get_latest(metric_name)
            avg = self.get_average(metric_name)
            threshold_status = self.check_threshold(metric_name)

            report["metrics"][metric_name] = {
                "latest": latest.value if latest else None,
                "average": avg,
                "threshold_status": threshold_status,
            }

        return report
