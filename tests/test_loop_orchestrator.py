"""
Tektos-Ultima v1 — Self-Improvement Loop Orchestrator Tests

Tests SelfImprovementLoop state machine and lifecycle:
- LoopCycle dataclass (duration, status tracking)
- SelfImprovementLoop.run() — full cycle execution
- SelfImprovementLoop.run_multiple() — sequential cycles
- SelfImprovementLoop.get_loop_health() — health report
- SelfImprovementLoop.clear_cycles()
- Max cycles enforcement
- Error handling (failed cycles)
- Synthesis and experience replay integration
"""

import uuid
from unittest.mock import MagicMock, patch, call

import pytest

from tektos.agents.self_improvement.loop_orchestrator import LoopCycle, SelfImprovementLoop
from src.tektos.memory.synthesis_engine import SynthesisFeedback


# ---------------------------------------------------------------------------
# LoopCycle
# ---------------------------------------------------------------------------


class TestLoopCycle:
    def test_cycle_defaults(self):
        cycle = LoopCycle(
            cycle_id="test-1",
            timestamp_start="2024-01-01T00:00:00+00:00",
            timestamp_end="2024-01-01T00:01:00+00:00",
            prompt="test prompt",
        )
        assert cycle.cycle_id == "test-1"
        assert cycle.status == "pending"
        assert cycle.spec is None
        assert cycle.execution_result is None
        assert cycle.manager_feedback is None
        assert cycle.syntheses == []
        assert cycle.experience_stored == []
        assert cycle.error is None

    def test_duration_seconds(self):
        cycle = LoopCycle(
            cycle_id="test-1",
            timestamp_start="2024-01-01T00:00:00+00:00",
            timestamp_end="2024-01-01T00:01:30+00:00",
            prompt="test",
        )
        assert cycle.duration_seconds == 90.0

    def test_duration_seconds_none_when_no_end(self):
        cycle = LoopCycle(
            cycle_id="test-1",
            timestamp_start="2024-01-01T00:00:00+00:00",
            prompt="test",
        )
        assert cycle.duration_seconds is None

    def test_status_values(self):
        valid_statuses = ["pending", "planning", "executing", "reflecting", "synthesizing", "complete", "failed"]
        for status in valid_statuses:
            cycle = LoopCycle(
                cycle_id="test",
                timestamp_start="2024-01-01T00:00:00+00:00",
                prompt="test",
                status=status,
            )
            assert cycle.status == status


# ---------------------------------------------------------------------------
# SelfImprovementLoop — initialization
# ---------------------------------------------------------------------------


class TestLoopInit:
    def test_init_default_values(self):
        loop = SelfImprovementLoop(max_cycles=5, workspace="/tmp/test", max_feedback_length=300)
        assert loop._max_cycles == 5
        assert loop._workspace == "/tmp/test"
        assert len(loop._cycles) == 0

    def test_init_has_components(self):
        loop = SelfImprovementLoop()
        assert loop.planner is not None
        assert loop.executor is not None
        assert loop.manager is not None

    def test_len(self):
        loop = SelfImprovementLoop()
        assert len(loop) == 0


# ---------------------------------------------------------------------------
# SelfImprovementLoop — run() with mocked components
# ---------------------------------------------------------------------------


class TestLoopRun:
    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_run_successful_cycle(
        self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan
    ):
        # Setup mocks
        mock_spec = MagicMock()
        mock_spec.id = "spec-1"
        mock_spec.description = "test spec"
        
        mock_planner_output = MagicMock()
        mock_planner_output.spec = mock_spec
        mock_plan.return_value.plan.return_value = mock_planner_output
        
        mock_record = MagicMock()
        mock_record.steps = []
        mock_record.status.value = "completed"
        mock_record.total_duration_seconds = 5.0
        mock_record.test_results = []
        mock_exec.return_value.execute_spec.return_value = mock_record
        
        mock_mgr_instance = mock_mgr.return_value
        mock_mgr_instance.on_error.return_value = None
        mock_mgr_instance.on_task_start = MagicMock()
        mock_mgr_instance.on_task_complete = MagicMock()
        
        mock_refl_instance = mock_refl.return_value
        mock_refl_instance.run_reflection.return_value = {"reflection": "test"}
        
        mock_syn_instance = mock_syn.return_value
        mock_syn_instance.process_reflection_session.return_value = []
        
        mock_exp_instance = mock_exp.return_value
        mock_exp_instance.get_planner_guidance.return_value = None
        
        loop = SelfImprovementLoop()
        cycle = loop.run("test prompt")
        
        assert cycle.status == "complete"
        assert cycle.spec == mock_spec
        assert cycle.duration_seconds > 0
        assert cycle.error is None
        assert len(loop._cycles) == 1
        assert loop._cycles[0] is cycle

    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_run_failed_cycle(
        self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan
    ):
        mock_plan.return_value.plan.side_effect = RuntimeError("planning failed")
        loop = SelfImprovementLoop()
        cycle = loop.run("test prompt")
        
        assert cycle.status == "failed"
        assert "planning failed" in cycle.error
        assert len(loop._cycles) == 1

    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_run_cycle_with_syntheses(
        self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan
    ):
        mock_spec = MagicMock()
        mock_spec.id = "spec-1"
        mock_spec.description = "test spec"
        mock_planner_output = MagicMock()
        mock_planner_output.spec = mock_spec
        mock_plan.return_value.plan.return_value = mock_planner_output
        
        mock_record = MagicMock()
        mock_record.steps = []
        mock_record.status.value = "completed"
        mock_record.total_duration_seconds = 5.0
        mock_record.test_results = []
        mock_exec.return_value.execute_spec.return_value = mock_record
        
        mock_mgr_instance = mock_mgr.return_value
        mock_mgr_instance.on_error.return_value = None
        mock_mgr_instance.on_task_start = MagicMock()
        mock_mgr_instance.on_task_complete = MagicMock()
        
        mock_refl_instance = mock_refl.return_value
        mock_refl_instance.run_reflection.return_value = {"reflection": "test"}
        
        synth1 = MagicMock()
        synth1.is_actionable = True
        synth1.synthesis = "improvement 1"
        synth2 = MagicMock()
        synth2.is_actionable = False
        synth2.synthesis = "non-actionable"
        mock_syn_instance = mock_syn.return_value
        mock_syn_instance.process_reflection_session.return_value = [synth1, synth2]
        
        exp_record = MagicMock()
        exp_record.id = "exp-1"
        mock_exp_instance = mock_exp.return_value
        mock_exp_instance.get_planner_guidance.return_value = None
        mock_exp_instance.store_from_synthesis.return_value = exp_record
        
        loop = SelfImprovementLoop()
        cycle = loop.run("test prompt")
        
        assert cycle.status == "complete"
        assert len(cycle.syntheses) == 2
        assert len(cycle.experience_stored) == 1  # only actionable
        assert cycle.experience_stored[0] == "exp-1"

    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_run_with_synthesis_guidance(
        self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan
    ):
        mock_spec = MagicMock()
        mock_spec.id = "spec-1"
        mock_spec.description = "test spec"
        mock_planner_output = MagicMock()
        mock_planner_output.spec = mock_spec
        mock_plan.return_value.plan.return_value = mock_planner_output
        
        mock_record = MagicMock()
        mock_record.steps = []
        mock_record.status.value = "completed"
        mock_record.total_duration_seconds = 5.0
        mock_record.test_results = []
        mock_exec.return_value.execute_spec.return_value = mock_record
        
        mock_mgr_instance = mock_mgr.return_value
        mock_mgr_instance.on_error.return_value = None
        mock_mgr_instance.on_task_start = MagicMock()
        mock_mgr_instance.on_task_complete = MagicMock()
        
        mock_refl_instance = mock_refl.return_value
        mock_refl_instance.run_reflection.return_value = {"reflection": "test"}
        mock_syn_instance = mock_syn.return_value
        mock_syn_instance.process_reflection_session.return_value = []
        
        mock_exp_instance = mock_exp.return_value
        mock_exp_instance.get_planner_guidance.return_value = None
        
        loop = SelfImprovementLoop()
        cycle = loop.run("test prompt", synthesis_guidance="use pattern X")
        
        assert cycle.status == "complete"
        # Verify planner was called with synthesis guidance
        plan_call = mock_plan.return_value.plan.call_args
        assert plan_call is not None
        # The planner.plan was called — check it received synthesis_guidance
        assert "synthesis_guidance" in plan_call.kwargs
        assert plan_call.kwargs["synthesis_guidance"] == "use pattern X"

    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_run_with_custom_cycle_id(
        self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan
    ):
        mock_spec = MagicMock()
        mock_spec.id = "spec-1"
        mock_spec.description = "test"
        mock_planner_output = MagicMock()
        mock_planner_output.spec = mock_spec
        mock_plan.return_value.plan.return_value = mock_planner_output
        
        mock_record = MagicMock()
        mock_record.steps = []
        mock_record.status.value = "completed"
        mock_record.total_duration_seconds = 5.0
        mock_record.test_results = []
        mock_exec.return_value.execute_spec.return_value = mock_record
        
        mock_mgr.return_value.on_error.return_value = None
        mock_mgr.return_value.on_task_start = MagicMock()
        mock_mgr.return_value.on_task_complete = MagicMock()
        mock_refl.return_value.run_reflection.return_value = {}
        mock_syn.return_value.process_reflection_session.return_value = []
        mock_exp.return_value.get_planner_guidance.return_value = None
        
        loop = SelfImprovementLoop()
        cycle = loop.run("test", cycle_id="my-custom-id")
        
        assert cycle.cycle_id == "my-custom-id"

    def test_run_max_cycles_enforced(self):
        loop = SelfImprovementLoop(max_cycles=2)
        # Without mocking, run() will fail during planning, but cycles should still be counted
        try:
            loop.run("prompt 1")
        except Exception:
            pass
        try:
            loop.run("prompt 2")
        except Exception:
            pass
        assert len(loop._cycles) == 2
        # Third cycle should raise
        with pytest.raises(RuntimeError, match="Maximum cycles"):
            loop.run("prompt 3")


# ---------------------------------------------------------------------------
# SelfImprovementLoop — run_multiple
# ---------------------------------------------------------------------------


class TestRunMultiple:
    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_run_multiple_successful(
        self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan
    ):
        mock_spec = MagicMock()
        mock_spec.id = "spec-1"
        mock_spec.description = "test"
        mock_planner_output = MagicMock()
        mock_planner_output.spec = mock_spec
        mock_plan.return_value.plan.return_value = mock_planner_output
        
        mock_record = MagicMock()
        mock_record.steps = []
        mock_record.status.value = "completed"
        mock_record.total_duration_seconds = 5.0
        mock_record.test_results = []
        mock_exec.return_value.execute_spec.return_value = mock_record
        
        mock_mgr.return_value.on_error.return_value = None
        mock_mgr.return_value.on_task_start = MagicMock()
        mock_mgr.return_value.on_task_complete = MagicMock()
        mock_refl.return_value.run_reflection.return_value = {}
        mock_syn.return_value.process_reflection_session.return_value = []
        mock_exp.return_value.get_planner_guidance.return_value = None
        
        loop = SelfImprovementLoop()
        results = loop.run_multiple(["prompt 1", "prompt 2", "prompt 3"])
        
        assert len(results) == 3
        for r in results:
            assert r.status == "complete"
        assert len(loop._cycles) == 3

    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_run_multiple_with_one_failure(
        self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan
    ):
        mock_spec = MagicMock()
        mock_spec.id = "spec-1"
        mock_spec.description = "test"
        mock_planner_output = MagicMock()
        mock_planner_output.spec = mock_spec
        
        call_count = [0]
        def plan_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("boom")
            return mock_planner_output
        
        mock_plan.return_value.plan.side_effect = plan_side_effect
        
        mock_record = MagicMock()
        mock_record.steps = []
        mock_record.status.value = "completed"
        mock_record.total_duration_seconds = 5.0
        mock_record.test_results = []
        mock_exec.return_value.execute_spec.return_value = mock_record
        
        mock_mgr.return_value.on_error.return_value = None
        mock_mgr.return_value.on_task_start = MagicMock()
        mock_mgr.return_value.on_task_complete = MagicMock()
        mock_refl.return_value.run_reflection.return_value = {}
        mock_syn.return_value.process_reflection_session.return_value = []
        mock_exp.return_value.get_planner_guidance.return_value = None
        
        loop = SelfImprovementLoop()
        results = loop.run_multiple(["prompt 1", "prompt 2", "prompt 3"])
        
        # First should succeed, second should fail, third may not run or fail
        assert any(r.status == "complete" for r in results)
        assert any(r.status == "failed" for r in results)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# SelfImprovementLoop — get_loop_health
# ---------------------------------------------------------------------------


class TestLoopHealth:
    def test_empty_health(self):
        with patch("tektos.agents.self_improvement.loop_orchestrator.Planner"), \
             patch("tektos.agents.self_improvement.loop_orchestrator.Executor"), \
             patch("tektos.agents.self_improvement.loop_orchestrator.Manager"), \
             patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem"), \
             patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine"), \
             patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine"), \
             patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay"):
            loop = SelfImprovementLoop()
            health = loop.get_loop_health()
        
        assert health["total_cycles"] == 0
        assert health["completed"] == 0
        assert health["failed"] == 0
        assert health["success_rate"] == 0.0
        assert health["total_syntheses"] == 0
        assert health["total_experiences_stored"] == 0
        assert "experience_replay_health" in health
        assert "synthesis_engine_health" in health
        assert "recent_cycles" in health

    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_health_with_cycles(
        self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan
    ):
        # Add some fake cycles directly
        loop = SelfImprovementLoop()
        
        cycle1 = LoopCycle(
            cycle_id="c1",
            timestamp_start="2024-01-01T00:00:00+00:00",
            timestamp_end="2024-01-01T00:01:00+00:00",
            prompt="p1",
            status="complete",
            syntheses=[SynthesisFeedback(insight_type="error_pattern", what_happened="execution completed", synthesis="improvement 1", priority="normal")],
            experience_stored=["e1"],
        )
        cycle2 = LoopCycle(
            cycle_id="c2",
            timestamp_start="2024-01-01T00:02:00+00:00",
            timestamp_end="2024-01-01T00:03:30+00:00",
            prompt="p2",
            status="complete",
        )
        cycle3 = LoopCycle(
            cycle_id="c3",
            timestamp_start="2024-01-01T00:04:00+00:00",
            prompt="p3",
            status="failed",
            error="test error",
        )
        loop._cycles = [cycle1, cycle2, cycle3]
        
        health = loop.get_loop_health()
        
        assert health["total_cycles"] == 3
        assert health["completed"] == 2
        assert health["failed"] == 1
        assert health["success_rate"] == 2 / 3
        assert len(health["recent_cycles"]) == 3
        
        # Check recent_cycles format
        c3 = health["recent_cycles"][2]
        assert c3["id"] == "c3"
        assert c3["status"] == "failed"
        assert c3["error"] == "test error"

    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_health_limits_recent_cycles(
        self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan
    ):
        loop = SelfImprovementLoop()
        # Add 10 cycles
        for i in range(10):
            cycle = LoopCycle(
                cycle_id=f"c{i}",
                timestamp_start=f"2024-01-01T00:{i:02d}:00+00:00",
                prompt=f"p{i}",
                status="complete",
            )
            loop._cycles.append(cycle)
        
        health = loop.get_loop_health()
        # recent_cycles should show only last 5
        assert len(health["recent_cycles"]) == 5
        assert health["recent_cycles"][0]["id"] == "c5"


# ---------------------------------------------------------------------------
# SelfImprovementLoop — clear_cycles
# ---------------------------------------------------------------------------


class TestClearCycles:
    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_clear_cycles_removes_all(
        self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan
    ):
        loop = SelfImprovementLoop()
        loop._cycles = [MagicMock(), MagicMock(), MagicMock()]
        assert len(loop._cycles) == 3
        
        loop.clear_cycles()
        assert len(loop._cycles) == 0

    @patch("tektos.agents.self_improvement.loop_orchestrator.Planner")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Executor")
    @patch("tektos.agents.self_improvement.loop_orchestrator.Manager")
    @patch("tektos.agents.self_improvement.loop_orchestrator.MemorySystem")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ReflectionEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.SynthesisEngine")
    @patch("tektos.agents.self_improvement.loop_orchestrator.ExperienceReplay")
    def test_clear_cycles_empty(self, mock_exp, mock_syn, mock_refl, mock_mem, mock_mgr, mock_exec, mock_plan):
        loop = SelfImprovementLoop()
        loop.clear_cycles()  # should not crash
        assert len(loop._cycles) == 0
