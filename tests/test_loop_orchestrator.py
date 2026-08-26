"""Tests for LoopCycle and SelfImprovementLoop."""

import pytest
import tempfile

from tektos.agents.self_improvement.loop_orchestrator import LoopCycle, SelfImprovementLoop
from tektos.agents.planner.models import BuildSpec, ArchitectureChoice
from tektos.memory.synthesis_engine import SynthesisFeedback


class TestLoopCycle:
    def test_defaults(self):
        cycle = LoopCycle(
            cycle_id="cycle-1",
            timestamp_start="2025-01-01T00:00:00+00:00",
            prompt="Build a module",
        )
        assert cycle.cycle_id == "cycle-1"
        assert cycle.timestamp_start == "2025-01-01T00:00:00+00:00"
        assert cycle.timestamp_end is None
        assert cycle.status == "pending"
        assert cycle.prompt == "Build a module"
        assert cycle.spec is None
        assert cycle.execution_result is None
        assert cycle.manager_feedback is None
        assert cycle.syntheses == []
        assert cycle.experience_stored == []
        assert cycle.error is None

    def test_duration_seconds(self):
        cycle = LoopCycle(
            cycle_id="cycle-1",
            timestamp_start="2025-01-01T00:00:00+00:00",
            timestamp_end="2025-01-01T00:01:00+00:00",
            prompt="Build a module",
        )
        assert cycle.duration_seconds == 60.0

    def test_duration_seconds_no_end(self):
        cycle = LoopCycle(
            cycle_id="cycle-1",
            timestamp_start="2025-01-01T00:00:00+00:00",
            prompt="Build a module",
        )
        assert cycle.duration_seconds is None

    def test_with_data(self):
        spec = BuildSpec(
            id="spec-1",
            description="Test",
            original_prompt="test",
            translated_prompt="test",
            requirements=["test"],
            architecture=ArchitectureChoice(selected="simple", reason="simple", is_user_choice=True),
            phases=[],
        )
        synth = SynthesisFeedback(
            insight_type="test",
            what_happened="test",
            synthesis="test",
            is_actionable=True,
        )
        cycle = LoopCycle(
            cycle_id="cycle-1",
            timestamp_start="2025-01-01T00:00:00+00:00",
            timestamp_end="2025-01-01T00:01:00+00:00",
            prompt="Build a module",
            spec=spec,
            status="complete",
            execution_result={"status": "ok"},
            manager_feedback={"type": "info"},
            syntheses=[synth],
            experience_stored=["exp-1"],
            error=None,
        )
        assert cycle.spec == spec
        assert cycle.status == "complete"
        assert cycle.execution_result == {"status": "ok"}
        assert cycle.manager_feedback == {"type": "info"}
        assert len(cycle.syntheses) == 1
        assert cycle.syntheses[0].synthesis == "test"
        assert cycle.experience_stored == ["exp-1"]


class TestSelfImprovementLoop:
    def test_init(self):
        loop = SelfImprovementLoop()
        assert loop.planner is not None
        assert loop.executor is not None
        assert loop.manager is not None
        assert len(loop._cycles) == 0

    def test_init_custom_params(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = SelfImprovementLoop(
                max_cycles=5,
                workspace=tmpdir,
                max_feedback_length=1000,
                experience_replay_max=25,
            )
            assert loop._max_cycles == 5

    def test_run_single_cycle(self):
        loop = SelfImprovementLoop()
        cycle = loop.run("Build a simple module")
        assert cycle.cycle_id is not None
        assert cycle.prompt == "Build a simple module"
        assert cycle.status in ("complete", "failed")
        assert len(loop._cycles) == 1

    def test_run_multiple_cycles(self):
        loop = SelfImprovementLoop()
        cycle1 = loop.run("Build module A")
        cycle2 = loop.run("Build module B")
        assert len(loop._cycles) == 2
        assert cycle1.cycle_id != cycle2.cycle_id

    def test_max_cycles_reached(self):
        loop = SelfImprovementLoop(max_cycles=2)
        loop.run("Build module A")
        loop.run("Build module B")
        with pytest.raises(RuntimeError, match="Maximum cycles"):
            loop.run("Build module C")

    def test_run_multiple_prompts(self):
        loop = SelfImprovementLoop()
        results = loop.run_multiple(["Build A", "Build B", "Build C"])
        assert len(results) == 3
        for r in results:
            assert r.cycle_id is not None

    def test_get_loop_health(self):
        loop = SelfImprovementLoop()
        loop.run("Build module")
        health = loop.get_loop_health()
        assert health["total_cycles"] == 1
        assert health["completed"] >= 0
        assert health["failed"] >= 0
        assert "success_rate" in health
        assert "total_syntheses" in health
        assert "total_experiences_stored" in health
        assert "experience_replay_health" in health
        assert "synthesis_engine_health" in health
        assert "recent_cycles" in health

    def test_clear_cycles(self):
        loop = SelfImprovementLoop()
        loop.run("Build module")
        assert len(loop._cycles) == 1
        loop.clear_cycles()
        assert len(loop._cycles) == 0

    def test_len(self):
        loop = SelfImprovementLoop()
        assert len(loop) == 0
        loop.run("Build module")
        assert len(loop) == 1

    def test_cycle_with_synthesis_guidance(self):
        loop = SelfImprovementLoop()
        cycle = loop.run("Build module", synthesis_guidance="Use pytest")
        assert cycle.prompt == "Build module"

    def test_cycle_with_custom_cycle_id(self):
        loop = SelfImprovementLoop()
        cycle = loop.run("Build module", cycle_id="custom-cycle")
        assert cycle.cycle_id == "custom-cycle"

    def test_cycle_with_context(self):
        loop = SelfImprovementLoop()
        cycle = loop.run("Build module", context={"tech_stack": ["python"]})
        assert cycle.prompt == "Build module"

    def test_health_after_multiple_cycles(self):
        loop = SelfImprovementLoop()
        loop.run_multiple(["Build A", "Build B"])
        health = loop.get_loop_health()
        assert health["total_cycles"] == 2
        assert health["recent_cycles"]  # last 5 cycles

    def test_health_after_clear(self):
        loop = SelfImprovementLoop()
        loop.run("Build module")
        loop.clear_cycles()
        health = loop.get_loop_health()
        assert health["total_cycles"] == 0
        assert health["completed"] == 0
        assert health["failed"] == 0
