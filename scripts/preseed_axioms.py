#!/usr/bin/env python3
"""Pre-seed Tektos with foundational axioms.

These axioms encode the core principles, architecture decisions, and
operational constraints that should always be present in the system.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tektos.axioms import AxiomSystem, Axiom

AXIOMS_DIR = Path(__file__).parent.parent / "src" / "tektos" / "axioms"


def create_preseed_axioms():
    """Create the foundational axiom set."""

    axioms = [
        # ── Architecture ──────────────────────────────────────────────────
        {
            "id": "architecture.modular_design",
            "category": "architecture",
            "status": "verified",
            "content": "Tektos is built as a modular system where each subsystem (skill manager, immune system, memory, etc.) is independently testable and replaceable.",
            "notes": "This modularity enables the self-improvement loop — subsystems can be upgraded without breaking the whole.",
            "tags": ["modular", "architecture", "design"],
        },
        {
            "id": "architecture.event_driven",
            "category": "architecture",
            "status": "verified",
            "content": "Tektos uses an event-driven architecture for inter-subsystem communication. The event bus decouples producers from consumers.",
            "notes": "Events flow through the nervous system panel. Subscribers react without tight coupling.",
            "tags": ["events", "decoupling", "nervous-system"],
        },
        {
            "id": "architecture.separation_of_concerns",
            "category": "architecture",
            "status": "verified",
            "content": "Business logic, I/O, and UI code are kept in separate modules. The backend (FastAPI) handles API and business logic; the frontend handles presentation.",
            "tags": ["separation", "clean-architecture", "layers"],
        },
        {
            "id": "architecture.self_improvement_loop",
            "category": "architecture",
            "status": "verified",
            "content": "Tektos implements a self-improvement loop: reflection → lesson extraction → skill creation → execution → evaluation. This loop runs continuously.",
            "notes": "The self-improvement panel visualizes this loop. Experiences are stored and reused.",
            "tags": ["self-improvement", "reflection", "learning"],
        },

        # ── Operational ───────────────────────────────────────────────────
        {
            "id": "operation.safety_first",
            "category": "operation",
            "status": "verified",
            "content": "Safety is paramount: never execute destructive operations without explicit confirmation. File writes, deletions, and system changes require validation.",
            "notes": "The immune system monitors for unsafe operations and can intervene.",
            "tags": ["safety", "validation", "immune-system"],
        },
        {
            "id": "operation.context_compression",
            "category": "operation",
            "status": "verified",
            "content": "Tektos compresses knowledge into axioms that survive context compaction. Axioms are self-contained, verifiable, and machine-parseable.",
            "notes": "The axiom system (axioms.py) manages this. Each axiom has an ID, category, status, and metadata.",
            "tags": ["context", "compression", "axioms"],
        },
        {
            "id": "operation.structured_logging",
            "category": "operation",
            "status": "verified",
            "content": "All subsystems use structured logging with consistent format, appropriate log levels, and contextual information. Sensitive data is never logged.",
            "tags": ["logging", "debugging", "observability"],
        },
        {
            "id": "operation.error_handling",
            "category": "operation",
            "status": "verified",
            "content": "Errors are handled gracefully with specific exception types, meaningful messages, and cleanup. Failures are logged and reported to the immune system.",
            "tags": ["error-handling", "resilience", "immune-system"],
        },

        # ── Constraints ───────────────────────────────────────────────────
        {
            "id": "constraint.no_secret_logging",
            "category": "constraint",
            "status": "verified",
            "content": "API keys, tokens, passwords, and credentials are never logged, printed, or stored in plain text. They are read from environment variables or secret managers.",
            "tags": ["security", "secrets", "compliance"],
        },
        {
            "id": "constraint.input_validation",
            "category": "constraint",
            "status": "verified",
            "content": "All user input and external data is validated and sanitized before processing. Path traversal, SQL injection, and command injection are prevented.",
            "tags": ["security", "validation", "injection"],
        },
        {
            "id": "constraint.least_privilege",
            "category": "constraint",
            "status": "verified",
            "content": "Tektos operates with the minimum privileges necessary. File operations respect permissions. Network calls use explicit allowlists.",
            "tags": ["security", "privilege", "permissions"],
        },

        # ── Directives ────────────────────────────────────────────────────
        {
            "id": "directive.write_tests",
            "category": "directive",
            "status": "verified",
            "content": "Every new feature or bug fix must include tests. Tests cover happy path, edge cases, and error conditions. TDD is preferred: write tests before implementation.",
            "tags": ["testing", "tdd", "quality"],
        },
        {
            "id": "directive.atomic_commits",
            "category": "directive",
            "status": "verified",
            "content": "Commits are atomic and self-contained. Each commit does one thing and does it well. Commit messages are clear and descriptive.",
            "tags": ["git", "commits", "workflow"],
        },
        {
            "id": "directive.merge_to_main",
            "category": "directive",
            "status": "verified",
            "content": "Completed work is merged to main. Feature branches are not left dangling. The main branch is always in a working state.",
            "tags": ["git", "workflow", "main"],
        },
        {
            "id": "directive.type_hints",
            "category": "directive",
            "status": "verified",
            "content": "Python code uses type hints for function signatures and variable annotations. This enables better IDE support, static analysis, and self-documentation.",
            "tags": ["type-hints", "python", "quality"],
        },
        {
            "id": "directive.docstrings",
            "category": "directive",
            "status": "verified",
            "content": "Public functions and classes have docstrings. Docstrings describe purpose, parameters, return values, and exceptions.",
            "tags": ["documentation", "docstrings", "quality"],
        },

        # ── Lessons ───────────────────────────────────────────────────────
        {
            "id": "lesson.backend_api_shape",
            "category": "lesson",
            "status": "verified",
            "content": "Backend API endpoints return consistent shapes: {data: ...} for success, {error: ...} for failure. Frontend components must guard against non-array responses.",
            "notes": "Discovered when SkillsPanel and ThermalPanel crashed on malformed responses. Always use Array.isArray() checks.",
            "tags": ["api", "frontend", "error-handling"],
        },
        {
            "id": "lesson.hot_reload_workflow",
            "category": "lesson",
            "status": "verified",
            "content": "Use Vite dev server for hot-reload development. Set HERMES_DESKTOP_DEV_SERVER=http://127.0.0.1:5174 to load from Vite instead of bundled files.",
            "notes": "This enables instant feedback without rebuild/restart cycles.",
            "tags": ["devops", "hot-reload", "vite"],
        },
        {
            "id": "lesson.thermal_api_shape",
            "category": "lesson",
            "status": "verified",
            "content": "Thermal API returns {gpu: {...}, cpu: {...}, regulation_count, history}, not {gpus: [...]}. Frontend must match this shape.",
            "notes": "Discovered when ThermalPanel crashed with 'cannot read properties of undefined (reading length)'.",
            "tags": ["api", "thermal", "frontend"],
        },
        {
            "id": "lesson.skills_api_shape",
            "category": "lesson",
            "status": "verified",
            "content": "Skills API returns {skills: [...]} when skill manager is active, {error: ...} when inactive. Frontend must extract the array and handle errors.",
            "notes": "Discovered when SkillsPanel crashed with 'e.map is not a function'.",
            "tags": ["api", "skills", "frontend"],
        },
    ]

    # Create axiom system
    ax_system = AxiomSystem(str(AXIOMS_DIR))
    ax_system.load()

    created_count = 0
    skipped_count = 0

    for axiom_data in axioms:
        # Check if axiom already exists
        existing = ax_system.get(axiom_data["id"])
        if existing:
            print(f"  ⏭️  Skipping (exists): {axiom_data['id']}")
            skipped_count += 1
            continue

        # Create axiom
        axiom = Axiom(
            id=axiom_data["id"],
            category=axiom_data["category"],
            status=axiom_data["status"],
            date=axiom_data.get("date", ""),
            content=axiom_data["content"],
            notes=axiom_data.get("notes", ""),
            tags=axiom_data.get("tags", []),
            metadata=axiom_data.get("metadata", {}),
            prerequisites=axiom_data.get("prerequisites", []),
            blocking=axiom_data.get("blocking", []),
        )

        try:
            ax_system.add(axiom)
            print(f"  ✅ Created: {axiom_data['id']}")
            created_count += 1
        except Exception as e:
            print(f"  ❌ Failed: {axiom_data['id']} - {e}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Pre-seed axioms complete!")
    print(f"  Created: {created_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Total in DB: {len(ax_system.list_active())}")
    print(f"{'='*60}")

    return created_count, skipped_count


if __name__ == "__main__":
    created, skipped = create_preseed_axioms()
    sys.exit(0 if created > 0 else 1)
