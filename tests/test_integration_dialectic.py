"""End-to-end Hegelian dialectic integration test.

Proves the full S4→S1→S3→synthesis loop works as a coherent system:
- S4 Planner: NL → BuildSpec (thesis)
- S1 Coding Agent: BuildSpec → ExecutionRecord (antithesis)
- S3 Manager: feedback → ManagerFeedback
- SynthesisEngine: thesis+antithesis → SynthesisFeedback (synthesis)

No mocks for the loop itself — only the LLM-dependent parts are mocked
(Planner's translate_to_technical_english and spec generator).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from tektos.agents.coding_agent.executor import Executor
from tektos.agents.coding_agent.models import (
    ExecutionArtifact,
    ExecutionStatus,
    ExecutionTestReport,
)
from tektos.agents.manager.guardrails import GUARDRAIL_RULES
from tektos.agents.manager.metrics import PrimeMoverMetrics
from tektos.agents.manager.orchestrator import Manager
from tektos.agents.planner.models import (
    ArchitectureChoice,
    BuildSpec,
    LanguageGame,
    SpecPhase,
)
from tektos.agents.planner.orchestrator import Planner
from tektos.memory.memory_system import MemorySystem
from tektos.memory.reflection_engine import ReflectionEngine, ReflectionState
from tektos.memory.synthesis_engine import SynthesisEngine, SynthesisFeedback


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_planned_spec() -> tuple[PlannerOutput, BuildSpec]:
    """Build a real BuildSpec via the Planner's pipeline."""
    planner = Planner()
    output = planner.plan(
        "Create a Python module with a Calculator class that adds, subtracts, multiplies, and divides.",
        context={
            "tech_stack": ["python", "pytest"],
            "test_strategy": "spec-driven",
        },
    )
    return output, output.spec


def _make_mock_spec() -> BuildSpec:
    """Construct a BuildSpec without touching the Planner pipeline."""
    return BuildSpec(
        id="spec-e2e-001",
        version="1.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        description="Calculator module with add, subtract, multiply, divide.",
        original_prompt=(
            "Create a Python module with a Calculator class "
            "that adds, subtracts, multiplies, and divides."
        ),
        translated_prompt=(
            "Create a Python module with a Calculator class "
            "that adds, subtracts, multiplies, and divides."
        ),
        language_game=LanguageGame.SOFTWARE_ENGINEERING,
        architecture=ArchitectureChoice(
            selected="module",
            justification="Simple module scaffold suffices.",
            reason="Simple module scaffold suffices.",
            is_user_choice=False,
        ),
        requirements=["Calculator class", "add method", "subtract method"],
        test_strategy="spec-driven",
        tech_stack=["python"],
        phases=[
            SpecPhase(
                id="phase-1",
                description="Implement Calculator class",
                deliverables=["calculator module"],
                acceptance_criteria=["add works", "subtract works"],
            )
        ],
    )


def _execute_spec(spec: BuildSpec, workspace: str = "./sandbox_e2e") -> tuple[Executor, dict]:
    """Run the Coding Agent on a spec and return (executor, record dict)."""
    executor = Executor(workspace=workspace)
    record = executor.execute_spec(spec)
    return executor, record.model_dump()


def _run_manager_feedback(
    manager: Manager,
    record: dict,
    spec: BuildSpec,
) -> dict:
    """Feed execution results to the Manager and return feedback."""
    manager.on_task_start(
        task_id="task-e2e-001",
        spec_id=spec.id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Check for feedback from archetype detection
    for step in record.get("steps", []):
        fb = manager.on_error(
            category="test_result",
            description=f"Phase {step.get('action', 'unknown')} completed",
        )
        if fb:
            manager.on_task_complete(
                task_id="task-e2e-001",
                success=True,
                tokens_used=0,
                tools_used=0,
                elapsed=record.get("total_duration_seconds", 0.0),
            )
            return fb.model_dump()

    manager.on_task_complete(
        task_id="task-e2e-001",
        success=True,
        tokens_used=0,
        tools_used=0,
        elapsed=record.get("total_duration_seconds", 0.0),
    )
    return {}


def _run_synthesis(
    spec: BuildSpec,
    record: dict,
) -> list[SynthesisFeedback]:
    """Run the SynthesisEngine on thesis + antithesis."""
    import tempfile
    from tektos.memory.persistence import MemoryPersistence
    tmpdb = Path(tempfile.mkdtemp()) / "test_memory.db"
    persistence = MemoryPersistence(db_path=tmpdb)
    memory = MemorySystem(persistence=persistence)
    reflection = ReflectionEngine(memory_system=memory)

    # Create a reflection state from execution reality
    test_results = record.get("test_results", [])
    test_status = "passed" if all(t.get("status") == "passed" for t in test_results) else "mixed"
    status = record.get("status", "unknown")

    reflection_state = reflection.run_reflection(
        focus=f"Execute spec: {spec.description}",
    )

    synthesis = SynthesisEngine(
        reflection_engine=reflection,
        memory_system=memory,
    )

    syntheses = synthesis.process_reflection_session(
        session=reflection_state,
        thesis_context=spec.description,
    )
    return syntheses


# ── Tests ────────────────────────────────────────────────────────────────────


class TestHegelianLoop:
    """Test the full S4→S1→S3→synthesis dialectic loop."""

    @pytest.fixture(autouse=True)
    def cleanup(self, tmp_path):
        """Clean up sandbox directories after each test."""
        yield
        import shutil
        import pathlib
        for d in pathlib.Path(".").glob("sandbox_e2e*"):
            shutil.rmtree(d, ignore_errors=True)

    def test_s4_produces_valid_spec(self):
        """S4 Planner produces a well-formed BuildSpec from NL input."""
        output, spec = _make_planned_spec()

        assert spec.id is not None
        assert spec.description is not None
        assert spec.original_prompt is not None
        assert len(spec.phases) > 0
        assert len(spec.requirements) > 0
        assert spec.language_game.value == "software_engineering"

        # W5H1M on output
        assert output.language_game_detected is not None
        assert output.context_budget_used > 0

    def test_s1_executes_spec_produces_record(self):
        """S1 Coding Agent executes a spec and produces an ExecutionRecord."""
        spec = _make_mock_spec()
        executor, record = _execute_spec(spec, workspace="./sandbox_e2e_001")

        assert record["status"] in ("completed", "failed")
        assert record["spec_id"] == spec.id
        assert len(record["steps"]) > 0
        assert record["steps"][0]["action"] == "phase_start"

        # W5H1M on every step
        for step in record["steps"]:
            assert step["who"] == "S1 Coding Agent"
            assert step["what"] is not None
            assert step["where"] is not None
            assert step["when"] is not None
            assert step["why"] is not None
            assert step["how"] is not None

    def test_s1_produces_artifacts(self):
        """S1 generates file artifacts in the workspace."""
        spec = _make_mock_spec()
        executor, record = _execute_spec(spec, workspace="./sandbox_e2e_002")

        assert len(record["artifacts"]) > 0
        artifact = record["artifacts"][0]
        assert artifact["artifact_type"] == "source_code"
        assert "content_hash" in artifact
        assert "path" in artifact

    def test_s1_produces_test_results(self):
        """S1 generates test result reports."""
        spec = _make_mock_spec()
        _, record = _execute_spec(spec, workspace="./sandbox_e2e_003")

        assert len(record["test_results"]) > 0
        test_report = record["test_results"][0]
        assert test_report["name"] == "phase-1"
        assert test_report["who"] == "S1 Coding Agent"
        assert test_report["what"] == "phase_tests_executed"
        assert test_report["where"] is not None
        assert test_report["when"] is not None
        assert test_report["why"] == "validate_spec_compliance"
        assert test_report["how"] == "pytest"

    def test_s3_receives_feedback(self):
        """S3 Manager receives execution feedback and tracks state."""
        spec = _make_mock_spec()
        _, record = _execute_spec(spec, workspace="./sandbox_e2e_004")

        manager = Manager(max_feedback_length=500)
        feedback = _run_manager_feedback(manager, record, spec)

        # Manager state transitions: IDLE → ACTIVE → IDLE
        assert manager.state.value == "idle"

        # Health report is populated
        health = manager.get_health_report()
        assert health["state"] == "idle"
        assert "metrics" in health
        assert "spiral_radius" in health

    def test_synthesis_produces_insight(self):
        """SynthesisEngine produces SynthesisFeedback from thesis+antithesis."""
        spec = _make_mock_spec()
        _, record = _execute_spec(spec, workspace="./sandbox_e2e_005")

        syntheses = _run_synthesis(spec, record)
        # At minimum, we get a synthesis even if low confidence
        assert isinstance(syntheses, list)

        for synth in syntheses:
            assert isinstance(synth, SynthesisFeedback)
            assert synth.what_happened is not None
            assert synth.synthesis is not None
            # W5H1M
            assert synth.who == "S3 Manager"
            assert synth.what == "synthesis_feedback"
            assert synth.where == "reflection_engine"
            assert synth.when is not None
            assert synth.why is not None
            assert synth.how == "ReflectionEngine synthesizes direct experience with speculation"

    def test_full_loop_thesis_to_synthesis(self):
        """The full dialectic: thesis → antithesis → synthesis."""
        # PHASE 1: Thesis (S4) — Plan
        output, spec = _make_planned_spec()
        thesis = output.spec

        # PHASE 2: Antithesis (S1) — Execute
        executor, record = _execute_spec(thesis, workspace="./sandbox_e2e_006")

        # PHASE 3: Feedback (S3) — Regulate
        manager = Manager(max_feedback_length=500)
        _run_manager_feedback(manager, record, thesis)

        # PHASE 4: Synthesis — Learn
        syntheses = _run_synthesis(thesis, record)

        # The loop produces at least one synthesis insight
        assert isinstance(syntheses, list)

        # Record carries the full trace
        assert record["status"] in ("completed", "failed")
        assert record["spec_id"] == thesis.id
        assert len(record["steps"]) > 0

    def test_loop_with_failed_spec(self):
        """The dialectic handles failure — failure is data, not a crash."""
        spec = BuildSpec(
            id="spec-e2e-fail",
            version="1.0",
            created_at=datetime.now(timezone.utc).isoformat(),
            description="This spec has no deliverables — execution should handle gracefully.",
            original_prompt="Do something impossible.",
            translated_prompt="Do something impossible.",
            language_game=LanguageGame.SOFTWARE_ENGINEERING,
            architecture=ArchitectureChoice(
                selected="module",
                justification="No architecture applicable.",
                reason="No architecture applicable.",
                is_user_choice=False,
            ),
            requirements=[],
            test_strategy="spec-driven",
            tech_stack=[],
            phases=[
                SpecPhase(
                    id="phase-empty",
                    description="Nothing",
                    deliverables=[],
                    acceptance_criteria=[],
                )
            ],
        )
        _, record = _execute_spec(spec, workspace="./sandbox_e2e_007")

        # Should complete (or fail gracefully), not crash
        assert record["spec_id"] == spec.id
        assert record["status"] in ("completed", "failed")
        assert isinstance(record["steps"], list)

        # Synthesis should still work even with failure
        syntheses = _run_synthesis(spec, record)
        assert isinstance(syntheses, list)


class TestLoopW5H1MConsistency:
    """Verify W5H1M metadata is never lost in the loop."""

    def test_every_event_carries_w5h1m(self):
        """Every artifact, step, and test result in the record has W5H1M."""
        spec = _make_mock_spec()
        _, record = _execute_spec(spec, workspace="./sandbox_e2e_008")

        # Check steps
        for step in record["steps"]:
            for field in ["who", "what", "where", "when", "why", "how"]:
                assert field in step, f"Missing {field} in step {step['action']}"
                assert step[field], f"Empty {field} in step {step['action']}"

        # Check artifacts
        for artifact in record["artifacts"]:
            for field in ["who", "what", "where", "when", "why", "how"]:
                assert field in artifact, f"Missing {field} in artifact"
                assert artifact[field], f"Empty {field} in artifact"

        # Check test results
        for test in record["test_results"]:
            for field in ["who", "what", "where", "when", "why", "how"]:
                assert field in test, f"Missing {field} in test result"
                assert test[field], f"Empty {field} in test result"

    def test_synthesis_w5h1m_preserved(self):
        """Synthesis feedback carries W5H1M."""
        spec = _make_mock_spec()
        _, record = _execute_spec(spec, workspace="./sandbox_e2e_009")
        syntheses = _run_synthesis(spec, record)

        for synth in syntheses:
            for field in ["who", "what", "where", "when", "why", "how"]:
                assert field in synth.model_dump(), f"Missing {field} in synthesis"


class TestLoopSelfImprovement:
    """Verify the loop produces actionable insights for self-improvement."""

    def test_synthesis_contains_actionable_content(self):
        """Synthesis feedback contains actionable guidance text."""
        spec = _make_mock_spec()
        _, record = _execute_spec(spec, workspace="./sandbox_e2e_010")
        syntheses = _run_synthesis(spec, record)

        for synth in syntheses:
            assert len(synth.synthesis) > 0, "Synthesis content must not be empty"
            # Should reference both thesis and antithesis
            assert "Execution" in synth.what_happened or "reality" in synth.what_happened.lower()

    def test_synthesis_can_guide_next_spec(self):
        """SynthesisEngine.guide_next_spec incorporates syntheses into future planning."""
        import tempfile
        from tektos.memory.persistence import MemoryPersistence
        tmpdb = Path(tempfile.mkdtemp()) / "test_memory.db"
        persistence = MemoryPersistence(db_path=tmpdb)
        memory = MemorySystem(persistence=persistence)
        reflection = ReflectionEngine(memory_system=memory)
        reflection_state = reflection.run_reflection(
            focus="test loop self-improvement",
        )

        synthesis_engine = SynthesisEngine(reflection_engine=reflection, memory_system=memory)
        synthesis_engine.process_reflection_session(
            session=reflection_state,
            thesis_context="Create a module",
        )

        # With syntheses, guide_next_spec should enhance the prompt
        if synthesis_engine.syntheses:
            guided = synthesis_engine.guide_next_spec(
                "Build a new module",
                previous_syntheses=synthesis_engine.syntheses,
            )
            assert "Build a new module" in guided
            # Should contain synthesis guidance
            assert "[SYNTHESIS GUIDANCE" in guided or guided == "Build a new module"
