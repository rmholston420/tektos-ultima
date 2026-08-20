"""Tests for Language Game Classifier."""

import pytest

from src.tektos.agents.planner.language_game import (
    LanguageGame,
    classify_language_game,
    get_language_game_description,
)


class TestLanguageGame:
    def test_all_values_present(self):
        assert LanguageGame.SOFTWARE_ENGINEERING == "software_engineering"
        assert LanguageGame.SYSTEMS_ARCHITECTURE == "systems_architecture"
        assert LanguageGame.BUDDHIST_PHILOSOPHY == "buddhist_philosophy"
        assert LanguageGame.GENERAL == "general"

    def test_iteration(self):
        assert len(list(LanguageGame)) == 4


class TestClassifyLanguageGame:
    def test_software_engineering(self):
        text = "Build an API with FastAPI and a PostgreSQL database"
        assert classify_language_game(text) == LanguageGame.SOFTWARE_ENGINEERING

    def test_systems_architecture(self):
        text = "Design a VSM-based governance system with feedback loops"
        assert classify_language_game(text) == LanguageGame.SYSTEMS_ARCHITECTURE

    def test_buddhist_philosophy(self):
        text = "Explain dependent origination and pratityasamutpada"
        assert classify_language_game(text) == LanguageGame.BUDDHIST_PHILOSOPHY

    def test_general(self):
        text = "Hello, how are you today?"
        assert classify_language_game(text) == LanguageGame.GENERAL

    def test_empty_text(self):
        assert classify_language_game("") == LanguageGame.GENERAL

    def test_tie_prefers_software_engineering(self):
        # Both SE and SA have matching keywords
        text = "api vsm"
        result = classify_language_game(text)
        assert result == LanguageGame.SOFTWARE_ENGINEERING

    def test_case_insensitive(self):
        text = "Build an API with FASTAPI and POSTGRESQL"
        assert classify_language_game(text) == LanguageGame.SOFTWARE_ENGINEERING

    def test_multiple_matches(self):
        text = "Build a docker kubernetes ci/cd pipeline for a microservice"
        assert classify_language_game(text) == LanguageGame.SOFTWARE_ENGINEERING


class TestGetLanguageGameDescription:
    def test_software_engineering(self):
        desc = get_language_game_description(LanguageGame.SOFTWARE_ENGINEERING)
        assert "Software Engineering" in desc

    def test_systems_architecture(self):
        desc = get_language_game_description(LanguageGame.SYSTEMS_ARCHITECTURE)
        assert "Systems Architecture" in desc

    def test_buddhist_philosophy(self):
        desc = get_language_game_description(LanguageGame.BUDDHIST_PHILOSOPHY)
        assert "Buddhist Philosophy" in desc

    def test_general(self):
        desc = get_language_game_description(LanguageGame.GENERAL)
        assert "General" in desc

    def test_unknown(self):
        desc = get_language_game_description("unknown")  # type: ignore
        assert desc == "Unknown"
