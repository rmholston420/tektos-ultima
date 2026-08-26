"""Tests for Disambiguator — identifies ambiguous terms in user prompts."""

import pytest

from tektos.agents.planner.language_game import LanguageGame
from tektos.agents.planner.disambiguator import (
    find_ambiguities,
    find_vague_terms,
    resolve_ambiguities,
    generate_clarifying_questions,
)
from tektos.agents.planner.models import Ambiguity, AmbiguityResolution, ClarifyingQuestion


class TestFindAmbiguities:
    def test_finds_ambiguous_term(self):
        ambiguities = find_ambiguities("Build a system with agents", LanguageGame.SOFTWARE_ENGINEERING)
        assert len(ambiguities) >= 1
        terms = [a.term for a in ambiguities]
        assert "agent" in terms

    def test_no_ambiguities(self):
        ambiguities = find_ambiguities("Build a simple hello world", LanguageGame.GENERAL)
        assert len(ambiguities) == 0

    def test_multiple_ambiguities(self):
        ambiguities = find_ambiguities("Build a system with agents and models", LanguageGame.SOFTWARE_ENGINEERING)
        terms = [a.term for a in ambiguities]
        assert "agent" in terms
        assert "model" in terms

    def test_ambiguity_has_meanings(self):
        ambiguities = find_ambiguities("Build a system with agents", LanguageGame.SOFTWARE_ENGINEERING)
        for amb in ambiguities:
            assert len(amb.possible_meanings) >= 1
            assert amb.term is not None

    def test_criticality_for_systems_architecture(self):
        ambiguities = find_ambiguities("Build a system with control", LanguageGame.SYSTEMS_ARCHITECTURE)
        for amb in ambiguities:
            if amb.term == "control":
                assert amb.criticality == "critical"

    def test_moderate_criticality_for_other_terms(self):
        ambiguities = find_ambiguities("Build a system with agents", LanguageGame.SYSTEMS_ARCHITECTURE)
        for amb in ambiguities:
            if amb.term == "agent":
                assert amb.criticality == "moderate"

    def test_domain_set(self):
        ambiguities = find_ambiguities("Build a system with agents", LanguageGame.SOFTWARE_ENGINEERING)
        for amb in ambiguities:
            assert amb.domain == LanguageGame.SOFTWARE_ENGINEERING


class TestFindVagueTerms:
    def test_finds_vague_term(self):
        ambiguities = find_vague_terms("Build a fast API")
        assert len(ambiguities) >= 1
        terms = [a.term for a in ambiguities]
        assert "fast" in terms

    def test_no_vague_terms(self):
        ambiguities = find_vague_terms("Build a REST API with PostgreSQL")
        assert len(ambiguities) == 0

    def test_multiple_vague_terms(self):
        ambiguities = find_vague_terms("Build a fast and secure API")
        terms = [a.term for a in ambiguities]
        assert "fast" in terms
        assert "secure" in terms

    def test_vague_ambiguity_has_clarification(self):
        ambiguities = find_vague_terms("Build a fast API")
        for amb in ambiguities:
            assert len(amb.possible_meanings) >= 1
            assert amb.criticality == "moderate"

    def test_case_insensitive(self):
        ambiguities = find_vague_terms("Build a FAST API")
        terms = [a.term for a in ambiguities]
        assert "fast" in terms


class TestResolveAmbiguities:
    def test_critical_always_ask_user(self):
        amb = Ambiguity(
            term="system",
            possible_meanings=["meaning1", "meaning2"],
            criticality="critical",
        )
        resolved, resolutions = resolve_ambiguities([amb])
        assert len(resolved) == 1
        assert len(resolutions) == 1
        assert resolutions[0] == AmbiguityResolution.ASK_USER

    def test_non_critical_with_context(self):
        amb = Ambiguity(
            term="agent",
            possible_meanings=["meaning1", "meaning2"],
            criticality="moderate",
            domain=LanguageGame.SOFTWARE_ENGINEERING,
        )
        resolved, resolutions = resolve_ambiguities([amb], user_input="context")
        assert len(resolutions) == 1
        assert resolutions[0] == AmbiguityResolution.OPTIMAL_CHOICE

    def test_non_critical_without_context(self):
        amb = Ambiguity(
            term="agent",
            possible_meanings=["meaning1", "meaning2"],
            criticality="moderate",
            domain=LanguageGame.SOFTWARE_ENGINEERING,
        )
        resolved, resolutions = resolve_ambiguities([amb])
        assert len(resolutions) == 1
        assert resolutions[0] == AmbiguityResolution.ASK_USER

    def test_empty_list(self):
        resolved, resolutions = resolve_ambiguities([])
        assert resolved == []
        assert resolutions == []

    def test_multiple_ambiguities(self):
        amb1 = Ambiguity(term="a", possible_meanings=["m1"], criticality="critical")
        amb2 = Ambiguity(term="b", possible_meanings=["m1"], criticality="moderate", domain=LanguageGame.GENERAL)
        resolved, resolutions = resolve_ambiguities([amb1, amb2], user_input="ctx")
        assert len(resolved) == 2
        assert resolutions[0] == AmbiguityResolution.ASK_USER
        assert resolutions[1] == AmbiguityResolution.OPTIMAL_CHOICE


class TestGenerateClarifyingQuestions:
    def test_only_critical(self):
        amb1 = Ambiguity(term="system", possible_meanings=["m1", "m2"], criticality="critical")
        amb2 = Ambiguity(term="agent", possible_meanings=["m1"], criticality="moderate")
        questions = generate_clarifying_questions([amb1, amb2])
        assert len(questions) == 1
        q = questions[0]
        assert "system" in q.question

    def test_no_critical(self):
        amb = Ambiguity(term="agent", possible_meanings=["m1"], criticality="moderate")
        questions = generate_clarifying_questions([amb])
        assert len(questions) == 0

    def test_question_structure(self):
        amb = Ambiguity(term="system", possible_meanings=["meaning1", "meaning2"], criticality="critical")
        questions = generate_clarifying_questions([amb])
        assert len(questions) == 1
        q = questions[0]
        assert "system" in q.question
        assert len(q.options) == 2
        assert q.default == "meaning1"
        assert "multiple meanings" in q.reason

    def test_empty_list(self):
        questions = generate_clarifying_questions([])
        assert questions == []

    def test_empty_meanings(self):
        # Ambiguity requires at least 1 possible_meaning
        amb = Ambiguity(term="x", possible_meanings=["placeholder"], criticality="critical")
        questions = generate_clarifying_questions([amb])
        assert len(questions) == 1
        assert questions[0].default == "placeholder"
