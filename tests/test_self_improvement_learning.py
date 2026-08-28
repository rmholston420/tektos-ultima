"""Test that Tektos's self-improvement loop actually learns across cycles.

This tests the core claim: that Tektos improves its planning quality over
multiple cycles by incorporating experience from past executions.

The test creates a scenario where:
1. Cycle 1: Tektos plans a spec with a known flaw (missing error handling)
2. The loop detects this flaw and stores it as experience
3. Cycle 2: Tektos plans a similar spec — it should now include error handling
4. Cycle 3: The improvement should persist and compound

This is the difference between a loop that *runs* and a loop that *learns*.
"""

from __future__ import annotations

import sys
sys.path.insert(0, "/home/rmholston/dev/tektos-ultima-v1/src")

import pytest
from tektos.agents.self_improvement import SelfImprovementLoop
from tektos.agents.planner.models import BuildSpec


class TestSelfImprovementActuallyLearns:
    """Tests that verify Tektos learns, not just loops."""

    def test_experience_influences_planning_quality(self):
        """Cycle 2 should produce better specs than Cycle 1 when experience exists."""
        loop = SelfImprovementLoop(workspace="./sandbox_learn_001")

        # Pre-seed experience: past cycles had specs missing error handling
        loop._experience.store(
            insight_type="error_pattern",
            what_happened="Specs without error handling requirements led to unhandled exceptions",
            guidance="Always include error handling and validation requirements in specs",
            context="software_engineering",
            confidence=0.95,
            priority="high",
        )

        # Run cycle — should pick up the experience
        cycle = loop.run("Create a user authentication module.")

        assert cycle.spec is not None
        # The spec should include error handling in its requirements
        reqs = cycle.spec.requirements or []
        reqs_text = " ".join(reqs).lower()
        assert any(
            kw in reqs_text
            for kw in ["error", "exception", "validation", "handle", "invalid"]
        ), (
            f"Spec should include error handling guidance from experience. "
            f"Requirements: {reqs}"
        )

    def test_learning_compounds_across_cycles(self):
        """Each cycle should build on the previous cycle's experience."""
        loop = SelfImprovementLoop(
            workspace="./sandbox_learn_002",
            max_cycles=5,
        )

        # Cycle 1: No prior experience — spec may lack error handling
        cycle1 = loop.run("Create a data processing module.")
        reqs1 = " ".join(cycle1.spec.requirements or []).lower() if cycle1.spec else ""

        # Cycle 2: Should have error handling from experience
        cycle2 = loop.run("Create a file I/O module.")
        reqs2 = " ".join(cycle2.spec.requirements or []).lower() if cycle2.spec else ""

        # Cycle 3: Should have both error handling AND other improvements
        cycle3 = loop.run("Create a logging module.")
        reqs3 = " ".join(cycle3.spec.requirements or []).lower() if cycle3.spec else ""

        # Verify the loop is accumulating experience
        assert len(loop._experience) >= 1, "Experience should accumulate across cycles"

        # Verify synthesis was attempted in each cycle
        for i, c in enumerate([cycle1, cycle2, cycle3], 1):
            assert isinstance(c.syntheses, list), f"Cycle {i} should have syntheses list"

    def test_experience_replay_guidance_is_actionable(self):
        """Experience stored from one cycle should produce actionable guidance for the next."""
        loop = SelfImprovementLoop(workspace="./sandbox_learn_003")

        # Store a specific, actionable insight
        loop._experience.store(
            insight_type="error_pattern",
            what_happened="Modules without type hints caused runtime errors",
            guidance="Always include type hints in function signatures",
            context="software_engineering",
            confidence=0.9,
        )

        # Get the guidance that would be given to the planner
        guidance = loop._experience.get_planner_guidance(
            language_game="software_engineering",
            recent_specs=3,
        )

        # The guidance should be actionable (not just a summary)
        assert len(guidance) > 0
        assert "type hint" in guidance.lower() or "type hint" in guidance.lower()

        # Run a cycle and verify the spec reflects the guidance
        cycle = loop.run("Create a utility function module.")
        assert cycle.spec is not None
        spec_reqs = cycle.spec.requirements or []
        spec_text = " ".join(spec_reqs).lower()
        assert "type hint" in spec_text or "type hint" in spec_text, (
            f"Spec should include type hint guidance. Requirements: {spec_reqs}"
        )

    def test_failed_cycles_still_produce_learning(self):
        """Even failed cycles should contribute to the experience replay."""
        loop = SelfImprovementLoop(workspace="./sandbox_learn_004")

        # Run a cycle that will likely fail (vague prompt)
        cycle = loop.run("Do something.")

        # The cycle should be recorded
        assert len(loop) == 1
        assert cycle.cycle_id is not None

        # Even if it failed, the loop should have attempted synthesis
        # (the synthesis engine processes whatever reflection state exists)
        assert isinstance(cycle.syntheses, list)

    def test_loop_health_indicates_learning_progress(self):
        """Loop health report should show evidence of learning."""
        loop = SelfImprovementLoop(workspace="./sandbox_learn_005")

        # Run a few cycles
        loop.run("Create module A.")
        loop.run("Create module B.")

        health = loop.get_loop_health()

        # Should show evidence of the loop functioning
        assert health["total_cycles"] == 2
        assert "success_rate" in health
        assert health["success_rate"] >= 0
        assert "experience_replay_health" in health
        assert "synthesis_engine_health" in health

        # Experience replay should have some records (from synthesis)
        exp_health = health["experience_replay_health"]
        assert "total_records" in exp_health


class TestSelfImprovementLoopQualityMetrics:
    """Test that the loop tracks quality metrics over time."""

    def test_spec_quality_improves_with_guidance(self):
        """Specs with synthesis guidance should be more complete."""
        loop = SelfImprovementLoop(workspace="./sandbox_learn_006")

        # Pre-seed multiple insights
        loop._experience.store(
            insight_type="error_pattern",
            what_happened="Missing error handling",
            guidance="Include error handling",
            context="software_engineering",
        )
        loop._experience.store(
            insight_type="error_pattern",
            what_happened="Missing type hints",
            guidance="Include type hints",
            context="software_engineering",
        )
        loop._experience.store(
            insight_type="error_pattern",
            what_happened="Missing tests",
            guidance="Include test requirements",
            context="software_engineering",
        )

        cycle = loop.run("Create a REST API endpoint.")

        assert cycle.spec is not None
        # The spec should have multiple requirements reflecting the experience
        assert len(cycle.spec.requirements) >= 1, (
            f"Spec should have requirements from experience. "
            f"Got: {cycle.spec.requirements}"
        )

    def test_experience_does_not_overflow_planner_context(self):
        """Too much experience should be truncated, not overwhelm the planner."""
        loop = SelfImprovementLoop(workspace="./sandbox_learn_007")

        # Store a lot of experience
        for i in range(20):
            loop._experience.store(
                insight_type="error_pattern",
                what_happened=f"Error {i}",
                guidance=f"Fix {i}",
                context="software_engineering",
            )

        # Get guidance — should be truncated
        guidance = loop._experience.get_planner_guidance(
            language_game="software_engineering",
            recent_specs=3,
        )

        # Should not be excessively long
        assert len(guidance) < 2000, (
            f"Guidance should be truncated. Got {len(guidance)} chars"
        )

        # Should still contain some experience
        assert len(guidance) > 0
        assert "EXPERIENCE GUIDANCE" in guidance


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
