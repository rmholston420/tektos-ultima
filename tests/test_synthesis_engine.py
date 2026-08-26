"""Tests for src/tektos/runtime/synthesis_engine.py

Covers: SynthesisResult, SynthesisEngine, get_synthesis_engine.
"""

from tektos.runtime.synthesis_engine import (
    SynthesisResult,
    SynthesisEngine,
    get_synthesis_engine,
)


# ─── SynthesisResult ────────────────────────────────────────────────────────────

class TestSynthesisResult:
    def test_creation(self):
        result = SynthesisResult(
            spec_id="spec-1",
            execution_id="exec-1",
            synthesis="Synthesized output",
            confidence=0.85,
        )
        assert result.spec_id == "spec-1"
        assert result.execution_id == "exec-1"
        assert result.synthesis == "Synthesized output"
        assert result.confidence == 0.85
        assert result.lessons_learned == []
        assert result.recommendations == []

    def test_with_all_fields(self):
        result = SynthesisResult(
            spec_id="spec-2",
            execution_id="exec-2",
            synthesis="Full synthesis",
            lessons_learned=["Lesson 1", "Lesson 2"],
            recommendations=["Rec 1"],
            confidence=0.9,
        )
        assert result.lessons_learned == ["Lesson 1", "Lesson 2"]
        assert result.recommendations == ["Rec 1"]
        assert result.confidence == 0.9


# ─── SynthesisEngine ────────────────────────────────────────────────────────────

class TestSynthesisEngine:
    def setup_method(self):
        self.engine = SynthesisEngine()

    def test_synthesize_success(self):
        spec = {"id": "spec-1", "description": "Test spec"}
        feedback = {"execution_id": "exec-1", "success": True, "test_results": {"passed": 5}}
        result = self.engine.synthesize(spec, feedback)
        assert result.spec_id == "spec-1"
        assert result.execution_id == "exec-1"
        assert result.confidence == 0.8
        assert "Spec was successfully executed" in result.lessons_learned
        assert "Tests passed: 5" in result.lessons_learned

    def test_synthesize_failure(self):
        spec = {"id": "spec-2", "description": "Test spec"}
        feedback = {"execution_id": "exec-2", "success": False, "error": "Build failed"}
        result = self.engine.synthesize(spec, feedback)
        assert result.spec_id == "spec-2"
        assert result.confidence == 0.5
        assert "Execution failed: Build failed" in result.lessons_learned
        assert "Review spec clarity and feasibility" in result.lessons_learned

    def test_synthesize_with_failed_tests(self):
        spec = {"id": "spec-3", "description": "Test spec"}
        feedback = {
            "execution_id": "exec-3",
            "success": True,
            "test_results": {"passed": 3, "failed": 2},
        }
        result = self.engine.synthesize(spec, feedback)
        assert "Tests passed: 3" in result.lessons_learned
        assert "Add more comprehensive test coverage" in result.recommendations

    def test_synthesize_with_lint_issues(self):
        spec = {"id": "spec-4", "description": "Test spec"}
        feedback = {
            "execution_id": "exec-4",
            "success": True,
            "lint_issues": 3,
        }
        result = self.engine.synthesize(spec, feedback)
        assert "Address lint issues before merging" in result.recommendations

    def test_synthesize_no_recommendations(self):
        spec = {"id": "spec-5", "description": "Test spec"}
        feedback = {
            "execution_id": "exec-5",
            "success": True,
            "test_results": {"passed": 10},
        }
        result = self.engine.synthesize(spec, feedback)
        assert "Continue with current approach" in result.recommendations

    def test_get_syntheses(self):
        spec = {"id": "s1"}
        feedback = {"execution_id": "e1", "success": True}
        self.engine.synthesize(spec, feedback)
        self.engine.synthesize({"id": "s2"}, {"execution_id": "e2", "success": False})
        syntheses = self.engine.get_syntheses(limit=1)
        assert len(syntheses) == 1
        assert syntheses[0].spec_id == "s2"

    def test_to_memory_entry(self):
        spec = {"id": "s1"}
        feedback = {"execution_id": "e1", "success": True}
        self.engine.synthesize(spec, feedback)
        entry = self.engine.to_memory_entry()
        assert entry["total_syntheses"] == 1
        assert "recent_syntheses" in entry
        assert len(entry["recent_syntheses"]) == 1
        assert entry["recent_syntheses"][0]["spec_id"] == "s1"


# ─── Convenience Function ───────────────────────────────────────────────────────

class TestConvenienceFunction:
    def test_get_synthesis_engine_singleton(self):
        e1 = get_synthesis_engine()
        e2 = get_synthesis_engine()
        assert e1 is e2
