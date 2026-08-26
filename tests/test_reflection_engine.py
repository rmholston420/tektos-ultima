"""Tests for src/tektos/runtime/reflection_engine.py

Covers: Reflection, ReflectionEngine, get_reflection_engine.
"""

from tektos.runtime.reflection_engine import (
    Reflection,
    ReflectionEngine,
    get_reflection_engine,
)


# ─── Reflection ─────────────────────────────────────────────────────────────────

class TestReflection:
    def test_creation(self):
        r = Reflection(
            action_id="act-1",
            description="Fix bug",
            insight="Pattern can be reused",
            category="success_pattern",
        )
        assert r.action_id == "act-1"
        assert r.description == "Fix bug"
        assert r.insight == "Pattern can be reused"
        assert r.category == "success_pattern"
        assert r.confidence == 0.0
        assert r.metadata == {}

    def test_with_all_fields(self):
        r = Reflection(
            action_id="act-2",
            description="Optimize query",
            insight="Use index",
            category="optimization",
            confidence=0.9,
            metadata={"priority": "high"},
        )
        assert r.confidence == 0.9
        assert r.metadata == {"priority": "high"}


# ─── ReflectionEngine ───────────────────────────────────────────────────────────

class TestReflectionEngine:
    def setup_method(self):
        self.engine = ReflectionEngine()

    def test_reflect_on_success(self):
        action = {
            "id": "act-1",
            "description": "Fixed auth bug",
            "success": True,
        }
        reflection = self.engine.reflect_on(action)
        assert reflection.action_id == "act-1"
        assert "Successfully completed" in reflection.insight
        assert reflection.confidence == 0.8
        assert reflection.category == "new_skill"

    def test_reflect_on_failure(self):
        action = {
            "id": "act-2",
            "description": "Permission denied",
            "success": False,
            "error": "Permission denied",
        }
        reflection = self.engine.reflect_on(action)
        assert reflection.action_id == "act-2"
        assert "Failed" in reflection.insight
        assert reflection.confidence == 0.5
        assert reflection.category == "failure_pattern"

    def test_reflect_on_test_success(self):
        action = {
            "id": "act-3",
            "description": "Test passed",
            "success": True,
        }
        reflection = self.engine.reflect_on(action)
        assert reflection.category == "success_pattern"

    def test_reflect_on_optimize(self):
        action = {
            "id": "act-4",
            "description": "Optimize query performance",
            "success": True,
        }
        reflection = self.engine.reflect_on(action)
        assert reflection.category == "optimization"

    def test_get_reflections(self):
        self.engine.reflect_on({"id": "a1", "description": "d1", "success": True})
        self.engine.reflect_on({"id": "a2", "description": "d2", "success": False})
        reflections = self.engine.get_reflections(limit=1)
        assert len(reflections) == 1
        assert reflections[0].action_id == "a2"

    def test_get_insights_by_category(self):
        self.engine.reflect_on({"id": "a1", "description": "Test passed", "success": True})
        self.engine.reflect_on({"id": "a2", "description": "Permission denied", "success": False})
        success_reflections = self.engine.get_insights_by_category("success_pattern")
        failure_reflections = self.engine.get_insights_by_category("failure_pattern")
        assert len(success_reflections) == 1
        assert len(failure_reflections) == 1

    def test_to_memory_entry(self):
        self.engine.reflect_on({"id": "a1", "description": "Test passed", "success": True})
        self.engine.reflect_on({"id": "a2", "description": "Permission denied", "success": False})
        entry = self.engine.to_memory_entry()
        assert entry["total_reflections"] == 2
        assert "by_category" in entry
        assert "recent_reflections" in entry
        assert len(entry["recent_reflections"]) == 2


# ─── Convenience Function ───────────────────────────────────────────────────────

class TestConvenienceFunction:
    def test_get_reflection_engine_singleton(self):
        e1 = get_reflection_engine()
        e2 = get_reflection_engine()
        assert e1 is e2
