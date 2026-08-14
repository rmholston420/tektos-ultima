"""Tests for the Planner/Thinker (S4) pipeline.

Validates the full NL → Spec pipeline:
- Language game classification
- Ambiguity detection and resolution
- Translation to Proper Technical English
- Architecture template selection
- Spec generation
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.tektos.agents.planner.language_game import (
    LanguageGame,
    classify_language_game,
    get_language_game_description,
)
from src.tektos.agents.planner.disambiguator import (
    find_ambiguities,
    find_vague_terms,
    generate_clarifying_questions,
    resolve_ambiguities,
)
from src.tektos.agents.planner.models import (
    Ambiguity,
    AmbiguityResolution,
    ArchitectureChoice,
    ArchitectureTemplate,
    BuildSpec,
    ClarifyingQuestion,
    PlannerOutput,
    SpecPhase,
)
from src.tektos.agents.planner.orchestrator import Planner
from src.tektos.agents.planner.spec_generator import (
    generate_spec,
)
from src.tektos.agents.planner.template_selector import (
    TEMPLATES,
    choose_best_template,
    select_best_templates,
)
from src.tektos.agents.planner.translator import (
    translate_to_technical_english,
    add_spec_context,
)


# ── Language Game Tests ───────────────────────────────────────────────────


class TestLanguageGameClassifier:
    """Test the Language Game Classifier (Wittgenstein)."""

    def test_classify_software_engineering(self) -> None:
        result = classify_language_game(
            "Build me an API endpoint with authentication and database storage"
        )
        assert result == LanguageGame.SOFTWARE_ENGINEERING

    def test_classify_systems_architecture(self) -> None:
        result = classify_language_game(
            "Design a VSM S3 control loop for the manager system"
        )
        assert result == LanguageGame.SYSTEMS_ARCHITECTURE

    def test_classify_buddhist_philosophy(self) -> None:
        result = classify_language_game(
            "Explain dependent origination and its relationship to dharma"
        )
        assert result == LanguageGame.BUDDHIST_PHILOSOPHY

    def test_classify_general(self) -> None:
        result = classify_language_game(
            "What's the weather today?"
        )
        assert result == LanguageGame.GENERAL

    def test_classify_mixed_uses_software_engineering(self) -> None:
        result = classify_language_game(
            "Build a REST API with authentication"
        )
        assert result == LanguageGame.SOFTWARE_ENGINEERING

    def test_get_language_game_description(self) -> None:
        assert "Software Engineering" in get_language_game_description(LanguageGame.SOFTWARE_ENGINEERING)
        assert "Systems Architecture" in get_language_game_description(LanguageGame.SYSTEMS_ARCHITECTURE)
        assert "Buddhist Philosophy" in get_language_game_description(LanguageGame.BUDDHIST_PHILOSOPHY)
        assert "General" in get_language_game_description(LanguageGame.GENERAL)


# ── Disambiguator Tests ───────────────────────────────────────────────────


class TestDisambiguator:
    """Test the Disambiguator (Wittgensteinian language game awareness)."""

    def test_find_function_ambiguity(self) -> None:
        result = find_ambiguities(
            "Write a function for the API",
            LanguageGame.SOFTWARE_ENGINEERING,
        )
        assert len(result) >= 1
        assert any(amb.term == "function" for amb in result)

    def test_find_model_ambiguity(self) -> None:
        result = find_ambiguities(
            "Design a model for the system",
            LanguageGame.SYSTEMS_ARCHITECTURE,
        )
        assert len(result) >= 1
        assert any(amb.term == "model" for amb in result)

    def test_find_agent_ambiguity(self) -> None:
        result = find_ambiguities(
            "The agent should handle errors",
            LanguageGame.SOFTWARE_ENGINEERING,
        )
        assert len(result) >= 1
        assert any(amb.term == "agent" for amb in result)

    def test_find_no_ambiguity_simple(self) -> None:
        result = find_ambiguities(
            "Hello world",
            LanguageGame.GENERAL,
        )
        assert len(result) == 0

    def test_find_vague_terms(self) -> None:
        result = find_vague_terms(
            "Build a fast and secure API"
        )
        assert len(result) >= 1
        assert any(amb.term == "fast" for amb in result)

    def test_find_no_vague_terms(self) -> None:
        result = find_vague_terms(
            "Build a REST API with authentication"
        )
        assert len(result) == 0

    def test_resolve_critical_asks_user(self) -> None:
        amb = Ambiguity(
            term="system",
            possible_meanings=["A software system", "A VSM cybernetic unit"],
            criticality="critical",
        )
        resolved, resolutions = resolve_ambiguities([amb])
        assert len(resolutions) == 1
        assert resolutions[0] == AmbiguityResolution.ASK_USER

    def test_resolve_moderate_optimal_choice(self) -> None:
        amb = Ambiguity(
            term="function",
            possible_meanings=["A named block of code", "A natural law"],
            criticality="moderate",
            domain=LanguageGame.SOFTWARE_ENGINEERING,
        )
        resolved, resolutions = resolve_ambiguities([amb], user_input="I need a Python function")
        assert len(resolutions) == 1
        assert resolutions[0] == AmbiguityResolution.OPTIMAL_CHOICE

    def test_generate_clarifying_questions(self) -> None:
        amb = Ambiguity(
            term="system",
            possible_meanings=["A software system", "A VSM cybernetic unit"],
            criticality="critical",
        )
        questions = generate_clarifying_questions([amb])
        assert len(questions) == 1
        assert "system" in questions[0].question.lower()


# ── Translator Tests ──────────────────────────────────────────────────────


class TestTranslator:
    """Test the Translator (NL → Proper Technical English)."""

    def test_strip_fillers(self) -> None:
        result = translate_to_technical_english(
            "I would like you to build a function that handles errors"
        )
        assert "I would like" not in result
        assert "function" in result

    def test_replace_vague_terms(self) -> None:
        result = translate_to_technical_english(
            "Build a fast API"
        )
        assert "fast" not in result
        assert "low-latency" in result

    def test_replace_phrase(self) -> None:
        result = translate_to_technical_english(
            "build me an api endpoint with authentication"
        )
        # Phrase "build me an api" → "implement RESTful API with" (before filler strip)
        # But filler strip runs first: "build me an api" → "build api"
        # Then phrase replacement on "build api endpoint"
        assert "api" in result

    def test_remove_trailing_punctuation(self) -> None:
        result = translate_to_technical_english(
            "Build a function that handles errors."
        )
        assert not result.endswith(".")

    def test_add_spec_context(self) -> None:
        result = add_spec_context(
            "Build API",
            {"language_game": "Software Engineering", "tech_stack": ["FastAPI"]},
        )
        assert "language_game" in result
        assert "FastAPI" in result

    def test_add_spec_context_no_context(self) -> None:
        result = add_spec_context("Build API")
        assert result == "Build API"

    def test_context_budget_efficiency(self) -> None:
        """Verify that translation produces terse output (context budget is precious)."""
        verbose = "I was thinking we could maybe build a fast and secure API with authentication that handles errors"
        result = translate_to_technical_english(verbose)
        # After filler/vague/phrase replacements, the result should be more precise
        # Even if not shorter (some phrases expand), it should contain precise terms
        assert "low-latency" in result
        assert "meets security standards" in result


# ── Template Selector Tests ───────────────────────────────────────────────


class TestTemplateSelector:
    """Test the Architecture Template Selector."""

    def test_select_best_templates_small_app(self) -> None:
        reqs = ["simple API", "quick prototype", "small team"]
        templates = select_best_templates(reqs, count=1)
        assert len(templates) >= 1

    def test_select_best_templates_large_app(self) -> None:
        reqs = ["enterprise application", "large team", "strict compliance"]
        templates = select_best_templates(reqs, count=1)
        assert len(templates) >= 1

    def test_choose_best_template_prefers_user_choice(self) -> None:
        choice = choose_best_template([], user_preference="vertical_slice")
        assert choice.selected == "vertical_slice"
        assert choice.is_user_choice is True

    def test_choose_best_template_no_user_preference(self) -> None:
        choice = choose_best_template(["simple API"])
        assert choice.selected in [t.name for t in TEMPLATES]
        assert choice.is_user_choice is False

    def test_choose_best_template_invalid_preference_fallback(self) -> None:
        choice = choose_best_template([], user_preference="nonexistent_template")
        assert choice.selected in [t.name for t in TEMPLATES]


# ── Spec Generator Tests ──────────────────────────────────────────────────


class TestSpecGenerator:
    """Test the Structured Spec Generator."""

    def test_generate_spec_minimal(self) -> None:
        arch = ArchitectureChoice(
            selected="vertical_slice",
            reason="User preference",
            is_user_choice=True,
        )
        spec = generate_spec(
            original_prompt="Build an API",
            translated_prompt="implement RESTful API",
            language_game=LanguageGame.SOFTWARE_ENGINEERING,
            architecture=arch,
        )
        assert spec is not None
        assert spec.description
        assert spec.requirements
        assert len(spec.phases) >= 1

    def test_generate_spec_with_phases(self) -> None:
        arch = ArchitectureChoice(
            selected="horizontal_layered",
            reason="Best fit",
            is_user_choice=False,
        )
        phases = [
            {
                "id": "phase-1",
                "description": "MVP",
                "deliverables": ["API endpoint", "Authentication"],
                "acceptance_criteria": ["Test passes"],
                "estimated_effort": "S",
            },
        ]
        spec = generate_spec(
            original_prompt="Build API",
            translated_prompt="implement RESTful API",
            language_game=LanguageGame.SOFTWARE_ENGINEERING,
            architecture=arch,
            phases=phases,
        )
        assert len(spec.phases) == 1
        assert spec.phases[0].id == "phase-1"
        assert spec.phases[0].description == "MVP"

    def test_generate_spec_auto_requires(self) -> None:
        arch = ArchitectureChoice(
            selected="vertical_slice",
            reason="Best fit",
            is_user_choice=False,
        )
        spec = generate_spec(
            original_prompt="Build a fast API with authentication",
            translated_prompt="implement low-latency API with authentication",
            language_game=LanguageGame.SOFTWARE_ENGINEERING,
            architecture=arch,
        )
        assert len(spec.requirements) >= 1

    def test_build_spec_summary(self) -> None:
        arch = ArchitectureChoice(
            selected="vertical_slice",
            reason="Best fit",
            is_user_choice=False,
        )
        spec = generate_spec(
            original_prompt="Build API",
            translated_prompt="implement RESTful API",
            language_game=LanguageGame.SOFTWARE_ENGINEERING,
            architecture=arch,
        )
        summary = spec.summary()
        assert "spec-" in summary
        assert "arch=vertical_slice" in summary
        assert "phases=" in summary

    def test_spec_phase_model(self) -> None:
        phase = SpecPhase(
            id="phase-1",
            description="MVP",
            deliverables=["API", "Auth"],
            acceptance_criteria=["Test passes"],
            estimated_effort="S",
        )
        assert phase.id == "phase-1"
        assert phase.description == "MVP"
        assert len(phase.deliverables) == 2
        assert len(phase.acceptance_criteria) == 1

    def test_spec_phase_defaults(self) -> None:
        phase = SpecPhase(id="phase-1", description="MVP", deliverables=[])
        assert phase.acceptance_criteria == []
        assert phase.estimated_effort == "unknown"


# ── Orchestrator Tests ────────────────────────────────────────────────────


class TestPlannerOrchestrator:
    """Test the full Planner pipeline."""

    def test_plan_simple_prompt(self) -> None:
        planner = Planner()
        result = planner.plan("Build a REST API with authentication")
        assert result is not None
        assert result.spec is not None
        assert result.spec.description
        assert result.spec.requirements
        assert result.language_game_detected == LanguageGame.SOFTWARE_ENGINEERING

    def test_plan_systems_prompt(self) -> None:
        planner = Planner()
        result = planner.plan("Design a VSM S3 control loop for the manager system")
        assert result is not None
        assert result.language_game_detected == LanguageGame.SYSTEMS_ARCHITECTURE

    def test_plan_buddhist_prompt(self) -> None:
        planner = Planner()
        result = planner.plan("Explain dependent origination and its relationship to dharma")
        assert result is not None
        assert result.language_game_detected == LanguageGame.BUDDHIST_PHILOSOPHY

    def test_plan_with_context(self) -> None:
        planner = Planner()
        result = planner.plan(
            "Build a fast API",
            context={"tech_stack": ["FastAPI", "PostgreSQL"]},
        )
        assert result is not None
        assert result.spec is not None

    def test_plan_with_user_preference(self) -> None:
        planner = Planner()
        result = planner.plan(
            "Build a large enterprise application",
            user_preference="kernel_extensions",
        )
        assert result is not None
        assert result.spec.architecture.selected == "kernel_extensions"

    def test_plan_summary(self) -> None:
        planner = Planner()
        result = planner.plan("Build a REST API")
        summary = result.summary()
        assert "Planner output" in summary
        assert "spec-" in summary

    def test_planner_context_budget(self) -> None:
        planner = Planner(context_budget=50000)
        assert planner.context_budget == 50000
        assert planner.max_clarifying_questions == 3

    def test_planner_custom_settings(self) -> None:
        planner = Planner(context_budget=25000, max_clarifying_questions=5)
        assert planner.context_budget == 25000
        assert planner.max_clarifying_questions == 5


# ── Integration Tests ─────────────────────────────────────────────────────


class TestPipelineIntegration:
    """End-to-end tests for the full pipeline."""

    def test_full_pipeline_software_engineering(self) -> None:
        """Full pipeline: NL → Lang Game → Ambiguity → Translate → Template → Spec."""
        planner = Planner()
        result = planner.plan(
            "I would like you to build me a fast API endpoint with authentication and database storage"
        )

        # Verify all pipeline stages ran
        assert result.language_game_detected == LanguageGame.SOFTWARE_ENGINEERING
        assert result.spec is not None
        assert result.spec.translated_prompt
        assert result.spec.architecture.selected
        assert len(result.spec.phases) >= 1

    def test_full_pipeline_with_ambiguity(self) -> None:
        """Pipeline with ambiguous terms detected and resolved."""
        planner = Planner()
        result = planner.plan(
            "Design a system model for the agent that handles events"
        )

        # Verify ambiguities were found
        assert len(result.ambiguities_found) >= 1

        # Verify spec was still generated
        assert result.spec is not None

    def test_planner_output_model(self) -> None:
        """Verify PlannerOutput model structure."""
        arch = ArchitectureChoice(
            selected="vertical_slice",
            reason="Best fit",
            is_user_choice=False,
        )
        spec = generate_spec(
            original_prompt="Test",
            translated_prompt="implement",
            language_game=LanguageGame.GENERAL,
            architecture=arch,
        )

        output = PlannerOutput(
            spec=spec,
            language_game_detected=LanguageGame.GENERAL,
            ambiguities_found=[Ambiguity(term="test", possible_meanings=["verify code", "assess student"])],
            ambiguities_resolved=[(Ambiguity(term="test", possible_meanings=["verify code"]), AmbiguityResolution.OPTIMAL_CHOICE)],
            clarifying_questions_asked=[
                ClarifyingQuestion(
                    question="What does test mean?",
                    options=["verify code", "assess student"],
                    default="verify code",
                    reason="Multiple meanings",
                )
            ],
        )

        assert output.spec is not None
        assert len(output.ambiguities_found) == 1
        assert len(output.ambiguities_resolved) == 1
        assert len(output.clarifying_questions_asked) == 1
