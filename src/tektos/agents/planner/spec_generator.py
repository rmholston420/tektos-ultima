"""Structured Spec Generator.

Outputs a standardized, structured build spec for deterministic Coding Agent execution.
The spec follows YAML format with all necessary information: description, requirements,
constraints, tech stack, test strategy, architecture choice, and phased deliverables.

This is the final stage of the pipeline. The spec is what the Coding Agent executes.
"""

from __future__ import annotations

from typing import Any

from .language_game import LanguageGame
from .models import (
    ArchitectureChoice,
    BuildSpec,
    SpecPhase,
)


def generate_spec(
    original_prompt: str,
    translated_prompt: str,
    language_game: LanguageGame,
    architecture: ArchitectureChoice,
    requirements: list[str] | None = None,
    constraints: list[str] | None = None,
    tech_stack: list[str] | None = None,
    test_strategy: str = "spec-driven",
    phases: list[dict[str, Any]] | None = None,
    notes: list[str] | None = None,
    context_budget_warning: str | None = None,
    description: str | None = None,
    synthesis_guidance: str = "",
) -> BuildSpec:
    """Generate a structured build spec from the pipeline output.

    Args:
        original_prompt: The user's original natural language prompt.
        translated_prompt: The Proper Technical English translation.
        language_game: The identified domain language game.
        architecture: The chosen architecture template.
        requirements: List of functional requirements. Auto-extracted from prompt if None.
        constraints: List of non-functional constraints.
        tech_stack: List of technologies to use.
        test_strategy: Testing approach ("tdd" or "spec-driven").
        phases: List of phase dicts with "id", "description", "deliverables".
        notes: Additional notes or caveats.
        context_budget_warning: Warning if spec exceeds context budget.
        description: Brief description of what to build. Auto-extracted if None.

    Returns:
        A BuildSpec object ready for Coding Agent execution.
    """
    # Auto-extract description and requirements if not provided
    if not description:
        description = translated_prompt.split("\n")[0].strip()
        if len(description) > 200:
            description = description[:197] + "..."

    if not requirements:
        requirements = _extract_requirements(translated_prompt)

    if not constraints:
        constraints = _extract_constraints(translated_prompt)

    if not phases:
        phases = _default_phases(requirements)

    # Convert phase dicts to SpecPhase objects
    spec_phases: list[SpecPhase] = []
    for phase_data in phases:
        spec_phases.append(SpecPhase(
            id=phase_data.get("id", f"phase-{len(spec_phases)+1}"),
            description=phase_data.get("description", ""),
            deliverables=phase_data.get("deliverables", []),
            acceptance_criteria=phase_data.get("acceptance_criteria", []),
            estimated_effort=phase_data.get("estimated_effort", "unknown"),
        ))

    spec_notes = list(notes) if notes else []
    if synthesis_guidance:
        spec_notes.append(f"[SELF-IMPROVEMENT GUIDANCE — Past execution lessons]\n{synthesis_guidance}")
        # Weave actionable guidance into requirements so the Coding Agent
        # sees them as first-class spec items, not just notes
        for line in synthesis_guidance.split("\n"):
            line = line.strip()
            if not line or line.startswith("["):
                continue
            # Skip context/tag lines (indented under guidance)
            if line.startswith("Context:") or line.startswith("Tags:"):
                continue
            # Strip priority markers (⚑ HIGH:, ⚠ URGENT:, -) to get actionable text
            actionable = line
            for prefix in ["⚑ HIGH:", "⚠ URGENT:", "⚑ HIGH", "⚠ URGENT", "⚑ ", "⚠ ", "- "]:
                if actionable.startswith(prefix):
                    actionable = actionable[len(prefix):].strip()
                    break
            if actionable and actionable not in requirements:
                requirements.append(actionable)

    return BuildSpec(
        original_prompt=original_prompt,
        translated_prompt=translated_prompt,
        language_game=language_game,
        description=description,
        requirements=requirements,
        constraints=constraints or [],
        tech_stack=tech_stack or [],
        test_strategy=test_strategy,
        architecture=architecture,
        phases=spec_phases,
        context_budget_warning=context_budget_warning,
        notes=spec_notes,
        synthesis_guidance=synthesis_guidance,
    )


def _extract_requirements(text: str) -> list[str]:
    """Extract requirements from a translated prompt.

    Looks for common requirement patterns like:
    - "with [feature]"
    - "that [verb]"
    - "support [capability]"
    - "include [component]"
    - numbered lists (1., 2., 3.)
    """
    requirements: list[str] = []
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Numbered lists
        if line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            requirements.append(line.lstrip("0123456789. "))
        # "with" clauses
        elif " with " in line:
            parts = line.split(" with ")
            if len(parts) > 1:
                requirements.append(parts[-1].strip())
        # "that" clauses
        elif " that " in line:
            parts = line.split(" that ")
            if len(parts) > 1:
                requirements.append(parts[-1].strip())

    # If no structured requirements found, use the full translated prompt
    if not requirements and text.strip():
        requirements = [text.strip()]

    return requirements


def _extract_constraints(text: str) -> list[str]:
    """Extract constraints from a translated prompt.

    Looks for constraint patterns like:
    - "must"
    - "must not"
    - "only"
    - "no"
    - "never"
    """
    constraints: list[str] = []
    text_lower = text.lower()

    constraint_patterns = {
        "must not": "must not",
        "must": "must",
        "only": "only",
        "no ": "no",
        "never": "never",
    }

    for pattern, label in constraint_patterns.items():
        if pattern in text_lower:
            # Extract the constraint phrase
            idx = text_lower.index(pattern)
            end = min(idx + 100, len(text))
            constraint = text[idx:end].strip().rstrip(".")
            constraints.append(constraint)

    return constraints


def _default_phases(requirements: list[str]) -> list[dict[str, Any]]:
    """Generate default phased deliverables based on requirements.

    Phase 1: Minimal viable implementation (the point — 1)
    Phase 2: Features that improve the slice (the line — 2)
    Phase 3: Polish and robustness (the surface — 3)
    Phase 4: Production readiness (the solid — 4)
    """
    if not requirements:
        return [
            {
                "id": "phase-1",
                "description": "Minimal viable implementation",
                "deliverables": [],
                "estimated_effort": "S",
            },
        ]

    # Phase 1: First 2-3 requirements (MVP)
    mvp_count = min(3, len(requirements))
    mvp_reqs = requirements[:mvp_count]

    # Phase 2: Next requirements (improvements)
    improvement_reqs = requirements[mvp_count:] if mvp_count < len(requirements) else []

    # Phase 3: Polish (derived from total requirement count)
    polish_needed = len(requirements) > 2

    phases: list[dict[str, str]] = [
        {
            "id": "phase-1",
            "description": "Minimal viable implementation",
            "deliverables": mvp_reqs,
            "acceptance_criteria": [
                f"Each of the {mvp_count} requirements is implemented and tested",
                "All acceptance criteria are met",
            ],
            "estimated_effort": "S" if mvp_count <= 2 else "M",
        },
    ]

    if improvement_reqs:
        phases.append({
            "id": "phase-2",
            "description": "Features that improve the slice",
            "deliverables": improvement_reqs,
            "acceptance_criteria": [
                f"Each of the {len(improvement_reqs)} improvement requirements is implemented and tested",
            ],
            "estimated_effort": "M" if len(improvement_reqs) <= 3 else "L",
        })

    if polish_needed:
        phases.append({
            "id": "phase-3",
            "description": "Polish and robustness",
            "deliverables": ["Error handling", "Input validation", "Documentation"],
            "acceptance_criteria": [
                "All error paths are handled",
                "Input validation is comprehensive",
                "Documentation covers all public APIs",
            ],
            "estimated_effort": "S",
        })

    return phases
