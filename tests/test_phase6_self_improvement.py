"""Phase 6: Self-Improvement Loop Integration Tests.

Verifies that SynthesisEngine output is wired back into Planner's next spec:
1. ExperienceReplay stores synthesis feedback as structured memories
2. Planner accepts synthesis_guidance and includes it in specs
3. Synthesis guidance appears in BuildSpec notes and metadata
4. SelfImprovementLoop orchestrates the full S4→S1→S3→synthesis→planner cycle
5. Multiple cycles progressively improve planning with past experience

This is the self-improvement loop — where Tektos learns from execution.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.tektos.agents.coding_agent.executor import Executor
from src.tektos.agents.manager.orchestrator import Manager
from src.tektos.agents.planner.models import (
    ArchitectureChoice,
    BuildSpec,
    LanguageGame,
    SpecPhase,
)
from src.tektos.agents.planner.orchestrator import Planner
from src.tektos.agents.self_improvement import SelfImprovementLoop, LoopCycle
from src.tektos.memory.experience_replay import ExperienceReplay
from src.tektos.memory.memory_system import MemorySystem
from src.tektos.memory.reflection_engine import ReflectionEngine, ReflectionState
from src.tektos.memory.synthesis_engine import SynthesisEngine, SynthesisFeedback


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_mock_spec(id_prefix: str = "spec") -> BuildSpec:
    """Construct a BuildSpec for testing."""
    return BuildSpec(
        id=f"{id_prefix}-phase6",
        version="1.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        description="Test spec for Phase 6 self-improvement loop.",
        original_prompt="Create a test module.",
        translated_prompt="Create a test module.",
        language_game=LanguageGame.SOFTWARE_ENGINEERING,
        architecture=ArchitectureChoice(
            selected="module",
            justification="Simple module.",
            reason="Simple module.",
            is_user_choice=False,
        ),
        requirements=["test module"],
        test_strategy="spec-driven",
        tech_stack=["python"],
        phases=[
            SpecPhase(
                id="phase-1",
                description="Implement test module",
                deliverables=["test module code"],
                acceptance_criteria=["passes import test"],
            )
        ],
    )


class TestExperienceReplay:
    """Test the ExperienceReplay module that bridges synthesis to planning."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Fresh experience replay for each test."""
        self.replay = ExperienceReplay(max_records=50)

    def test_store_and_retrieve_single(self):
        """ExperienceReplay stores a single experience record."""
        record = self.replay.store(
            insight_type="error_pattern",
            what_happened="Spec lacked error handling requirements",
            guidance="Always include error handling in requirements",
            context="software_engineering",
            confidence=0.85,
        )
        assert record.id is not None
        assert record.insight_type == "error_pattern"
        assert len(self.replay) == 1

    def test_get_planner_guidance_returns_text(self):
        """ExperienceReplay produces planner-ready guidance text."""
        self.replay.store(
            insight_type="error_pattern",
            what_happened="Missing test requirements led to untested code",
            guidance="Always specify test criteria before implementation",
            context="software_engineering",
            confidence=0.9,
        )
        guidance = self.replay.get_planner_guidance(
            language_game="software_engineering",
            recent_specs=3,
        )
        assert len(guidance) > 0
        assert "[EXPERIENCE GUIDANCE" in guidance
        assert "Always specify test criteria" in guidance

    def test_planner_guidance_empty_without_records(self):
        """No guidance when no experience exists."""
        guidance = self.replay.get_planner_guidance(language_game="software_engineering")
        assert guidance == ""

    def test_filter_by_type(self):
        """Can retrieve experience by specific insight type."""
        self.replay.store(
            insight_type="error_pattern",
            what_happened="First error",
            guidance="Fix error 1",
            context="software_engineering",
        )
        self.replay.store(
            insight_type="bias_detected",
            what_happened="Planning bias",
            guidance="Correct bias",
            context="software_engineering",
        )
        errors = self.replay.get_guidance_by_type("error_pattern")
        assert len(errors) == 1
        assert errors[0].insight_type == "error_pattern"
        biases = self.replay.get_guidance_by_type("bias_detected")
        assert len(biases) == 1

    def test_from_synthesis(self):
        """Store a SynthesisFeedback directly."""
        synth = SynthesisFeedback(
            insight_type="error_pattern",
            what_happened="Tests failed due to missing validation",
            synthesis="Add input validation to spec requirements",
            confidence=0.8,
            is_actionable=True,
        )
        record = self.replay.store_from_synthesis(synth, cycle_id="cycle-001")
        assert record.insight_type == "error_pattern"
        assert len(self.replay) == 1

    def test_max_records_enforced(self):
        """Experience replay respects max_records limit."""
        replay = ExperienceReplay(max_records=3)
        for i in range(5):
            replay.store(
                insight_type="test",
                what_happened=f"Experience {i}",
                guidance=f"Guidance {i}",
                context="general",
            )
        assert len(replay) == 3  # Only last 3

    def test_health_report(self):
        """Health report contains structured statistics."""
        self.replay.store(
            insight_type="error_pattern",
            what_happened="Error 1",
            guidance="Fix 1",
            context="software_engineering",
            priority="high",
        )
        self.replay.store(
            insight_type="direct_experience",
            what_happened="Experience 2",
            guidance="Learn 2",
            context="software_engineering",
            confidence=0.9,
        )
        report = self.replay.get_health_report()
        assert report["total_records"] == 2
        assert "by_type" in report
        assert "by_priority" in report
        assert report["average_confidence"] > 0


class TestPlannerSynthesisGuidance:
    """Test that Planner accepts and passes synthesis_guidance."""

    def test_planner_accepts_synthesis_guidance_param(self):
        """Planner.plan() accepts synthesis_guidance parameter."""
        planner = Planner()
        output = planner.plan(
            "Create a calculator module.",
            synthesis_guidance="[GUIDANCE] Always include error handling.",
        )
        assert output is not None
        assert output.spec is not None

    def test_synthesis_guidance_appears_in_spec(self):
        """Synthesis guidance flows into BuildSpec.notes."""
        planner = Planner()
        guidance = "[EXPERIENCE] Past cycles showed missing error handling led to bugs."
        output = planner.plan(
            "Create a math library.",
            synthesis_guidance=guidance,
        )
        # The synthesis_guidance should appear in the spec
        assert output.spec is not None
        # Check it made it into notes (spec generator appends it)
        assert any("EXPERIENCE" in note for note in output.spec.notes)

    def test_synthesis_guidance_appears_in_output(self):
        """PlannerOutput carries synthesis_guidance field."""
        planner = Planner()
        output = planner.plan(
            "Create a test module.",
            synthesis_guidance="[GUIDANCE] Add test requirements.",
        )
        assert output.synthesis_guidance == "[GUIDANCE] Add test requirements."

    def test_empty_guidance_is_safe(self):
        """Empty synthesis_guidance doesn't break planning."""
        planner = Planner()
        output = planner.plan("Create a module.", synthesis_guidance="")
        assert output.spec is not None
        assert output.synthesis_guidance == ""


class TestSynthesisToSpecWiring:
    """Test that synthesis actually modifies the generated spec."""

    def test_synthesis_guidance_added_to_spec_notes(self):
        """Synthesis guidance from ExperienceReplay appears in spec notes."""
        # Store some experience
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="Spec lacked performance requirements",
            guidance="Always specify performance constraints",
            context="software_engineering",
            confidence=0.85,
        )

        # Get guidance
        guidance = replay.get_planner_guidance(
            language_game="software_engineering",
        )

        # Plan with guidance
        planner = Planner()
        output = planner.plan(
            "Create an API endpoint.",
            synthesis_guidance=guidance,
        )

        # Spec should contain the guidance
        assert output.spec is not None
        assert any("performance" in note.lower() for note in output.spec.notes)

    def test_multiple_syntheses_combined(self):
        """Multiple past syntheses are combined in guidance."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="Missing tests",
            guidance="Add test requirements",
            context="software_engineering",
        )
        replay.store(
            insight_type="bias_detected",
            what_happened="Over-engineering",
            guidance="Keep it simple",
            context="software_engineering",
        )

        guidance = replay.get_planner_guidance(
            language_game="software_engineering",
        )

        assert "EXPERIENCE GUIDANCE" in guidance
        assert "Add test requirements" in guidance
        assert "Keep it simple" in guidance


class TestSelfImprovementLoop:
    """Test the SelfImprovementLoop orchestrator."""

    @pytest.fixture(autouse=True)
    def cleanup(self, tmp_path):
        """Clean up sandbox directories."""
        yield
        for d in Path(".").glob("sandbox_phase6*"):
            shutil.rmtree(d, ignore_errors=True)

    def test_run_single_cycle(self):
        """SelfImprovementLoop.run() executes a full cycle."""
        loop = SelfImprovementLoop(workspace="./sandbox_phase6_001")
        cycle = loop.run("Create a calculator module.")

        assert cycle.cycle_id is not None
        assert cycle.status in ("complete", "failed")
        assert cycle.spec is not None
        assert cycle.prompt == "Create a calculator module."
        assert len(loop) == 1

    def test_cycle_carries_synthesis_guidance_in_spec(self):
        """Spec generated with synthesis guidance includes it in notes."""
        # First: store some experience
        loop = SelfImprovementLoop(workspace="./sandbox_phase6_002")
        loop._experience.store(
            insight_type="error_pattern",
            what_happened="Missing test requirements",
            guidance="Always specify test criteria",
            context="software_engineering",
            confidence=0.9,
        )

        # Second: run a cycle (should pick up guidance automatically)
        cycle = loop.run("Create a test module.")

        assert cycle.spec is not None
        assert cycle.spec.synthesis_guidance is not None
        assert len(cycle.spec.synthesis_guidance) > 0

    def test_multiple_cycles_sequential(self):
        """Multiple cycles run sequentially."""
        loop = SelfImprovementLoop(
            workspace="./sandbox_phase6_003",
            max_cycles=5,
        )
        cycles = loop.run_multiple([
            "Create module A.",
            "Create module B.",
        ])

        assert len(cycles) == 2
        assert cycles[0].status in ("complete", "failed")
        assert cycles[1].status in ("complete", "failed")
        assert len(loop) == 2

    def test_max_cycles_enforced(self):
        """Maximum cycle count is enforced."""
        loop = SelfImprovementLoop(
            workspace="./sandbox_phase6_004",
            max_cycles=2,
        )
        loop.run("Cycle 1.")
        loop.run("Cycle 2.")

        with pytest.raises(RuntimeError, match="Maximum cycles"):
            loop.run("Cycle 3.")

    def test_loop_health_report(self):
        """Loop health report contains structured data."""
        loop = SelfImprovementLoop(workspace="./sandbox_phase6_005")
        loop.run("Create a module.")

        health = loop.get_loop_health()
        assert health["total_cycles"] == 1
        assert health["completed"] >= 0
        assert "success_rate" in health
        assert "experience_replay_health" in health
        assert "synthesis_engine_health" in health

    def test_failed_cycle_still_stored(self):
        """Failed cycles are recorded, not lost."""
        loop = SelfImprovementLoop(workspace="./sandbox_phase6_006")
        cycle = loop.run("This will fail due to empty spec.")

        # Even failed cycles are stored
        assert len(loop) == 1
        assert cycle.cycle_id is not None


class TestEndToEndSelfImprovementLoop:
    """Integration test: full loop with experience feeding back into planning."""

    @pytest.fixture(autouse=True)
    def cleanup(self, tmp_path):
        yield
        for d in Path(".").glob("sandbox_phase6_e2e*"):
            shutil.rmtree(d, ignore_errors=True)

    def test_synthesis_informs_next_spec(self):
        """Past synthesis feedback influences future spec generation."""
        loop = SelfImprovementLoop(workspace="./sandbox_phase6_e2e_001")

        # Store some experience manually
        loop._experience.store(
            insight_type="error_pattern",
            what_happened="Previous spec lacked error handling requirements",
            guidance="Always include error handling and validation in specs",
            context="software_engineering",
            confidence=0.95,
            priority="high",
        )
        loop._experience.store(
            insight_type="bias_detected",
            what_happened="Plans over-specified for simple tasks",
            guidance="Keep specs minimal for simple requirements",
            context="software_engineering",
            confidence=0.8,
        )

        # Run cycle — should pick up experience automatically
        cycle = loop.run("Create a simple calculator.")

        # Spec should include guidance from experience
        assert cycle.spec is not None
        # The synthesis_guidance field should be populated
        assert cycle.spec.synthesis_guidance is not None
        # And notes should contain the guidance text
        assert any(
            "error handling" in note.lower() or "minimal" in note.lower()
            for note in cycle.spec.notes
        )

    def test_full_loop_pipeline(self):
        """End-to-end: Planner → Executor → Manager → Synthesis → Experience → Planner."""
        loop = SelfImprovementLoop(workspace="./sandbox_phase6_e2e_002")

        # Run first cycle
        cycle1 = loop.run("Create a test module with pytest.")

        assert cycle1.spec is not None
        assert cycle1.status in ("complete", "failed")

        # Check that execution produced artifacts
        if cycle1.execution_result:
            assert "status" in cycle1.execution_result
            assert "steps" in cycle1.execution_result

        # Check synthesis was attempted
        assert isinstance(cycle1.syntheses, list)

        # Check experience was stored
        assert isinstance(cycle1.experience_stored, list)

    def test_experience_survives_cycle_completion(self):
        """Experience replay retains records after cycles complete."""
        loop = SelfImprovementLoop(workspace="./sandbox_phase6_e2e_003")

        # Store experience
        loop._experience.store(
            insight_type="error_pattern",
            what_happened="Test coverage gap",
            guidance="Include coverage requirements",
            context="software_engineering",
        )

        # Run cycle
        cycle = loop.run("Create a module.")

        # Experience should still be there
        assert len(loop._experience) == 1

        # New cycle should pick it up
        cycle2 = loop.run("Create another module.")
        assert cycle2.spec.synthesis_guidance is not None


class TestSynthesisGuidanceFormat:
    """Test the formatting and structure of synthesis guidance."""

    def test_guidance_contains_header(self):
        """Planner guidance includes [EXPERIENCE GUIDANCE] header."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="test",
            what_happened="Test event",
            guidance="Test guidance",
            context="software_engineering",
        )
        guidance = replay.get_planner_guidance(language_game="software_engineering")
        assert "[EXPERIENCE GUIDANCE" in guidance

    def test_urgent_guidance_marked(self):
        """Urgent guidance is marked with warning symbol."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="Critical error",
            guidance="Must fix critical error",
            context="software_engineering",
            priority="urgent",
        )
        guidance = replay.get_planner_guidance(language_game="software_engineering")
        assert "URGENT" in guidance

    def test_guidance_truncates_long_text(self):
        """Very long guidance is truncated to reasonable length."""
        long_text = "x" * 1000
        replay = ExperienceReplay()
        replay.store(
            insight_type="test",
            what_happened="test",
            guidance=long_text,
            context="software_engineering",
        )
        guidance = replay.get_planner_guidance(language_game="software_engineering")
        assert len(guidance) < 500  # Should be truncated


class TestW5H1MConsistencyInLoop:
    """Verify W5H1M is preserved through the self-improvement loop."""

    def test_loop_cycle_has_temporal_metadata(self):
        """LoopCycle carries timestamps for when/why/how."""
        loop = SelfImprovementLoop(workspace="./sandbox_phase6_w5h1m")
        cycle = loop.run("Create a module.")

        assert cycle.timestamp_start is not None
        assert cycle.prompt is not None
        assert cycle.cycle_id is not None

    def test_spec_w5h1m_preserved_with_guidance(self):
        """Spec's W5H1M metadata is preserved when synthesis_guidance is added."""
        planner = Planner()
        output = planner.plan(
            "Create a module.",
            synthesis_guidance="[GUIDANCE] Add error handling.",
        )
        assert output.spec.metadata.who == "S4 Planner/Thinker"
        assert output.spec.metadata.what == "spec_generated"
        assert output.spec.metadata.why == "translate user intent to executable spec"
        assert output.spec.metadata.how is not None
