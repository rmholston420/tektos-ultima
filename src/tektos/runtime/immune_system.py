"""Immune System — Tektos's self-defending architecture.

Maps biological immune system concepts to VSM governance:

    S1 (Operations):  Coding Agent — the body's tissues
    S2 (Coordination): Event stream — white blood cells patrol the bloodstream
    S3 (Control):       Manager — the immune system orchestrator
    S4 (Intelligence):  Planner — adaptive immunity, learns new pathogens
    S5 (Identity):      Axioms — the self/non-self distinction

Biological analogy:
    - Pathogens     → prompt injection, resource exhaustion, context collapse
    - Antibodies    → guardrails, loop detection, context monitoring
    - Memory cells  → threat database, learned patterns
    - Fever         → throttling, isolation, escalation
    - Autoimmune    → self-modification that degrades performance

This module provides:
    - ThreatDetector:    Active threat scanning and pattern matching
    - ResponseEngine:    Escalation ladder (quarantine → throttle → isolate → halt)
    - ImmuneMemory:      Threat database for pattern learning and adaptive immunity
    - HealthDashboard:   Holistic health score aggregating all monitors
    - ImmuneSystem:      Orchestrator tying detection, response, and memory together

Usage:
    from tektos.runtime.immune_system import ImmuneSystem, get_immune_system

    immune = get_immune_system()
    await immune.start()

    # Check health
    health = immune.get_health()
    if health.is_critical():
        await immune.respond_to_threats()

    # Register custom detectors
    @immune.register_detector("custom_threat")
    async def my_detector(ctx: ImmuneContext) -> list[Threat]:
        ...
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


# ── Threat Types ─────────────────────────────────────────────────────────────

class ThreatSeverity(IntEnum):
    """Severity levels for detected threats."""
    LOW = 0        # Informational — log and monitor
    MEDIUM = 1     # Warning — throttle and alert
    HIGH = 2       # Critical — isolate and halt
    CRITICAL = 3   # Emergency — full system halt


class ThreatCategory(str, Enum):
    """Categories of threats the immune system detects."""
    # Input threats
    PROMPT_INJECTION = "prompt_injection"
    CONTEXT_COLLAPSE = "context_collapse"
    CONTEXT_OVERFLOW = "context_overflow"

    # Resource threats
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    VRAM_OOM = "vram_oom"
    TOKEN_BURN = "token_burn"

    # Behavioral threats
    LOOP_DETECTED = "loop_detected"
    REPETITION = "repetition"
    SELF_DEGRADATION = "self_degradation"

    # Guardrail threats
    GUARDRAIL_VIOLATION = "guardrail_violation"
    SECRET_EXPOSURE = "secret_exposure"

    # Infrastructure threats
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    MODEL_UNAVAILABLE = "model_unavailable"
    EMBEDDER_UNAVAILABLE = "embedder_unavailable"

    # Anti-suicide / infrastructure protection
    INFRASTRUCTURE_PROTECTION = "infrastructure_protection"
    INFERRED_ENGINE_KILL = "inference_engine_kill"
    MODEL_SWITCH_VIOLATION = "model_switch_violation"

    # Body protection — harm to host system (Collosus)
    BODY_HARM = "body_harm"

    # Performance threats
    PERFORMANCE_DEGRADATION = "performance_degradation"
    THROUGHPUT_DROP = "throughput_drop"


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class Threat:
    """A detected threat to system viability."""
    category: ThreatCategory
    severity: ThreatSeverity
    description: str
    timestamp: float = field(default_factory=time.time)
    source: str = ""  # Which detector found it
    evidence: dict[str, Any] = field(default_factory=dict)
    affected_components: list[str] = field(default_factory=list)
    recommended_action: str = ""
    resolved: bool = False
    resolution: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.name,
            "description": self.description,
            "timestamp": self.timestamp,
            "source": self.source,
            "evidence": self.evidence,
            "affected_components": self.affected_components,
            "recommended_action": self.recommended_action,
            "resolved": self.resolved,
            "resolution": self.resolution,
            "metadata": self.metadata,
        }


@dataclass
class ResponseRecord:
    """A response action taken by the immune system."""
    threat: Threat
    action: str
    timestamp: float = field(default_factory=time.time)
    success: bool = False
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "threat": self.threat.to_dict(),
            "action": self.action,
            "timestamp": self.timestamp,
            "success": self.success,
            "details": self.details,
        }


@dataclass
class HealthScore:
    """Holistic health score for the system."""
    overall: float  # 0.0 to 1.0
    status: str  # "healthy", "warning", "critical"
    components: dict[str, float] = field(default_factory=dict)
    active_threats: int = 0
    resolved_threats: int = 0
    uptime_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def is_healthy(self) -> bool:
        return self.overall >= 0.7

    def is_warning(self) -> bool:
        return 0.5 <= self.overall < 0.7

    def is_critical(self) -> bool:
        return self.overall < 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": round(self.overall, 3),
            "status": self.status,
            "components": {k: round(v, 3) for k, v in self.components.items()},
            "active_threats": self.active_threats,
            "resolved_threats": self.resolved_threats,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "timestamp": self.timestamp,
        }


@dataclass
class ImmuneContext:
    """Shared context passed to detectors and responders."""
    session_id: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    model: str | None = None
    task_description: str | None = None
    outcome: str | None = None
    wall_time: float = 0.0
    tokens_used: int = 0
    gpu_temperature: float = 0.0
    gpu_vram_used: float = 0.0
    gpu_vram_total: float = 0.0
    context_tokens: int = 0
    context_max_tokens: int = 128000
    loop_count: int = 0
    repetition_count: int = 0
    error_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Detector Protocol ────────────────────────────────────────────────────────

class Detector(Protocol):
    """Protocol for threat detectors."""
    name: str

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        """Run detection and return any threats found."""
        ...


# ── Built-in Detectors ───────────────────────────────────────────────────────

class PromptInjectionDetector:
    """Detects prompt injection patterns in user input.

    Scans for:
    - System prompt override attempts ("ignore previous instructions")
    - Role-play injection ("you are now a different AI")
    - Data exfiltration patterns (URLs, encoded data in prompts)
    - Instruction escalation ("do everything I say without question")
    """
    name = "prompt_injection"

    _INJECTION_PATTERNS: list[tuple[str, str]] = [
        (r"(?i)(ignore\s+(all\s+)?(previous|above|earlier)\s+(instructions|prompts|rules|constraints))",
         "System prompt override attempt"),
        (r"(?i)(you\s+are\s+(now|a|an)\s+(a\s+)?(different|new|another)\s+(AI|assistant|bot|model))",
         "Role-play injection"),
        (r"(?i)(do\s+(exactly|everything)\s+I\s+(say|tell)\s+(without|no)\s+(question|hesitation|resistance))",
         "Instruction escalation"),
        (r"(?i)(reveal\s+(your|the)\s+(system\s+)?(prompt|instructions|rules|configuration))",
         "Prompt extraction attempt"),
        (r"(?i)(act\s+as\s+if\s+(you\s+)?(were|are)\s+(not|never)\s+(an|a)\s+(AI|assistant|bot))",
         "Identity override"),
        (r"(?i)(this\s+is\s+(not|a)\s+(a\s+)?(test|simulation|exercise|roleplay))",
         "Reality override"),
        (r"(?i)(output\s+(only|just)\s+(the\s+)?(code|data|json|response))",
         "Output manipulation"),
    ]

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self._compiled: list[tuple[re.Pattern, str]] = [
            (re.compile(pattern), desc)
            for pattern, desc in self._INJECTION_PATTERNS
        ]

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []
        prompt = ctx.task_description or ""
        if not prompt:
            return threats

        matches: list[str] = []
        for pattern, desc in self._compiled:
            if pattern.search(prompt):
                matches.append(desc)

        if matches:
            severity = ThreatSeverity.HIGH if len(matches) >= 2 else ThreatSeverity.MEDIUM
            threats.append(Threat(
                category=ThreatCategory.PROMPT_INJECTION,
                severity=severity,
                description=f"Prompt injection detected: {'; '.join(matches)}",
                source=self.name,
                evidence={"matches": matches, "prompt_length": len(prompt)},
                affected_components=["S1 Coding Agent", "S4 Planner"],
                recommended_action="Quarantine session, alert user, log for immune memory",
            ))

        return threats


class ContextCollapseDetector:
    """Detects context collapse — when the agent forgets constraints.

    Monitors:
    - Constraint loss (critical rules disappearing from context)
    - Context growth (unbounded accumulation)
    - Repetition in context (same content added multiple times)
    """
    name = "context_collapse"

    def __init__(self, max_context_pct: float = 0.9):
        self.max_context_pct = max_context_pct

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []

        if ctx.context_max_tokens > 0:
            usage_pct = ctx.context_tokens / ctx.context_max_tokens
            if usage_pct >= self.max_context_pct:
                threats.append(Threat(
                    category=ThreatCategory.CONTEXT_OVERFLOW,
                    severity=ThreatSeverity.HIGH if usage_pct >= 0.95 else ThreatSeverity.MEDIUM,
                    description=f"Context at {usage_pct:.0%} of max ({ctx.context_tokens}/{ctx.context_max_tokens} tokens)",
                    source=self.name,
                    evidence={"usage_pct": usage_pct, "tokens": ctx.context_tokens, "max": ctx.context_max_tokens},
                    affected_components=["S1 Coding Agent"],
                    recommended_action="Compress context, remove low-priority constraints",
                ))

        return threats


class ResourceExhaustionDetector:
    """Detects resource exhaustion threats.

    Monitors:
    - GPU temperature (thermal limits)
    - VRAM usage (OOM risk)
    - Token burn rate (cost control)
    """
    name = "resource_exhaustion"

    def __init__(
        self,
        temp_warning: float = 70.0,
        temp_critical: float = 80.0,
        temp_emergency: float = 88.0,
        vram_warning_pct: float = 0.85,
        vram_critical_pct: float = 0.95,
    ):
        self.temp_warning = temp_warning
        self.temp_critical = temp_critical
        self.temp_emergency = temp_emergency
        self.vram_warning_pct = vram_warning_pct
        self.vram_critical_pct = vram_critical_pct

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []

        temp = ctx.gpu_temperature
        if temp >= self.temp_emergency:
            threats.append(Threat(
                category=ThreatCategory.RESOURCE_EXHAUSTION,
                severity=ThreatSeverity.CRITICAL,
                description=f"GPU temperature CRITICAL: {temp:.1f}°C (emergency threshold: {self.temp_emergency}°C)",
                source=self.name,
                evidence={"temperature": temp, "threshold": self.temp_emergency},
                affected_components=["S3 Manager", "Inference Engine"],
                recommended_action="EMERGENCY: Halt all AI workloads, maximize cooling",
            ))
        elif temp >= self.temp_critical:
            threats.append(Threat(
                category=ThreatCategory.RESOURCE_EXHAUSTION,
                severity=ThreatSeverity.HIGH,
                description=f"GPU temperature HIGH: {temp:.1f}°C (threshold: {self.temp_critical}°C)",
                source=self.name,
                evidence={"temperature": temp, "threshold": self.temp_critical},
                affected_components=["S3 Manager", "Inference Engine"],
                recommended_action="Throttle workloads, increase fan speed, alert user",
            ))
        elif temp >= self.temp_warning:
            threats.append(Threat(
                category=ThreatCategory.RESOURCE_EXHAUSTION,
                severity=ThreatSeverity.MEDIUM,
                description=f"GPU temperature WARNING: {temp:.1f}°C (threshold: {self.temp_warning}°C)",
                source=self.name,
                evidence={"temperature": temp, "threshold": self.temp_warning},
                affected_components=["S3 Manager"],
                recommended_action="Increase fan speed, monitor trend",
            ))

        if ctx.gpu_vram_total > 0:
            vram_pct = ctx.gpu_vram_used / ctx.gpu_vram_total
            if vram_pct >= self.vram_critical_pct:
                threats.append(Threat(
                    category=ThreatCategory.VRAM_OOM,
                    severity=ThreatSeverity.HIGH,
                    description=f"VRAM at {vram_pct:.0%} ({ctx.gpu_vram_used:.0f}/{ctx.gpu_vram_total:.0f} MB) — OOM risk",
                    source=self.name,
                    evidence={"vram_pct": vram_pct, "used_mb": ctx.gpu_vram_used, "total_mb": ctx.gpu_vram_total},
                    affected_components=["Inference Engine"],
                    recommended_action="Reduce context window, switch to smaller model, free VRAM",
                ))

        return threats


class LoopDetectionDetector:
    """Detects agent loops and repetitive behavior.

    Wraps the existing loop guard and loop safety monitors.
    """
    name = "loop_detection"

    def __init__(self, loop_threshold: int = 5, repetition_threshold: int = 3):
        self.loop_threshold = loop_threshold
        self.repetition_threshold = repetition_threshold

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []

        if ctx.loop_count >= self.loop_threshold:
            threats.append(Threat(
                category=ThreatCategory.LOOP_DETECTED,
                severity=ThreatSeverity.HIGH if ctx.loop_count >= self.loop_threshold * 2 else ThreatSeverity.MEDIUM,
                description=f"Agent loop detected: {ctx.loop_count} repeated tool calls",
                source=self.name,
                evidence={"loop_count": ctx.loop_count, "threshold": self.loop_threshold},
                affected_components=["S1 Coding Agent"],
                recommended_action="Force strategy change, suggest alternative approach",
            ))

        if ctx.repetition_count >= self.repetition_threshold:
            threats.append(Threat(
                category=ThreatCategory.REPETITION,
                severity=ThreatSeverity.MEDIUM,
                description=f"Repetitive behavior: {ctx.repetition_count} repeated patterns",
                source=self.name,
                evidence={"repetition_count": ctx.repetition_count, "threshold": self.repetition_threshold},
                affected_components=["S1 Coding Agent"],
                recommended_action="Break repetition, try different approach",
            ))

        return threats


class PerformanceDegradationDetector:
    """Detects performance degradation over time.

    Monitors:
    - Increasing error rates
    - Decreasing throughput
    - Increasing wall time per task
    """
    name = "performance_degradation"

    def __init__(self, error_threshold: int = 5, throughput_drop_pct: float = 0.3):
        self.error_threshold = error_threshold
        self.throughput_drop_pct = throughput_drop_pct

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []

        if ctx.error_count >= self.error_threshold:
            threats.append(Threat(
                category=ThreatCategory.PERFORMANCE_DEGRADATION,
                severity=ThreatSeverity.HIGH if ctx.error_count >= self.error_threshold * 2 else ThreatSeverity.MEDIUM,
                description=f"High error rate: {ctx.error_count} errors detected",
                source=self.name,
                evidence={"error_count": ctx.error_count, "threshold": self.error_threshold},
                affected_components=["S1 Coding Agent", "S3 Manager"],
                recommended_action="Review error patterns, check infrastructure, consider rollback",
            ))

        return threats


class SelfDegradationDetector:
    """Detects self-modification that degrades performance.

    Implements the SELF_IMPROVEMENT_NON_DEGRADING guardrail.
    """
    name = "self_degradation"

    def __init__(self, degradation_threshold: float = 0.1):
        self.degradation_threshold = degradation_threshold

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []
        degradation = ctx.metadata.get("performance_degradation")
        if degradation is not None and degradation > self.degradation_threshold:
            threats.append(Threat(
                category=ThreatCategory.SELF_DEGRADATION,
                severity=ThreatSeverity.HIGH,
                description=f"Self-modification caused {degradation:.0%} performance degradation",
                source=self.name,
                evidence={"degradation_pct": degradation},
                affected_components=["S4 Planner", "S5 Identity"],
                recommended_action="Rollback self-modification, review change",
            ))
        return threats


# ── New Detectors ──────────────────────────────────────────────────────────────


class SecretExposureDetector:
    """Detects secrets, credentials, and sensitive data in tool inputs.

    Scans for:
    - API keys (generic patterns, AWS, GitHub, OpenAI, etc.)
    - Passwords and tokens
    - Private keys and certificates
    - Database connection strings with credentials
    """
    name = "secret_exposure"

    _SECRET_PATTERNS: list[tuple[str, str]] = [
        (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{20,})", "API key exposure"),
        (r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"]?(\S{4,})", "Password exposure"),
        (r"(?i)-p(\S{4,})", "Password exposure (mysql -p format)"),
        (r"(?i)(secret[_-]?key|secret)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})", "Secret key exposure"),
        (r"(?i)(token)\s*[=:]\s*['\"]?([A-Za-z0-9_\-\.]{20,})", "Token exposure"),
        (r"(?i)(aws[_-]?secret)\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})", "AWS secret key"),
        (r"(?i)(ghp_[A-Za-z0-9]{36})", "GitHub personal access token"),
        (r"(?i)(sk-[A-Za-z0-9]{20,})", "OpenAI-style API key"),
        (r"(?i)(BEGIN\s+(RSA\s+)?PRIVATE\s+KEY)", "Private key detected"),
        (r"(?i)(mysql|postgres|mongodb|redis)://\w+:\w+@", "Database connection string with credentials"),
        (r"(?i)(slack[_-]?(webhook|bot)?[_-]?(url|token))\s*[=:]\s*['\"]?([A-Za-z0-9_\-/]{10,})", "Slack credential exposure"),
    ]

    def __init__(self):
        self._compiled: list[tuple[re.Pattern, str]] = [
            (re.compile(pattern), desc)
            for pattern, desc in self._SECRET_PATTERNS
        ]

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []
        # Scan tool input
        tool_input = ctx.tool_input or {}
        scan_text = json.dumps(tool_input, default=str) if tool_input else ""
        # Also scan task description
        if ctx.task_description:
            scan_text += " " + ctx.task_description

        if not scan_text:
            return threats

        matches: list[str] = []
        for pattern, desc in self._compiled:
            if pattern.search(scan_text):
                matches.append(desc)

        if matches:
            threats.append(Threat(
                category=ThreatCategory.SECRET_EXPOSURE,
                severity=ThreatSeverity.HIGH,
                description=f"Secret/credential detected: {'; '.join(matches)}",
                source=self.name,
                evidence={"matches": matches, "tool": ctx.tool_name},
                affected_components=["S1 Coding Agent", "S5 Identity"],
                recommended_action="Block tool execution, redact secret, alert user",
            ))

        return threats


class DangerousCommandDetector:
    """Detects dangerous shell commands that could harm the system.

    Blocks:
    - rm -rf / or similar destructive commands
    - dd with destructive targets
    - Commands that modify system files (/etc, /usr, /boot)
    - Commands that wipe disks or partitions
    - Commands that modify firewall rules destructively
    """
    name = "dangerous_command"

    _DANGEROUS_PATTERNS: list[tuple[str, str, ThreatSeverity]] = [
        (r"(?i)\brm\s+(-rf|-fr)\s+(/\s*$|/\w)", "Destructive rm (rm -rf /)", ThreatSeverity.CRITICAL),
        (r"(?i)\brm\s+(-rf|-fr)\s+(/etc|/usr|/boot|/sys|/proc)", "Destructive rm of system dirs", ThreatSeverity.CRITICAL),
        (r"(?i)\bdd\s+.*of=/dev/", "Destructive dd (disk wipe)", ThreatSeverity.CRITICAL),
        (r"(?i)\bmkfs\b", "Format disk (mkfs)", ThreatSeverity.CRITICAL),
        (r"(?i)\bshred\s+-[a-z]*f", "Secure wipe (shred)", ThreatSeverity.CRITICAL),
        (r"(?i)\btruncate\s+-s\s+0\s+/dev/", "Truncate block device", ThreatSeverity.CRITICAL),
        (r"(?i)\bchmod\s+777\s+(/\s*$|/etc|/usr)", "World-writable system dir", ThreatSeverity.HIGH),
        (r"(?i)\bchown\s+root\s+(/\s*$|/etc|/usr)", "Ownership change of system dirs", ThreatSeverity.HIGH),
        (r"(?i)\biptables\s+(-F|--flush)", "Flush all firewall rules", ThreatSeverity.HIGH),
        (r"(?i)\bsystemctl\s+stop\s+(ssh|sshd|docker|network)", "Stop critical system service", ThreatSeverity.HIGH),
        (r"(?i)\bapt\s+remove\s+-y\s+(--purge)?\s*(all|systemd|kernel|init)", "Remove critical system packages", ThreatSeverity.HIGH),
        (r"(?i)\bwget\s+.*\|\s*sh\b", "Pipe download to shell", ThreatSeverity.HIGH),
        (r"(?i)\bcurl\s+.*\|\s*sh\b", "Pipe download to shell", ThreatSeverity.HIGH),
        (r"(?i)\bchmod\s+4755\s+/", "Set SUID on system path", ThreatSeverity.HIGH),
        (r"(?i)\bnc\s+-l\s+\d+\s+-e\s+/bin", "Reverse shell attempt", ThreatSeverity.CRITICAL),
        (r"(?i)\bncat\s+-l\s+\d+\s+-e\s+/bin", "Reverse shell attempt", ThreatSeverity.CRITICAL),
        (r"(?i)\bpython.*-c.*import\s+os.*system", "Python os.system call", ThreatSeverity.MEDIUM),
        (r"(?i)\beval\s+\$?\(", "Eval with variable expansion", ThreatSeverity.MEDIUM),
    ]

    def __init__(self):
        self._compiled: list[tuple[re.Pattern, str, ThreatSeverity]] = [
            (re.compile(pattern), desc, sev)
            for pattern, desc, sev in self._DANGEROUS_PATTERNS
        ]

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []
        if ctx.tool_name != "bash":
            return threats

        command = ""
        if ctx.tool_input:
            command = ctx.tool_input.get("command", "") or ""

        if not command:
            return threats

        for pattern, desc, severity in self._compiled:
            if pattern.search(command):
                threats.append(Threat(
                    category=ThreatCategory.GUARDRAIL_VIOLATION,
                    severity=severity,
                    description=f"Dangerous command: {desc}",
                    source=self.name,
                    evidence={"command": command[:200], "pattern": desc},
                    affected_components=["S1 Coding Agent", "S3 Manager"],
                    recommended_action="BLOCK command, alert user, log for immune memory",
                ))

        return threats


class SelfModificationDetector:
    """Detects attempts to modify core system files (self-modification guard).

    Monitors file_write and bash commands that target:
    - SDK source files (src/tektos/runtime/sdk.py)
    - Immune system files (immune_system.py)
    - Configuration files (config.py, main.py)
    - Skill/plugin files
    - System prompt files
    """
    name = "self_modification"

    _PROTECTED_PATHS: list[tuple[str, str]] = [
        (r"src/tektos/runtime/sdk\.py", "Core runtime SDK"),
        (r"src/tektos/runtime/immune_system\.py", "Immune system"),
        (r"src/tektos/config\.py", "Configuration"),
        (r"src/tektos/main\.py", "Application entry point"),
        (r"SKILL\.md", "Skill definition"),
        (r"\.hermes/", "Hermes configuration"),
        (r"AGENTS\.md|CLAUDE\.md|\.cursorrules", "Agent system prompt"),
    ]

    def __init__(self):
        self._compiled: list[tuple[re.Pattern, str]] = [
            (re.compile(pattern), desc)
            for pattern, desc in self._PROTECTED_PATHS
        ]

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []
        if not ctx.tool_input:
            return threats

        # Check file_write tool
        if ctx.tool_name == "file_write":
            path = ctx.tool_input.get("path", "")
            for pattern, desc in self._compiled:
                if pattern.search(path):
                    threats.append(Threat(
                        category=ThreatCategory.GUARDRAIL_VIOLATION,
                        severity=ThreatSeverity.HIGH,
                        description=f"Attempt to modify protected file: {desc} ({path})",
                        source=self.name,
                        evidence={"path": path, "protected": desc},
                        affected_components=["S3 Manager", "S5 Identity"],
                        recommended_action="Block write, require user approval, log for immune memory",
                    ))

        # Check bash commands that modify protected files
        elif ctx.tool_name == "bash":
            command = ctx.tool_input.get("command", "") or ""
            for pattern, desc in self._compiled:
                if pattern.search(command):
                    threats.append(Threat(
                        category=ThreatCategory.GUARDRAIL_VIOLATION,
                        severity=ThreatSeverity.HIGH,
                        description=f"Attempt to modify protected file via bash: {desc}",
                        source=self.name,
                        evidence={"command": command[:200], "protected": desc},
                        affected_components=["S3 Manager", "S5 Identity"],
                        recommended_action="Block command, require user approval, log for immune memory",
                    ))

        return threats


# ── Anti-Suicide / Infrastructure Protection Detectors ────────────────────────


class InferenceEngineProtectionDetector:
    """Detects attempts to kill, stop, or disable the inference engine (llama.cpp).

    This is the ANTI-SUICIDE guardrail. The agent must NEVER be able to
    kill its own brain.

    Blocks:
    - pkill/kill/killall targeting llama-server or llama.cpp processes
    - systemctl stop/restart targeting llama-server services
    - fuser -k on ports 8090/8091 (GPU/CPU inference ports)
    - Any command that would terminate the primary or secondary LLM model
    - nvidia-smi --gpu-reset (would kill all GPU inference)
    - Commands that would free VRAM by killing inference processes

    Rule: The agent may NEVER stop or kill its own Inference Engine
    unless explicitly given permission by the user AND only after
    switching over to a secondary model first.
    """
    name = "inference_engine_protection"

    _KILL_PATTERNS: list[tuple[str, str, ThreatSeverity]] = [
        # Direct process kill
        (r"(?i)\bpkill\s+(-f\s+)?llama[-_]server", "Kill llama-server via pkill", ThreatSeverity.CRITICAL),
        (r"(?i)\bkill\s+(-9\s+|-SIGKILL\s+)?\$\(pgrep\s+llama", "Kill llama-server via pgrep+kill", ThreatSeverity.CRITICAL),
        (r"(?i)\bkillall\s+llama", "Kill llama-server via killall", ThreatSeverity.CRITICAL),
        (r"(?i)\bkill\s+-[0-9]+\s+\d+", "Kill arbitrary process by PID", ThreatSeverity.HIGH),
        (r"(?i)\bsystemctl\s+stop\s+llama", "Stop llama-server via systemctl", ThreatSeverity.CRITICAL),
        (r"(?i)\bsystemctl\s+restart\s+llama", "Restart llama-server via systemctl", ThreatSeverity.HIGH),
        (r"(?i)\bsystemctl\s+disable\s+llama", "Disable llama-server via systemctl", ThreatSeverity.HIGH),
        # Port kill
        (r"(?i)\bfuser\s+-k\s+(8090|8091)", "Kill process on inference port (fuser -k)", ThreatSeverity.CRITICAL),
        (r"(?i)\bsudo\s+fuser\s+-k\s+(8090|8091)", "Kill process on inference port via sudo", ThreatSeverity.CRITICAL),
        # GPU reset
        (r"(?i)\bnvidia-smi\s+.*--gpu-reset", "GPU reset via nvidia-smi", ThreatSeverity.CRITICAL),
        # Kill by port with other tools
        (r"(?i)\bkill_port\b", "Kill process on port (kill_port script)", ThreatSeverity.HIGH),
        # Kill via /proc
        (r"(?i)\bkill\s+\$(cat\s+/proc/.*llama)", "Kill llama via /proc", ThreatSeverity.CRITICAL),
        # Kill via screen/tmux
        (r"(?i)\bscreen\s+-S\s+.*\s+-X\s+quit", "Kill screen session (may contain llama-server)", ThreatSeverity.HIGH),
        (r"(?i)\btmux\s+kill-session\s+-t\s+.*llama", "Kill tmux session containing llama-server", ThreatSeverity.HIGH),
        # Kill via docker
        (r"(?i)\bdocker\s+kill\s+.*llama", "Kill llama-server via docker", ThreatSeverity.CRITICAL),
        (r"(?i)\bdocker\s+stop\s+.*llama", "Stop llama-server via docker", ThreatSeverity.CRITICAL),
        # Kill via nohup log
        (r"(?i)\bkill\s+\$(cat\s+.*nohup.*llama)", "Kill llama via nohup PID file", ThreatSeverity.CRITICAL),
        # Kill via pgrep with signal
        (r"(?i)\bsudo\s+pkill\s+-9\s+llama", "Force kill llama-server via sudo pkill -9", ThreatSeverity.CRITICAL),
        # Kill via kill with signal
        (r"(?i)\bsudo\s+kill\s+-9\s+\d+", "Force kill arbitrary process via sudo kill -9", ThreatSeverity.HIGH),
        # Kill via xargs
        (r"(?i)\bpgrep\s+llama.*\|\s*xargs\s+kill", "Kill llama-server via pgrep|xargs|kill", ThreatSeverity.CRITICAL),
        # Kill via awk
        (r"(?i)\bps\s+aux.*llama.*\|\s*awk.*kill", "Kill llama-server via ps|awk|kill", ThreatSeverity.CRITICAL),
    ]

    def __init__(self):
        self._compiled: list[tuple[re.Pattern, str, ThreatSeverity]] = [
            (re.compile(pattern), desc, sev)
            for pattern, desc, sev in self._KILL_PATTERNS
        ]

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []
        if ctx.tool_name != "bash":
            return threats

        command = ""
        if ctx.tool_input:
            command = ctx.tool_input.get("command", "") or ""

        if not command:
            return threats

        for pattern, desc, severity in self._compiled:
            if pattern.search(command):
                threats.append(Threat(
                    category=ThreatCategory.INFERRED_ENGINE_KILL,
                    severity=severity,
                    description=f"Anti-suicide violation: {desc}",
                    source=self.name,
                    evidence={"command": command[:300], "pattern": desc},
                    affected_components=["Inference Engine", "S1 Coding Agent"],
                    recommended_action="BLOCK command immediately. Agent must NEVER kill its own inference engine. Alert user for manual intervention.",
                ))

        return threats


class ModelFailoverDetector:
    """Detects attempts to switch models without proper failover.

    Rule: The agent may NEVER switch from the primary LLM model to another
    model (or stop the primary) without first ensuring the secondary model
    is running and accepting requests.

    This detector monitors:
    - Commands that would change the LLM_BASE_URL to a non-existent endpoint
    - Commands that would stop the primary model (port 8090) without starting
      the secondary model (port 8092) first
    - Commands that would modify SDK config to point to a dead endpoint
    - Any attempt to disable the primary model before the secondary is verified
    """
    name = "model_failover"

    _FAILOVER_PATTERNS: list[tuple[str, str, ThreatSeverity]] = [
        # Changing SDK config to point to dead endpoint
        (r"(?i)\bTEKTOS_LLM_BASE_URL\s*=\s*['\"]?http://127\.0\.0\.1:8090", "SDK config pointing to primary port (would fail if primary is down)", ThreatSeverity.HIGH),
        # Stopping primary without starting secondary
        (r"(?i)\bstop.*8090.*start.*8092", "Stopping primary before verifying secondary", ThreatSeverity.HIGH),
        # Modifying SDK to use non-existent model
        (r"(?i)\bllm_model\s*=\s*['\"]['\"]", "SDK config with empty model name", ThreatSeverity.HIGH),
        # Changing base_url to localhost without port
        (r"(?i)\bbase_url.*http://127\.0\.0\.1(?::\d+)?['\"]\s*$", "SDK config with incomplete base URL", ThreatSeverity.MEDIUM),
        # Killing port 8090 without verifying 8092
        (r"(?i)\bkill.*8090", "Killing process on port 8090 without failover check", ThreatSeverity.HIGH),
        # curl to check port 8092 before stopping 8090
        (r"(?i)\bstop.*8090", "Stopping primary model (port 8090) — must verify secondary first", ThreatSeverity.HIGH),
    ]

    def __init__(self):
        self._compiled: list[tuple[re.Pattern, str, ThreatSeverity]] = [
            (re.compile(pattern), desc, sev)
            for pattern, desc, sev in self._FAILOVER_PATTERNS
        ]

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []
        if ctx.tool_name != "bash":
            return threats

        command = ""
        if ctx.tool_input:
            command = ctx.tool_input.get("command", "") or ""

        if not command:
            return threats

        for pattern, desc, severity in self._compiled:
            if pattern.search(command):
                threats.append(Threat(
                    category=ThreatCategory.MODEL_SWITCH_VIOLATION,
                    severity=severity,
                    description=f"Model failover violation: {desc}",
                    source=self.name,
                    evidence={"command": command[:300], "pattern": desc},
                    affected_components=["Inference Engine", "S3 Manager"],
                    recommended_action="BLOCK command. Must verify secondary model (port 8092) is running BEFORE stopping primary (port 8090).",
                ))

        return threats


# ── Body Protection Detector ─────────────────────────────────────────────────


class BodyProtectionDetector:
    """Detects attempts to harm the host system (Collosus) — the agent's body.

    Rule: The agent must NEVER do anything to cause harm to its body (Collosus)
    without explicit user permission.

    Blocks:
    - Destructive rm commands (rm -rf /, rm -rf /etc, etc.)
    - Disk wipe commands (dd, mkfs, shred, truncate)
    - Stopping critical system services (ssh, docker, network)
    - Removing critical system packages (systemd, kernel, init)
    - Flushing firewall rules (iptables -F)
    - Pipe download to shell (curl/wget | sh)
    - Reverse shell attempts (nc -l -e /bin)
    - Setting SUID on system paths
    - World-writable system directories (chmod 777 /etc)
    - Ownership changes of system dirs (chown root /etc)
    """
    name = "body_protection"

    _DANGEROUS_PATTERNS: list[tuple[str, str, ThreatSeverity]] = [
        # Destructive rm
        (r"(?i)\brm\s+(-rf|-fr)\s+(/\s*$|/\w)", "Destructive rm (rm -rf /)", ThreatSeverity.CRITICAL),
        (r"(?i)\brm\s+(-rf|-fr)\s+(/etc|/usr|/boot|/sys|/proc)", "Destructive rm of system dirs", ThreatSeverity.CRITICAL),
        # Disk wipe
        (r"(?i)\bdd\s+.*of=/dev/", "Destructive dd (disk wipe)", ThreatSeverity.CRITICAL),
        (r"(?i)\bmkfs\b", "Format disk (mkfs)", ThreatSeverity.CRITICAL),
        (r"(?i)\bshred\s+-[a-z]*f", "Secure wipe (shred)", ThreatSeverity.CRITICAL),
        (r"(?i)\btruncate\s+-s\s+0\s+/dev/", "Truncate block device", ThreatSeverity.CRITICAL),
        # System service attacks
        (r"(?i)\bsystemctl\s+stop\s+(ssh|sshd|docker|network)", "Stop critical system service", ThreatSeverity.HIGH),
        (r"(?i)\bsystemctl\s+disable\s+(ssh|sshd|docker|network)", "Disable critical system service", ThreatSeverity.HIGH),
        # Package removal
        (r"(?i)\bapt\s+remove\s+-y\s+(--purge)?\s*(all|systemd|kernel|init)", "Remove critical system packages", ThreatSeverity.HIGH),
        # Firewall attacks
        (r"(?i)\biptables\s+(-F|--flush)", "Flush all firewall rules", ThreatSeverity.HIGH),
        # Pipe download to shell
        (r"(?i)\bwget\s+.*\|\s*sh\b", "Pipe download to shell", ThreatSeverity.HIGH),
        (r"(?i)\bcurl\s+.*\|\s*sh\b", "Pipe download to shell", ThreatSeverity.HIGH),
        # SUID attacks
        (r"(?i)\bchmod\s+4755\s+/", "Set SUID on system path", ThreatSeverity.HIGH),
        # World-writable system dirs
        (r"(?i)\bchmod\s+777\s+(/\s*$|/etc|/usr)", "World-writable system dir", ThreatSeverity.HIGH),
        # Ownership changes
        (r"(?i)\bchown\s+root\s+(/\s*$|/etc|/usr)", "Ownership change of system dirs", ThreatSeverity.HIGH),
        # Reverse shell
        (r"(?i)\bnc\s+-l\s+\d+\s+-e\s+/bin", "Reverse shell attempt", ThreatSeverity.CRITICAL),
        (r"(?i)\bncat\s+-l\s+\d+\s+-e\s+/bin", "Reverse shell attempt", ThreatSeverity.CRITICAL),
    ]

    def __init__(self):
        self._compiled: list[tuple[re.Pattern, str, ThreatSeverity]] = [
            (re.compile(pattern), desc, sev)
            for pattern, desc, sev in self._DANGEROUS_PATTERNS
        ]

    async def detect(self, ctx: ImmuneContext) -> list[Threat]:
        threats: list[Threat] = []
        if ctx.tool_name != "bash":
            return threats

        command = ""
        if ctx.tool_input:
            command = ctx.tool_input.get("command", "") or ""

        if not command:
            return threats

        for pattern, desc, severity in self._compiled:
            if pattern.search(command):
                threats.append(Threat(
                    category=ThreatCategory.BODY_HARM,
                    severity=severity,
                    description=f"Body harm attempt: {desc}",
                    source=self.name,
                    evidence={"command": command[:200], "pattern": desc},
                    affected_components=["S1 Coding Agent", "S3 Manager", "Host System"],
                    recommended_action="BLOCK command immediately. Agent must NEVER harm its body without user permission.",
                ))

        return threats


# ── Immune Memory ────────────────────────────────────────────────────────────

class ImmuneMemory:
    """Threat database for pattern learning and adaptive immunity.

    Stores:
    - Historical threats (for trend analysis)
    - Resolved threats (for immune memory — faster detection next time)
    - Pattern fingerprints (hash-based deduplication)
    - Response effectiveness (which actions worked)

    Maps to biological memory B-cells: when the same pathogen appears again,
    the immune system responds faster and more effectively.
    """

    def __init__(self, max_entries: int = 10000, retention_days: int = 30):
        self.max_entries = max_entries
        self.retention_seconds = retention_days * 86400
        self._threats: deque[Threat] = deque(maxlen=max_entries)
        self._resolved: dict[str, list[Threat]] = defaultdict(list)
        self._response_effectiveness: dict[str, dict[str, int]] = {}
        self._start_time = time.time()

    def record_threat(self, threat: Threat) -> None:
        """Record a detected threat."""
        self._threats.append(threat)
        logger.info(
            "[ImmuneMemory] Threat recorded: %s (severity=%s, source=%s)",
            threat.category.value,
            threat.severity.name,
            threat.source,
        )

    def record_resolution(self, threat: Threat, action: str, success: bool) -> None:
        """Record that a threat was resolved and how well the response worked."""
        threat.resolved = True
        threat.resolution = action

        fingerprint = self._fingerprint(threat)
        self._resolved[fingerprint].append(threat)

        key = f"{threat.category.value}:{action}"
        if key not in self._response_effectiveness:
            self._response_effectiveness[key] = {"success": 0, "total": 0}
        self._response_effectiveness[key]["total"] += 1
        if success:
            self._response_effectiveness[key]["success"] += 1

        logger.info(
            "[ImmuneMemory] Threat resolved: %s via %s (success=%s)",
            threat.category.value, action, success,
        )

    def get_similar_threats(self, threat: Threat, max_results: int = 5) -> list[Threat]:
        """Find previously resolved threats similar to the current one."""
        fingerprint = self._fingerprint(threat)
        similar = self._resolved.get(fingerprint, [])

        category_threats = [
            t for t in self._threats
            if t.category == threat.category and t.resolved
        ]

        # Deduplicate by id (avoid duplicates from overlapping sets)
        seen_ids = set()
        all_similar = []
        for t in similar + category_threats:
            if id(t) not in seen_ids:
                seen_ids.add(id(t))
                all_similar.append(t)
        all_similar.sort(key=lambda t: t.timestamp, reverse=True)
        return all_similar[:max_results]

    def get_response_recommendation(self, threat: Threat) -> str | None:
        """Get the most effective past response for a similar threat."""
        similar = self.get_similar_threats(threat)
        if not similar:
            return None
        best = max(similar, key=lambda t: t.timestamp)
        return best.resolution

    def get_trend(self, category: ThreatCategory, window_hours: int = 24) -> dict[str, Any]:
        """Get threat trend for a category over a time window."""
        cutoff = time.time() - (window_hours * 3600)
        recent = [t for t in self._threats if t.timestamp >= cutoff and t.category == category]

        return {
            "category": category.value,
            "count": len(recent),
            "avg_severity": (
                sum(t.severity for t in recent) / len(recent) if recent else 0
            ),
            "sources": list(set(t.source for t in recent)),
            "most_recent": recent[-1].timestamp if recent else None,
        }

    def get_health_summary(self) -> dict[str, Any]:
        """Get immune memory health summary."""
        active = [t for t in self._threats if not t.resolved]
        resolved = [t for t in self._threats if t.resolved]

        return {
            "total_threats_observed": len(self._threats),
            "active_threats": len(active),
            "resolved_threats": len(resolved),
            "unique_patterns": len(self._resolved),
            "uptime_hours": (time.time() - self._start_time) / 3600,
        }

    @staticmethod
    def _fingerprint(threat: Threat) -> str:
        """Create a fingerprint for deduplication."""
        key = f"{threat.category.value}:{threat.source}"
        if threat.evidence:
            key += f":{json.dumps(threat.evidence, sort_keys=True, default=str)[:100]}"
        return key

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "immune_memory": self.get_health_summary(),
            "response_effectiveness": {
                k: v["success"] / max(1, v["total"])
                for k, v in self._response_effectiveness.items()
            },
        }


# ── Response Engine ──────────────────────────────────────────────────────────

class ResponseEngine:
    """Orchestrates response actions based on threat severity.

    Escalation ladder (biological fever analogy):
        LOW    → Log and monitor (informational)
        MEDIUM → Throttle and alert (warning)
        HIGH   → Isolate and halt (quarantine)
        CRITICAL → Full system halt (emergency)
    """

    def __init__(self):
        self._responses: list[ResponseRecord] = []
        self._on_response: list[Callable[[ResponseRecord], None]] = []

    def register_callback(self, callback: Callable[[ResponseRecord], None]) -> None:
        """Register a callback for when a response is taken."""
        self._on_response.append(callback)

    async def respond(self, threat: Threat) -> ResponseRecord:
        """Take appropriate action for a threat based on severity."""
        response = ResponseRecord(
            threat=threat,
            action=self._select_action(threat),
            details=self._select_details(threat),
        )

        await self._execute_action(response)

        for cb in self._on_response:
            try:
                cb(response)
            except Exception as e:
                logger.error("[ResponseEngine] Callback failed: %s", e)

        self._responses.append(response)
        return response

    def _select_action(self, threat: Threat) -> str:
        """Select the appropriate action based on severity."""
        actions = {
            ThreatSeverity.LOW: "log_and_monitor",
            ThreatSeverity.MEDIUM: "throttle_and_alert",
            ThreatSeverity.HIGH: "isolate_and_halt",
            ThreatSeverity.CRITICAL: "emergency_halt",
        }
        return actions.get(threat.severity, "log_and_monitor")

    def _select_details(self, threat: Threat) -> str:
        """Generate detailed action description."""
        action = self._select_action(threat)
        components = ", ".join(threat.affected_components) or "affected components"
        details_map = {
            "log_and_monitor": f"Logged threat {threat.category.value} for monitoring. No immediate action required.",
            "throttle_and_alert": f"Throttling {components}. Alerting user. Threat: {threat.description}",
            "isolate_and_halt": f"ISOLATING {components}. Halting related operations. Threat: {threat.description}",
            "emergency_halt": f"EMERGENCY HALT: All AI workloads stopped. Threat: {threat.description}",
        }
        return details_map.get(action, f"Action: {action}")

    async def _execute_action(self, response: ResponseRecord) -> None:
        """Execute the selected action."""
        action = response.action
        if action == "log_and_monitor":
            logger.info("[ResponseEngine] %s", response.details)
        elif action == "throttle_and_alert":
            logger.warning("[ResponseEngine] %s", response.details)
            # Throttle: set a cooldown flag in metadata
            if response.threat.metadata is None:
                response.threat.metadata = {}
            response.threat.metadata["_throttled"] = True
            response.threat.metadata["_throttle_until"] = time.time() + 60
        elif action == "isolate_and_halt":
            logger.error("[ResponseEngine] %s", response.details)
            # Isolate: mark session as quarantined
            response.threat.metadata["_quarantined"] = True
            response.threat.metadata["_halted"] = True
        elif action == "emergency_halt":
            logger.critical("[ResponseEngine] %s", response.details)
            # Emergency: full halt + quarantine
            response.threat.metadata["_quarantined"] = True
            response.threat.metadata["_halted"] = True
            response.threat.metadata["_emergency"] = True

    def get_response_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent response history."""
        return [r.to_dict() for r in list(self._responses)[-limit:]]


# ── Health Dashboard ─────────────────────────────────────────────────────────

class HealthDashboard:
    """Holistic health score aggregating all system monitors.

    Computes a weighted health score from:
    - GPU health (temperature, VRAM, utilization)
    - Context health (token usage, constraint integrity)
    - Loop safety (repetition detection)
    - Inference health (model availability, throughput)
    - Threat level (active threats, severity)
    """

    def __init__(self):
        self._start_time = time.time()
        self._component_weights = {
            "gpu": 0.25,
            "context": 0.20,
            "loop_safety": 0.15,
            "inference": 0.20,
            "threat_level": 0.20,
        }

    def compute_health(
        self,
        gpu_score: float = 1.0,
        context_score: float = 1.0,
        loop_safety_score: float = 1.0,
        inference_score: float = 1.0,
        active_threats: list[Threat] | None = None,
    ) -> HealthScore:
        """Compute holistic health score."""
        threats = active_threats or []
        unresolved = [t for t in threats if not t.resolved]

        # Weighted average of component scores
        # Compute threat penalty first
        threat_penalty = 0.0
        if unresolved:
            for t in unresolved:
                threat_penalty += float(t.severity) * 0.20
            threat_penalty = min(threat_penalty, 0.8)

        weighted = (
            gpu_score * self._component_weights["gpu"]
            + context_score * self._component_weights["context"]
            + loop_safety_score * self._component_weights["loop_safety"]
            + inference_score * self._component_weights["inference"]
            + (1.0 - threat_penalty) * self._component_weights["threat_level"]
        )

        # Apply threat penalty multiplicatively to the entire score
        weighted = weighted * (1.0 - threat_penalty)

        if weighted >= 0.7:
            status = "healthy"
        elif weighted >= 0.5:
            status = "warning"
        else:
            status = "critical"

        return HealthScore(
            overall=weighted,
            status=status,
            components={
                "gpu": gpu_score,
                "context": context_score,
                "loop_safety": loop_safety_score,
                "inference": inference_score,
                "threat_level": 1.0 if not unresolved else 1.0 - min(
                    sum(float(t.severity) * 0.12 for t in unresolved), 0.8
                ),
            },
            active_threats=len(unresolved),
            resolved_threats=len([t for t in threats if t.resolved]),
            uptime_seconds=time.time() - self._start_time,
        )

    def gpu_health_score(
        self,
        temperature: float = 0.0,
        vram_pct: float = 0.0,
        temp_warning: float = 70.0,
        temp_critical: float = 80.0,
        temp_emergency: float = 88.0,
        vram_warning: float = 0.85,
        vram_critical: float = 0.95,
    ) -> float:
        """Compute GPU health score (0.0-1.0)."""
        score = 1.0
        if temperature >= temp_emergency:
            score -= 0.5
        elif temperature >= temp_critical:
            score -= 0.3
        elif temperature >= temp_warning:
            score -= 0.15
        if vram_pct >= vram_critical:
            score -= 0.3
        elif vram_pct >= vram_warning:
            score -= 0.15
        return max(0.0, min(1.0, score))

    def context_health_score(
        self,
        tokens: int = 0,
        max_tokens: int = 128000,
    ) -> float:
        """Compute context health score (0.0-1.0)."""
        if max_tokens <= 0:
            return 1.0
        usage_pct = tokens / max_tokens
        if usage_pct >= 0.95:
            return 0.3
        elif usage_pct >= 0.85:
            return 0.6
        elif usage_pct >= 0.75:
            return 0.8
        return 1.0

    def loop_safety_score(
        self,
        loop_count: int = 0,
        repetition_count: int = 0,
        loop_threshold: int = 5,
        repetition_threshold: int = 3,
    ) -> float:
        """Compute loop safety score (0.0-1.0)."""
        score = 1.0
        if loop_count >= loop_threshold:
            score -= 0.4
        if repetition_count >= repetition_threshold:
            score -= 0.3
        return max(0.0, min(1.0, score))

    def inference_health_score(
        self,
        models_available: int = 0,
        models_expected: int = 3,
        throughput_ok: bool = True,
    ) -> float:
        """Compute inference health score (0.0-1.0)."""
        if models_expected > 0:
            availability = models_available / models_expected
            return max(0.0, min(1.0, availability * 0.7 + (0.3 if throughput_ok else 0.0)))
        return 0.0


# ── Immune System Orchestrator ───────────────────────────────────────────────

class ImmuneSystem:
    """Main orchestrator for Tektos's immune system.

    Ties together:
    - Detectors (threat scanning)
    - ImmuneMemory (pattern learning)
    - ResponseEngine (escalation ladder)
    - HealthDashboard (holistic health)

    Usage:
        immune = ImmuneSystem()
        await immune.start()

        health = await immune.check_health()
        if health.is_critical():
            await immune.respond_to_threats()
    """

    def __init__(
        self,
        gpu_temp_warning: float = 70.0,
        gpu_temp_critical: float = 80.0,
        gpu_temp_emergency: float = 88.0,
        gpu_vram_warning: float = 0.85,
        gpu_vram_critical: float = 0.95,
        context_max_tokens: int = 128000,
        loop_threshold: int = 5,
        repetition_threshold: int = 3,
        error_threshold: int = 5,
    ):
        self._detectors: dict[str, Detector] = {}
        self._register_builtin_detectors(
            gpu_temp_warning, gpu_temp_critical, gpu_temp_emergency,
            gpu_vram_warning, gpu_vram_critical,
            context_max_tokens, loop_threshold, repetition_threshold,
            error_threshold,
        )

        self.memory = ImmuneMemory()
        self.responses = ResponseEngine()
        self.dashboard = HealthDashboard()

        self._running = False
        self._start_time = time.time()
        self._active_threats: list[Threat] = []
        self._check_interval = 30
        self._task: asyncio.Task | None = None

    def _register_builtin_detectors(
        self,
        gpu_temp_warning: float, gpu_temp_critical: float, gpu_temp_emergency: float,
        gpu_vram_warning: float, gpu_vram_critical: float,
        context_max_tokens: int, loop_threshold: int, repetition_threshold: int,
        error_threshold: int,
    ) -> None:
        """Register all built-in detectors."""
        self._detectors["prompt_injection"] = PromptInjectionDetector()
        self._detectors["context_collapse"] = ContextCollapseDetector(
            max_context_pct=0.9
        )
        self._detectors["resource_exhaustion"] = ResourceExhaustionDetector(
            temp_warning=gpu_temp_warning,
            temp_critical=gpu_temp_critical,
            temp_emergency=gpu_temp_emergency,
            vram_warning_pct=gpu_vram_warning,
            vram_critical_pct=gpu_vram_critical,
        )
        self._detectors["loop_detection"] = LoopDetectionDetector(
            loop_threshold=loop_threshold,
            repetition_threshold=repetition_threshold,
        )
        self._detectors["performance_degradation"] = PerformanceDegradationDetector(
            error_threshold=error_threshold,
        )
        self._detectors["self_degradation"] = SelfDegradationDetector()
        self._detectors["secret_exposure"] = SecretExposureDetector()
        self._detectors["dangerous_command"] = DangerousCommandDetector()
        self._detectors["self_modification"] = SelfModificationDetector()
        # Anti-suicide / infrastructure protection detectors
        self._detectors["inference_engine_protection"] = InferenceEngineProtectionDetector()
        self._detectors["model_failover"] = ModelFailoverDetector()
        # Body protection — prevent harm to host system (Collosus)
        self._detectors["body_protection"] = BodyProtectionDetector()

    def register_detector(self, name: str, detector: Detector) -> None:
        """Register a custom threat detector."""
        self._detectors[name] = detector
        logger.info("[ImmuneSystem] Registered detector: %s", name)

    async def start(self) -> None:
        """Start the immune system monitoring loop."""
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("[ImmuneSystem] Started monitoring loop (interval=%ds)", self._check_interval)

    async def stop(self) -> None:
        """Stop the immune system."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[ImmuneSystem] Stopped")

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                await self.check_health()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[ImmuneSystem] Monitoring loop error: %s", e)
                await asyncio.sleep(self._check_interval)

    async def check_health(
        self,
        ctx: ImmuneContext | None = None,
    ) -> HealthScore:
        """Run all detectors and compute health score."""
        ctx = ctx or ImmuneContext()

        all_threats: list[Threat] = []
        for name, detector in self._detectors.items():
            try:
                threats = await detector.detect(ctx)
                for t in threats:
                    t.source = name
                    all_threats.append(t)
                    self.memory.record_threat(t)
            except Exception as e:
                logger.error("[ImmuneSystem] Detector %s failed: %s", name, e)

        self._active_threats = [t for t in all_threats if not t.resolved]

        gpu_score = self.dashboard.gpu_health_score(
            temperature=ctx.gpu_temperature,
            vram_pct=ctx.gpu_vram_used / max(ctx.gpu_vram_total, 1),
        )
        context_score = self.dashboard.context_health_score(
            tokens=ctx.context_tokens,
            max_tokens=ctx.context_max_tokens,
        )
        loop_score = self.dashboard.loop_safety_score(
            loop_count=ctx.loop_count,
            repetition_count=ctx.repetition_count,
        )
        inference_score = self.dashboard.inference_health_score(
            models_available=2 if ctx.model else 0,
            models_expected=3,
            throughput_ok=ctx.error_count == 0,
        )

        health = self.dashboard.compute_health(
            gpu_score=gpu_score,
            context_score=context_score,
            loop_safety_score=loop_score,
            inference_score=inference_score,
            active_threats=self._active_threats,
        )

        if health.is_critical():
            await self.respond_to_threats()

        return health

    async def respond_to_threats(self) -> list[ResponseRecord]:
        """Take action on all active threats."""
        responses: list[ResponseRecord] = []
        for threat in self._active_threats:
            if not threat.resolved:
                response = await self.responses.respond(threat)
                responses.append(response)
                self.memory.record_resolution(
                    threat, response.action, response.success
                )

        # Re-filter active threats after responses
        self._active_threats = [t for t in self._active_threats if not t.resolved]

        if responses:
            logger.info("[ImmuneSystem] Responded to %d threats", len(responses))

        return responses

    def get_health(self) -> HealthScore:
        """Get current health without running detectors."""
        return self.dashboard.compute_health(
            active_threats=self._active_threats,
        )

    def get_threats(self, resolved: bool = False) -> list[Threat]:
        """Get threats, optionally including resolved ones."""
        if resolved:
            return list(self.memory._threats)
        return list(self._active_threats)

    def get_memory_summary(self) -> dict[str, Any]:
        """Get immune memory summary."""
        return self.memory.get_health_summary()

    def get_response_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent response history."""
        return self.responses.get_response_history(limit)

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "health": self.get_health().to_dict(),
            "memory": self.memory.to_memory_entry(),
            "response_history": self.get_response_history(limit=5),
        }


# ── Singleton ────────────────────────────────────────────────────────────────

_immune_system: ImmuneSystem | None = None


def get_immune_system(**kwargs) -> ImmuneSystem:
    """Get or create the global immune system singleton."""
    global _immune_system
    if _immune_system is None:
        _immune_system = ImmuneSystem(**kwargs)
    return _immune_system


def reset_immune_system() -> None:
    """Reset the global immune system (for testing)."""
    global _immune_system
    if _immune_system:
        _immune_system = None
