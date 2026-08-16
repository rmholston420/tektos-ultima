"""Tests for Tektos spec_generator — phase generation and requirement extraction."""

from tektos.agents.planner.models import ArchitectureChoice, LanguageGame
from tektos.agents.planner.spec_generator import (
    generate_spec,
    _extract_requirements,
    _extract_constraints,
    _default_phases,
)

_ARCH = ArchitectureChoice(selected="monolith", reason="simple app", is_user_choice=True)


class TestExtractRequirements:
    def test_numbered_list(self):
        text = "Build a login system\n1. User authentication\n2. Password reset\n3. Session management"
        reqs = _extract_requirements(text)
        assert len(reqs) == 3
        assert "User authentication" in reqs

    def test_with_clauses(self):
        text = "Build a tool with real-time updates and offline support"
        reqs = _extract_requirements(text)
        # " with " splits into ["Build a tool", "real-time updates and offline support"]
        assert "real-time updates and offline support" in reqs

    def test_that_clauses(self):
        text = "Build a parser that handles Unicode and supports streaming"
        reqs = _extract_requirements(text)
        # " that " splits into ["Build a parser", "handles Unicode and supports streaming"]
        assert "handles Unicode and supports streaming" in reqs

    def test_fallback_to_full_text(self):
        text = "Just build a simple REST API"
        reqs = _extract_requirements(text)
        assert reqs == ["Just build a simple REST API"]

    def test_empty_text(self):
        reqs = _extract_requirements("")
        assert reqs == []

    def test_empty_lines_ignored(self):
        text = "\n\n1. First\n\n2. Second\n"
        reqs = _extract_requirements(text)
        assert len(reqs) == 2


class TestExtractConstraints:
    def test_must_clauses(self):
        text = "Build a system that must handle 10k concurrent users"
        constraints = _extract_constraints(text)
        assert any("10k" in c or "handle" in c.lower() for c in constraints)

    def test_no_clauses(self):
        text = "Build a system with no external dependencies"
        constraints = _extract_constraints(text)
        assert any("no external" in c or "no" in c.lower() for c in constraints)

    def test_empty_text(self):
        constraints = _extract_constraints("")
        assert constraints == []


class TestDefaultPhases:
    def test_empty_requirements(self):
        phases = _default_phases([])
        assert len(phases) == 1
        assert phases[0]["id"] == "phase-1"
        assert phases[0]["estimated_effort"] == "S"

    def test_single_requirement(self):
        phases = _default_phases(["Build login"])
        assert len(phases) == 1
        assert phases[0]["id"] == "phase-1"
        assert "Build login" in phases[0]["deliverables"]

    def test_multiple_requirements(self):
        reqs = ["A", "B", "C", "D", "E"]
        phases = _default_phases(reqs)
        assert len(phases) >= 2
        assert phases[0]["id"] == "phase-1"
        assert len(phases[0]["deliverables"]) == 3

    def test_polish_phase(self):
        reqs = ["A", "B", "C"]
        phases = _default_phases(reqs)
        assert len(phases) >= 2

    def test_effort_estimates(self):
        phases = _default_phases(["A"])
        assert phases[0]["estimated_effort"] == "S"

        phases = _default_phases(["A", "B", "C"])
        assert phases[0]["estimated_effort"] == "M"


class TestGenerateSpec:
    def test_basic(self):
        spec = generate_spec(
            original_prompt="Build a REST API",
            translated_prompt="Build a REST API",
            language_game=LanguageGame.GENERAL,
            architecture=_ARCH,
        )
        assert spec.original_prompt == "Build a REST API"
        assert len(spec.phases) >= 1

    def test_auto_description(self):
        prompt = "Build a complex feature with many details and long descriptions"
        spec = generate_spec(
            original_prompt=prompt, translated_prompt=prompt,
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
        )
        assert len(spec.description) <= 200

    def test_auto_description_truncation(self):
        long_text = "A" * 250
        spec = generate_spec(
            original_prompt=long_text, translated_prompt=long_text,
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
        )
        assert len(spec.description) == 200

    def test_with_phases(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
            phases=[{"id": "phase-1", "description": "Do it", "deliverables": ["test"]}],
        )
        assert len(spec.phases) == 1
        assert spec.phases[0].description == "Do it"

    def test_with_notes(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
            notes=["Note 1", "Note 2"],
        )
        assert len(spec.notes) == 2
        assert "Note 1" in spec.notes

    def test_with_synthesis_guidance(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
            synthesis_guidance="Lesson: test more",
        )
        assert len(spec.notes) == 1
        assert "SELF-IMPROVEMENT GUIDANCE" in spec.notes[0]

    def test_with_constraints(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
            constraints=["must be fast", "no external deps"],
        )
        assert len(spec.constraints) == 2
        assert "must be fast" in spec.constraints

    def test_with_tech_stack(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
            tech_stack=["python", "fastapi"],
        )
        assert spec.tech_stack == ["python", "fastapi"]

    def test_with_test_strategy(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
            test_strategy="tdd",
        )
        assert spec.test_strategy == "tdd"

    def test_with_context_budget_warning(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
            context_budget_warning="large spec",
        )
        assert spec.context_budget_warning == "large spec"

    def test_architecture_passed_through(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
        )
        assert spec.architecture.selected == "monolith"
        assert spec.architecture.reason == "simple app"

    def test_phases_converted_to_specphase_objects(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
        )
        for phase in spec.phases:
            assert isinstance(phase, __import__("tektos.agents.planner.models", fromlist=["SpecPhase"]).SpecPhase)

    def test_default_test_strategy(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
        )
        assert spec.test_strategy == "spec-driven"

    def test_empty_notes_list(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
            notes=[],
        )
        assert spec.notes == []

    def test_empty_constraints(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
            constraints=[],
        )
        assert spec.constraints == []

    def test_empty_tech_stack(self):
        spec = generate_spec(
            original_prompt="Build X", translated_prompt="Build X",
            language_game=LanguageGame.GENERAL, architecture=_ARCH,
            tech_stack=[],
        )
        assert spec.tech_stack == []
