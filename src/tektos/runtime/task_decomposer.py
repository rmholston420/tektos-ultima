"""Task Decomposer — breaks complex tasks into numbered, sequential sub-tasks.

High-ROI improvement for Terminal-Bench and similar multi-step tasks.
The model struggles with open-ended complex prompts; explicit sub-task
instructions with completion criteria dramatically improve success rates.

Usage:
    decomposer = TaskDecomposer()
    plan = decomposer.decompose("Build chess move generator via regex")
    # Returns structured plan with numbered steps, each with:
    #   - description: what to do
    #   - expected_output: how to verify completion
    #   - tools_needed: recommended tools
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("tektos.task_decomposer")


@dataclass
class SubTask:
    """A single decomposed sub-task."""
    step_number: int
    description: str
    expected_output: str
    tools_needed: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | complete


@dataclass
class DecompositionPlan:
    """A complete task decomposition plan."""
    original_task: str
    sub_tasks: list[SubTask] = field(default_factory=list)
    phase: str = "research"  # research | scaffold | implement | verify


class TaskDecomposer:
    """Breaks complex tasks into sequential, verifiable sub-tasks.

    Uses heuristic rules (not LLM) to decompose common task patterns:
    - Build/compile tasks
    - Code generation tasks
    - Research + implementation tasks
    - File manipulation tasks
    """

    def __init__(self) -> None:
        self._plans: dict[str, DecompositionPlan] = {}

    def decompose(self, task: str, task_id: str | None = None) -> DecompositionPlan:
        """Decompose a task into sub-tasks based on heuristics.

        Args:
            task: The original task description.
            task_id: Optional identifier for this decomposition.

        Returns:
            DecompositionPlan with numbered sub-tasks.
        """
        plan_id = task_id or f"plan_{len(self._plans)}"
        plan = DecompositionPlan(original_task=task)

        # Detect task type and apply appropriate decomposition
        task_lower = task.lower()

        if self._is_build_task(task_lower):
            plan = self._decompose_build_task(task)
        elif self._is_code_generation_task(task_lower):
            plan = self._decompose_code_generation(task)
        elif self._is_regex_or_pattern_task(task_lower):
            plan = self._decompose_regex_task(task)
        elif self._is_download_build_task(task_lower):
            plan = self._decompose_download_build(task)
        else:
            plan = self._decompose_generic(task)

        self._plans[plan_id] = plan
        log.info(f"[TaskDecomposer] Decomposed task into {len(plan.sub_tasks)} sub-tasks")
        return plan

    def get_plan(self, plan_id: str) -> DecompositionPlan | None:
        """Retrieve a plan by ID."""
        return self._plans.get(plan_id)

    def _is_build_task(self, task: str) -> bool:
        return any(kw in task for kw in ["build", "compile", "make", "cmake", "ccomp", "build"])

    def _is_code_generation_task(self, task: str) -> bool:
        return any(kw in task for kw in ["write", "create", "implement", "generate", "implement"])

    def _is_regex_or_pattern_task(self, task: str) -> bool:
        return any(kw in task for kw in ["regex", "pattern", "chess", "fen", "re.json"])

    def _is_download_build_task(self, task: str) -> bool:
        return any(kw in task for kw in ["download", "fetch", "clone", "git clone", "tar", "tarball"])

    def _decompose_build_task(self, task: str) -> DecompositionPlan:
        """Decompose: check tools → download → configure → build → verify."""
        return DecompositionPlan(
            original_task=task,
            sub_tasks=[
                SubTask(
                    step_number=1,
                    description="Check available tools: gcc, g++, make, cmake, python3, etc.",
                    expected_output="List of available build tools and their versions",
                    tools_needed=["bash"],
                ),
                SubTask(
                    step_number=2,
                    description="Download or clone source code to /tmp/",
                    expected_output="Source code extracted in /tmp/<project>/",
                    tools_needed=["web_fetch", "bash"],
                ),
                SubTask(
                    step_number=3,
                    description="Read README/INSTALL for build instructions",
                    expected_output="Build instructions identified",
                    tools_needed=["file_read"],
                ),
                SubTask(
                    step_number=4,
                    description="Configure the build (./configure, cmake, etc.)",
                    expected_output="Build system configured successfully",
                    tools_needed=["bash"],
                ),
                SubTask(
                    step_number=5,
                    description="Build the project (make, cmake --build, etc.)",
                    expected_output="Binary/executable produced",
                    tools_needed=["bash"],
                ),
                SubTask(
                    step_number=6,
                    description="Verify the build output exists and works",
                    expected_output="Binary runs successfully or produces expected output",
                    tools_needed=["bash"],
                ),
            ],
        )

    def _decompose_code_generation(self, task: str) -> DecompositionPlan:
        """Decompose: research → scaffold → implement → test."""
        return DecompositionPlan(
            original_task=task,
            sub_tasks=[
                SubTask(
                    step_number=1,
                    description="Research the task: search web for relevant documentation, examples, or specifications",
                    expected_output="Key requirements and approach identified",
                    tools_needed=["web_search", "web_extract"],
                ),
                SubTask(
                    step_number=2,
                    description="Create a file skeleton/outline with function signatures and structure",
                    expected_output="File created with basic structure (even if incomplete)",
                    tools_needed=["file_write"],
                ),
                SubTask(
                    step_number=3,
                    description="Implement the core logic in the file",
                    expected_output="File contains complete implementation",
                    tools_needed=["file_write"],
                ),
                SubTask(
                    step_number=4,
                    description="Test the implementation with sample inputs",
                    expected_output="Test runs successfully, output matches expectations",
                    tools_needed=["bash"],
                ),
                SubTask(
                    step_number=5,
                    description="Fix any issues and verify final output",
                    expected_output="Final file is correct and complete",
                    tools_needed=["file_write", "bash"],
                ),
            ],
        )

    def _decompose_regex_task(self, task: str) -> DecompositionPlan:
        """Decompose regex/pattern tasks: understand → generate → validate."""
        return DecompositionPlan(
            original_task=task,
            sub_tasks=[
                SubTask(
                    step_number=1,
                    description="Research the problem: understand the input format, rules, and expected output",
                    expected_output="Clear understanding of input/output format and constraints",
                    tools_needed=["web_search", "web_extract"],
                ),
                SubTask(
                    step_number=2,
                    description="Design the regex patterns: list each pattern and its replacement",
                    expected_output="List of regex patterns with descriptions",
                    tools_needed=["bash"],  # Write to /tmp/patterns.txt for reference
                ),
                SubTask(
                    step_number=3,
                    description="Generate the output file (e.g., re.json) with all regex pairs",
                    expected_output="Output file created at the specified path",
                    tools_needed=["file_write"],
                ),
                SubTask(
                    step_number=4,
                    description="Validate: test the output against sample inputs",
                    expected_output="Output file passes validation tests",
                    tools_needed=["bash"],
                ),
            ],
        )

    def _decompose_download_build(self, task: str) -> DecompositionPlan:
        """Decompose download + build tasks."""
        return DecompositionPlan(
            original_task=task,
            sub_tasks=[
                SubTask(
                    step_number=1,
                    description="Find the download URL for the source code",
                    expected_output="Download URL identified",
                    tools_needed=["web_search"],
                ),
                SubTask(
                    step_number=2,
                    description="Download and extract the source code to /tmp/",
                    expected_output="Source code extracted in /tmp/<project>/",
                    tools_needed=["web_fetch", "bash"],
                ),
                SubTask(
                    step_number=3,
                    description="Read build instructions (README, INSTALL, Makefile)",
                    expected_output="Build process understood",
                    tools_needed=["file_read"],
                ),
                SubTask(
                    step_number=4,
                    description="Install any missing dependencies",
                    expected_output="All dependencies installed",
                    tools_needed=["bash"],
                ),
                SubTask(
                    step_number=5,
                    description="Build the project",
                    expected_output="Build succeeds, binary produced",
                    tools_needed=["bash"],
                ),
                SubTask(
                    step_number=6,
                    description="Verify the build output",
                    expected_output="Binary works correctly",
                    tools_needed=["bash"],
                ),
            ],
        )

    def _decompose_generic(self, task: str) -> DecompositionPlan:
        """Generic decomposition for unknown task types."""
        return DecompositionPlan(
            original_task=task,
            sub_tasks=[
                SubTask(
                    step_number=1,
                    description="Understand the task: identify inputs, outputs, and constraints",
                    expected_output="Clear task requirements documented",
                    tools_needed=["web_search", "web_extract"],
                ),
                SubTask(
                    step_number=2,
                    description="Plan the approach: identify tools and steps needed",
                    expected_output="Implementation plan with numbered steps",
                    tools_needed=["bash"],
                ),
                SubTask(
                    step_number=3,
                    description="Implement the solution: write code/files as needed",
                    expected_output="Implementation files created",
                    tools_needed=["file_write", "bash"],
                ),
                SubTask(
                    step_number=4,
                    description="Test and verify the solution",
                    expected_output="Solution produces correct output",
                    tools_needed=["bash"],
                ),
            ],
        )

    def format_for_prompt(self, plan: DecompositionPlan) -> str:
        """Format the decomposition plan for injection into the system prompt.

        Returns a structured string that tells the agent exactly what to do,
        in what order, and how to verify each step.
        """
        lines = [
            "## TASK DECOMPOSITION — FOLLOW THESE STEPS IN ORDER",
            "",
            f"Original task: {plan.original_task}",
            "",
            "You MUST complete each step before moving to the next. After completing each step,",
            "verify the expected output exists before proceeding.",
            "",
        ]

        for i, sub_task in enumerate(plan.sub_tasks, 1):
            tools = ", ".join(sub_task.tools_needed) if sub_task.tools_needed else "bash, file_write"
            lines.append(f"### Step {i}: {sub_task.description}")
            lines.append(f"- Expected output: {sub_task.expected_output}")
            lines.append(f"- Recommended tools: {tools}")
            lines.append(f"- DO NOT skip this step. DO NOT proceed to the next step until this one is complete.")
            lines.append("")

        lines.append("## IMPORTANT RULES")
        lines.append("- Write files IMMEDIATELY after researching — don't keep searching.")
        lines.append("- After each step, verify the expected output exists before proceeding.")
        lines.append("- If a step fails, fix the issue and retry — don't skip it.")
        lines.append("- The FINAL deliverable is the output file specified in the task.")
        lines.append("- Make sure the output file exists at the EXACT path specified.")

        return "\n".join(lines)
